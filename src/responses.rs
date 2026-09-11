// TODO: if the implementation doesn't work, move if to the Python side
use std::str::FromStr;

use cookie::{Cookie, SameSite};
use pyo3::create_exception;
use pyo3::exceptions::{PyAssertionError, PyException, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyBytes, PyDict, PyFloat, PyInt, PyList, PyMemoryView, PyString, PyTuple};
use time::OffsetDateTime;

use crate::datastructures::{Headers, MutableHeaders, encode_latin1, get_raw_from_inputs, raw_to_pylist};

create_exception!(speedy._speedy, MalformedRangeHeader, PyException, "A malformed Range header.");
create_exception!(
    speedy._speedy,
    RangeNotSatisfiable,
    PyException,
    "A Range header that can't be satisfied."
);

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

#[pyfunction]
pub fn dump_json(py: Python<'_>, content: &Bound<'_, PyAny>) -> PyResult<Py<PyBytes>> {
    let value = python_to_json_value(content)?;
    let bytes = serde_json::to_vec(&value).map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok(PyBytes::new(py, &bytes).unbind())
}

fn python_to_json_value(obj: &Bound<'_, PyAny>) -> PyResult<serde_json::Value> {
    if obj.is_none() {
        return Ok(serde_json::Value::Null);
    }
    if let Ok(b) = obj.cast::<PyBool>() {
        return Ok(serde_json::Value::Bool(b.is_true()));
    }
    if obj.is_instance_of::<PyInt>() {
        let digits: String = obj.str()?.extract()?;
        let number = serde_json::Number::from_str(&digits).map_err(|e| PyValueError::new_err(e.to_string()))?;
        return Ok(serde_json::Value::Number(number));
    }
    if obj.is_instance_of::<PyFloat>() {
        return Ok(serde_json::Value::Number(json_number(obj.extract()?)?));
    }
    if let Ok(s) = obj.cast::<PyString>() {
        return Ok(serde_json::Value::String(s.extract()?));
    }
    if let Ok(list) = obj.cast::<PyList>() {
        let items = list
            .iter()
            .map(|item| python_to_json_value(&item))
            .collect::<PyResult<_>>()?;
        return Ok(serde_json::Value::Array(items));
    }
    if let Ok(tuple) = obj.cast::<PyTuple>() {
        let items = tuple
            .iter()
            .map(|item| python_to_json_value(&item))
            .collect::<PyResult<_>>()?;
        return Ok(serde_json::Value::Array(items));
    }
    if let Ok(dict) = obj.cast::<PyDict>() {
        let map = dict
            .iter()
            .map(|(key, value)| Ok((json_key_string(&key)?, python_to_json_value(&value)?)))
            .collect::<PyResult<serde_json::Map<String, serde_json::Value>>>()?;
        return Ok(serde_json::Value::Object(map));
    }

    let type_name: String = obj.get_type().name()?.extract()?;
    Err(PyTypeError::new_err(format!(
        "Object of type {type_name} is not JSON serializable"
    )))
}

fn json_key_string(key: &Bound<'_, PyAny>) -> PyResult<String> {
    if let Ok(s) = key.cast::<PyString>() {
        return s.extract();
    }
    if key.is_none() {
        return Ok("null".to_string());
    }
    if let Ok(b) = key.cast::<PyBool>() {
        return Ok(if b.is_true() {
            "true".to_string()
        } else {
            "false".to_string()
        });
    }
    if key.is_instance_of::<PyInt>() {
        return key.str()?.extract();
    }
    if key.is_instance_of::<PyFloat>() {
        let f: f64 = key.extract()?;
        return serde_json::to_string(&json_number(f)?).map_err(|e| PyValueError::new_err(e.to_string()));
    }
    let type_name: String = key.get_type().name()?.extract()?;
    Err(PyTypeError::new_err(format!(
        "keys must be str, int, float, bool or None, not {type_name}"
    )))
}

fn json_number(f: f64) -> PyResult<serde_json::Number> {
    if !f.is_finite() {
        return Err(json_out_of_range(f));
    }
    serde_json::Number::from_f64(f).ok_or_else(|| json_out_of_range(f))
}

fn json_out_of_range(f: f64) -> PyErr {
    let repr = if f.is_nan() {
        "nan"
    } else if f.is_sign_positive() {
        "inf"
    } else {
        "-inf"
    };
    PyValueError::new_err(format!("Out of range float values are not JSON compliant: {repr}"))
}

