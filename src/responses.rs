// TODO: if the implementation doesn't work, move if to the Python side

use cookie::{Cookie, SameSite};
use pyo3::exceptions::{PyAssertionError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyList, PyMemoryView};
use time::OffsetDateTime;

use crate::datastructures::{Headers, MutableHeaders, encode_latin1, get_raw_from_inputs, raw_to_pylist};

fn render(py: Python<'_>, content: Option<&Bound<'_, PyAny>>, charset: &str) -> PyResult<Py<PyAny>> {
    match content {
        None => Ok(PyBytes::new(py, b"").into_any().unbind()),
        Some(content) if is_bytes_like(content) => Ok(content.clone().unbind()),
        Some(content) => Ok(content.call_method1("encode", (charset,))?.unbind()),
    }
}

fn is_bytes_like(content: &Bound<'_, PyAny>) -> bool {
    content.is_instance_of::<PyBytes>() || content.is_instance_of::<PyMemoryView>()
}

#[allow(clippy::too_many_arguments)]
fn build_headers(
    py: Python<'_>,
    headers: Option<&Bound<'_, PyAny>>,
    status_code: i64,
    media_type: Option<&str>,
    charset: &str,
    body: &Bound<'_, PyAny>,
) -> PyResult<Vec<(Vec<u8>, Vec<u8>)>> {
    let mut raw_headers: Vec<(Vec<u8>, Vec<u8>)> = match headers {
        Some(headers) => get_raw_from_inputs(Some(headers), None, None)?,
        None => Vec::new(),
    };
    let population_content_length = !raw_headers.iter().any(|(k, _)| k == b"content-length");
    let population_content_type = !raw_headers.iter().any(|(k, _)| k == b"content-type");

    if population_content_length && !(status_code < 200 || status_code == 204 || status_code == 304) {
        let body_len = body.len()?;
        raw_headers.push((b"content-length".to_vec(), encode_latin1(&body_len.to_string())?));
    }

    if let Some(mt) = media_type {
        if population_content_type {
            let mut content_type = mt.to_string();
            if content_type.starts_with("text/") && !content_type.to_lowercase().contains("charset=") {
                content_type.push_str("; charset=");
                content_type.push_str(charset);
            }
            raw_headers.push((b"content-type".to_vec(), encode_latin1(&content_type)?));
        }
    }

    let _ = py;
    Ok(raw_headers)
}

fn make_headers_obj(py: Python<'_>, raw: Vec<(Vec<u8>, Vec<u8>)>) -> PyResult<Py<MutableHeaders>> {
    let initializer = PyClassInitializer::from(Headers { raw }).add_subclass(MutableHeaders {});
    Py::new(py, initializer)
}

fn parse_samesite(value: &str) -> PyResult<SameSite> {
    match value.to_lowercase().as_str() {
        "strict" => Ok(SameSite::Strict),
        "lax" => Ok(SameSite::Lax),
        "none" => Ok(SameSite::None),
        _ => Err(PyAssertionError::new_err("samesite must be either 'strict', 'lax' or 'none'")),
    }
}

fn extract_expires(expires: &Bound<'_, PyAny>) -> PyResult<OffsetDateTime> {
    if let Ok(dt) = expires.extract::<OffsetDateTime>() {
        return Ok(dt);
    }
    if let Ok(timestamp) = expires.extract::<i64>() {
        return OffsetDateTime::from_unix_timestamp(timestamp)
            .map_err(|e| PyValueError::new_err(format!("invalid `expires` timestamp: {e}")));
    }
    Err(PyTypeError::new_err(
        "`expires` must be a datetime.datetime or an int (Unix timestamp in seconds)",
    ))
}

fn apply_common_cookie_attrs(
    mut builder: cookie::CookieBuilder,
    domain: Option<String>,
    samesite: Option<String>,
    partitioned: bool,
) -> PyResult<cookie::CookieBuilder> {
    if let Some(domain) = domain {
        builder = builder.domain(domain);
    }
    if let Some(samesite) = samesite {
        builder = builder.same_site(parse_samesite(&samesite)?);
    }
    if partitioned {
        builder = builder.partitioned(true);
    }
    Ok(builder)
}