#[pyfunction]
pub fn multipart_closing_boundary(py: Python<'_>, boundary: &str) -> Py<PyBytes> {
    PyBytes::new(py, format!("--{boundary}--").as_bytes()).unbind()
}

#[pyfunction]
pub fn multipart_range_header(
    py: Python<'_>,
    boundary: &str,
    content_type: &str,
    start: u64,
    end: u64,
    max_size: u64,
) -> Py<PyBytes> {
    let text = format!(
        "--{boundary}\r\nContent-Type: {content_type}\r\nContent-Range: bytes {start}-{}/{max_size}\r\n\r\n",
        end - 1
    );
    PyBytes::new(py, text.as_bytes()).unbind()
}

#[pyfunction]
pub fn multipart_content_length(ranges: Vec<(u64, u64)>, boundary: &str, max_size: u64, content_type: &str) -> u64 {
    let boundary_len = boundary.len() as u64;
    let static_header_len = 49 + boundary_len + content_type.len() as u64 + max_size.to_string().len() as u64;
    let sum: u64 = ranges
        .iter()
        .map(|&(start, end)| {
            start.to_string().len() as u64 + (end - 1).to_string().len() as u64 + static_header_len + (end - start)
        })
        .sum();
    sum + 4 + boundary_len
}

#[pyfunction]
pub fn compute_etag(mtime: f64, size: u64) -> String {
    let etag_base = format!("{mtime:?}-{size}");
    let digest = md5::compute(etag_base.as_bytes());
    format!("\"{digest:x}\"")
}

#[pyfunction]
pub fn parse_range_header(
    py: Python<'_>,
    range_header: &str,
    file_size: u64,
    max_ranges: usize,
) -> PyResult<Vec<(u64, u64)>> {
    let (units, range_part) = range_header
        .split_once('=')
        .ok_or_else(|| malformed_range_error(py, "Malformed range header."))?;
    if units.trim().to_lowercase() != "bytes" {
        return Err(malformed_range_error(py, "Only support bytes range"));
    }

    if range_part.matches(',').count() + 1 > max_ranges {
        return Ok(Vec::new());
    }

    let ranges = parse_ranges(range_part, file_size);
    if ranges.is_empty() {
        return Err(malformed_range_error(py, "Range header: range must be requested"));
    }
    if ranges.iter().any(|&(start, _)| start >= file_size) {
        return Err(range_not_satisfiable_error(py, file_size));
    }
    if ranges.iter().any(|&(start, end)| start >= end) {
        return Err(malformed_range_error(py, "Range header: start must be less than end"));
    }

    Ok(if ranges.len() == 1 {
        ranges
    } else {
        merge_ranges(ranges)
    })
}

fn merge_ranges(mut ranges: Vec<(u64, u64)>) -> Vec<(u64, u64)> {
    ranges.sort_unstable();
    ranges.into_iter().fold(Vec::new(), |mut merged, (start, end)| {
        match merged.last_mut() {
            Some((_, last_end)) if start <= *last_end => *last_end = (*last_end).max(end),
            _ => merged.push((start, end)),
        }
        merged
    })
}

fn parse_ranges(range_value: &str, file_size: u64) -> Vec<(u64, u64)> {
    range_value
        .split(',')
        .filter_map(|part| {
            let part = part.trim();
            if part.is_empty() || part == "-" || !part.contains('-') {
                return None;
            }
            let (start_str, end_str) = part.split_once('-')?;
            let start_str = start_str.trim();
            let end_str = end_str.trim();

            let start: u64 = if start_str.is_empty() {
                let suffix_len: u64 = end_str.parse().ok()?;
                file_size.saturating_sub(suffix_len)
            } else {
                start_str.parse().ok()?
            };
            let end: u64 = if !start_str.is_empty() && !end_str.is_empty() {
                let requested_end: u64 = end_str.parse().ok()?;
                if requested_end < file_size {
                    requested_end + 1
                } else {
                    file_size
                }
            } else {
                file_size
            };
            Some((start, end))
        })
        .collect()
}

fn malformed_range_error(py: Python<'_>, content: &str) -> PyErr {
    let err = MalformedRangeHeader::new_err(content.to_string());
    let _ = err.value(py).setattr("content", content);
    err
}

fn range_not_satisfiable_error(py: Python<'_>, max_size: u64) -> PyErr {
    let err = RangeNotSatisfiable::new_err(format!("Range not satisfiable for a resource of size {max_size}"));
    let _ = err.value(py).setattr("max_size", max_size);
    err
}