fn push_cookie_header(
    headers_obj: &Py<MutableHeaders>,
    py: Python<'_>,
    builder: cookie::CookieBuilder<'_>,
) -> PyResult<()> {
    let cookie_val = builder.build().encoded().to_string();
    let mut base = headers_obj.bind(py).borrow_mut().into_super();
    base.raw.push((b"set-cookie".to_vec(), encode_latin1(&cookie_val)?));
    Ok(())
}

#[pyclass(subclass, module = "speedy.responses")]
pub struct Response {
    #[pyo3(get, set)]
    status_code: i64,
    #[pyo3(get, set)]
    media_type: Option<String>,
    #[pyo3(get, set)]
    charset: String,
    #[pyo3(get, set)]
    background: Option<Py<PyAny>>,
    #[pyo3(get, set)]
    body: Py<PyAny>,
    headers_obj: Py<MutableHeaders>,
}

#[pymethods]
impl Response {
    #[new]
    fn new(
        py: Python<'_>,
        content: Option<&Bound<'_, PyAny>>,
        status_code: i64,
        headers: Option<&Bound<'_, PyAny>>,
        media_type: Option<String>,
        background: Option<Py<PyAny>>,
    ) -> PyResult<Self> {
        let charset = "utf-8".to_string();
        let body = render(py, content, &charset)?;
        let raw_headers = build_headers(py, headers, status_code, media_type.as_deref(), &charset, body.bind(py))?;
        let headers_obj = make_headers_obj(py, raw_headers)?;

        Ok(Response {
            status_code,
            media_type,
            charset,
            background,
            body,
            headers_obj,
        })
    }

    #[getter]
    fn headers(&self, py: Python<'_>) -> Py<MutableHeaders> {
        self.headers_obj.clone_ref(py)
    }

    #[getter]
    fn raw_headers(&self, py: Python<'_>) -> PyResult<Py<PyList>> {
        let base = self.headers_obj.bind(py).borrow().into_super();
        Ok(raw_to_pylist(py, &base.raw)?.unbind())
    }

    #[setter]
    fn set_raw_headers(&mut self, py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<()> {
        let raw = value.extract::<Vec<(Vec<u8>, Vec<u8>)>>()?;
        self.headers_obj = make_headers_obj(py, raw)?;
        Ok(())
    }

    #[pyo3(signature = (
        key,
        value=String::new(),
        max_age=None,
        expires=None,
        path=Some("/".to_string()),
        domain=None,
        secure=false,
        httponly=false,
        samesite=Some("lax".to_string()),
        partitioned=false,
    ))]
    #[allow(clippy::too_many_arguments)]
    fn set_cookie(
        &mut self,
        py: Python<'_>,
        key: String,
        value: String,
        max_age: Option<i64>,
        expires: Option<&Bound<'_, PyAny>>,
        path: Option<String>,
        domain: Option<String>,
        secure: bool,
        httponly: bool,
        samesite: Option<String>,
        partitioned: bool,
    ) -> PyResult<()> {
        let mut builder = Cookie::build((key, value))
            .path(path.unwrap_or_default())
            .secure(secure)
            .http_only(httponly);

        if let Some(max_age) = max_age {
            builder = builder.max_age(time::Duration::seconds(max_age));
        }
        if let Some(expires) = expires {
            if !expires.is_none() {
                builder = builder.expires(extract_expires(expires)?);
            }
        }
        builder = apply_common_cookie_attrs(builder, domain, samesite, partitioned)?;
        push_cookie_header(&self.headers_obj, py, builder)
    }

    #[pyo3(signature = (
        key,
        path="/".to_string(),
        domain=None,
        secure=false,
        httponly=false,
        samesite=Some("lax".to_string()),
        partitioned=false,
    ))]
    #[allow(clippy::too_many_arguments)]
    fn delete_cookie(
        &mut self,
        py: Python<'_>,
        key: String,
        path: String,
        domain: Option<String>,
        secure: bool,
        httponly: bool,
        samesite: Option<String>,
        partitioned: bool,
    ) -> PyResult<()> {
        let builder = Cookie::build((key, ""))
            .path(path)
            .secure(secure)
            .http_only(httponly)
            .max_age(time::Duration::seconds(0))
            .expires(OffsetDateTime::UNIX_EPOCH);

        let builder = apply_common_cookie_attrs(builder, domain, samesite, partitioned)?;
        push_cookie_header(&self.headers_obj, py, builder)
    }
}
