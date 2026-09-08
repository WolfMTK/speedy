use cookie::Cookie;
use pyo3::exceptions::{PyAssertionError, PyKeyError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList, PyString};
use pyo3::{PyTypeCheck, create_exception};
use url::form_urlencoded;

use crate::datastructures::{Address, Headers, QueryParams, State, URL, get_raw_from_inputs, url_from_scope};

create_exception!(
    speedy._speedy,
    JSONDecodeError,
    PyValueError,
    "Raised when JSON decoding fails; shaped like json.JSONDecodeError."
);

fn downcast_to_py<T: PyTypeCheck>(obj: &Bound<'_, PyAny>) -> PyResult<Py<T>> {
    Ok(obj.cast::<T>()?.clone().unbind())
}

#[pyclass(mapping, subclass, module = "speedy.requests")]
pub struct HTTPConnection {
    scope: Py<PyDict>,
    cached_url: Option<Py<URL>>,
    cached_base_url: Option<Py<URL>>,
    cached_headers: Option<Py<Headers>>,
    cached_query_params: Option<Py<QueryParams>>,
    cached_cookies: Option<Py<PyDict>>,
    cached_state: Option<Py<State>>,
}

#[pymethods]
impl HTTPConnection {
    #[new]
    #[pyo3(signature = (scope, receive=None))]
    fn new(py: Python<'_>, scope: Py<PyDict>, receive: Option<Py<PyAny>>) -> PyResult<Self> {
        let scope_type: String = scope
            .bind(py)
            .get_item("type")?
            .ok_or_else(|| PyKeyError::new_err("type"))?
            .extract()?;
        if scope_type != "http" && scope_type != "websocket" {
            return Err(PyAssertionError::new_err(()));
        }

        let _ = receive;

        Ok(Self {
            scope,
            cached_url: None,
            cached_base_url: None,
            cached_headers: None,
            cached_query_params: None,
            cached_cookies: None,
            cached_state: None,
        })
    }

    fn __getitem__(&self, py: Python<'_>, key: String) -> PyResult<Py<PyAny>> {
        self.scope
            .bind(py)
            .get_item(&key)?
            .map(|v| v.unbind())
            .ok_or_else(|| PyKeyError::new_err(key))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        Ok(self.scope.bind(py).as_any().call_method0("__iter__")?.unbind())
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        self.scope.bind(py).len()
    }

    fn __contains__(&self, py: Python<'_>, key: String) -> PyResult<bool> {
        self.scope.bind(py).contains(key)
    }

    #[pyo3(signature = (key, default=None))]
    fn get(&self, py: Python<'_>, key: String, default: Option<Py<PyAny>>) -> PyResult<Py<PyAny>> {
        match self.scope.bind(py).get_item(&key)? {
            Some(value) => Ok(value.unbind()),
            None => Ok(default.unwrap_or_else(|| py.None())),
        }
    }

    fn keys(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        Ok(self.scope.bind(py).call_method0("keys")?.unbind())
    }

    fn values(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        Ok(self.scope.bind(py).call_method0("values")?.unbind())
    }

    fn items(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        Ok(self.scope.bind(py).call_method0("items")?.unbind())
    }

    #[getter]
    fn app(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        self.scope
            .bind(py)
            .get_item("app")?
            .map(|v| v.unbind())
            .ok_or_else(|| PyKeyError::new_err("app"))
    }

    #[getter]
    fn url(&mut self, py: Python<'_>) -> PyResult<Py<URL>> {
        if let Some(cached) = &self.cached_url {
            return Ok(cached.clone_ref(py));
        }
        let url = Py::new(py, url_from_scope(self.scope.bind(py))?)?;
        self.cached_url = Some(url.clone_ref(py));
        Ok(url)
    }

    #[getter]
    fn base_url(&mut self, py: Python<'_>) -> PyResult<Py<URL>> {
        if let Some(cached) = &self.cached_base_url {
            return Ok(cached.clone_ref(py));
        }

        let scope = self.scope.bind(py);
        let base_scope = scope.copy()?;

        let app_root_path: String = match base_scope.get_item("app_root_path")? {
            Some(v) if !v.is_none() => v.extract()?,
            _ => match base_scope.get_item("root_path")? {
                Some(v) if !v.is_none() => v.extract()?,
                _ => String::new(),
            },
        };
        let mut path = app_root_path.clone();
        if !path.ends_with('/') {
            path.push('/');
        }
        base_scope.set_item("path", &path)?;
        base_scope.set_item("query_string", PyBytes::new(py, b""))?;
        base_scope.set_item("root_path", &app_root_path)?;

        let base_url = Py::new(py, url_from_scope(&base_scope)?)?;
        self.cached_base_url = Some(base_url.clone_ref(py));
        Ok(base_url)
    }

    #[getter]
    fn headers(&mut self, py: Python<'_>) -> PyResult<Py<Headers>> {
        if let Some(cached) = &self.cached_headers {
            return Ok(cached.clone_ref(py));
        }
        let raw = get_raw_from_inputs(None, None, Some(self.scope.bind(py)))?;
        let headers = Py::new(py, Headers { raw })?;
        self.cached_headers = Some(headers.clone_ref(py));
        Ok(headers)
    }

    #[getter]
    fn query_params(&mut self, py: Python<'_>) -> PyResult<Py<QueryParams>> {
        if let Some(cached) = &self.cached_query_params {
            return Ok(cached.clone_ref(py));
        }
        let query_string = self
            .scope
            .bind(py)
            .get_item("query_string")?
            .ok_or_else(|| PyKeyError::new_err("query_string"))?;
        let query_params_obj = py.get_type::<QueryParams>().call1((query_string,))?;
        let query_params = downcast_to_py::<QueryParams>(&query_params_obj)?;
        self.cached_query_params = Some(query_params.clone_ref(py));
        Ok(query_params)
    }

    #[getter]
    fn path_params(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        match self.scope.bind(py).get_item("path_params")? {
            Some(value) if !value.is_none() => Ok(value.cast::<PyDict>()?.clone().unbind()),
            _ => Ok(PyDict::new(py).unbind()),
        }
    }

    #[getter]
    fn cookies(&mut self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        if let Some(cached) = &self.cached_cookies {
            return Ok(cached.clone_ref(py));
        }

        let headers = self.headers(py)?;
        let cookie_headers = headers.bind(py).call_method1("getlist", ("cookie",))?;

        let header_values: Vec<String> = cookie_headers
            .try_iter()?
            .map(|item| item?.extract())
            .collect::<PyResult<_>>()?;

        let result = PyDict::new(py);
        header_values
            .iter()
            .flat_map(|header_value| Cookie::split_parse_encoded(header_value.as_str()))
            .filter_map(Result::ok)
            .try_for_each(|cookie| result.set_item(cookie.name(), cookie.value()))?;

        let cookies = result.unbind();
        self.cached_cookies = Some(cookies.clone_ref(py));
        Ok(cookies)
    }

    #[getter]
    fn client(&self, py: Python<'_>) -> PyResult<Option<Address>> {
        match self.scope.bind(py).get_item("client")? {
            Some(value) if !value.is_none() => {
                let (host, port): (String, u16) = value.extract()?;
                Ok(Some(Address { host, port }))
            }
            _ => Ok(None),
        }
    }

    #[getter]
    fn session(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let session = self.scope.bind(py).get_item("session")?.ok_or_else(|| {
            PyAssertionError::new_err("SessionMiddleware must be installed to access request.session")
        })?;
        if session.hasattr("mark_accessed")? {
            session.call_method0("mark_accessed")?;
        }
        Ok(session.unbind())
    }

    #[getter]
    fn auth(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        self.scope
            .bind(py)
            .get_item("auth")?
            .map(|v| v.unbind())
            .ok_or_else(|| {
                PyAssertionError::new_err("AuthenticationMiddleware must be installed to access request.auth")
            })
    }

    #[getter]
    fn user(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        self.scope
            .bind(py)
            .get_item("user")?
            .map(|v| v.unbind())
            .ok_or_else(|| {
                PyAssertionError::new_err("AuthenticationMiddleware must be installed to access request.user")
            })
    }

    #[getter]
    fn state(&mut self, py: Python<'_>) -> PyResult<Py<State>> {
        if self.cached_state.is_none() {
            let scope = self.scope.bind(py);
            if scope.get_item("state")?.is_none() {
                scope.set_item("state", PyDict::new(py))?;
            }
            let state_dict = scope.get_item("state")?.expect("just set above if missing");
            let state_obj = py.get_type::<State>().call1((state_dict,))?;
            self.cached_state = Some(state_obj.extract()?);
        }
        Ok(self.cached_state.as_ref().expect("just populated above").clone_ref(py))
    }

    #[pyo3(signature = (name, **path_params))]
    fn url_for(&mut self, py: Python<'_>, name: String, path_params: Option<&Bound<'_, PyDict>>) -> PyResult<Py<URL>> {
        let provider = match self.scope.bind(py).get_item("router")? {
            Some(v) if !v.is_none() => v,
            _ => self
                .scope
                .bind(py)
                .get_item("app")?
                .filter(|v| !v.is_none())
                .ok_or_else(|| {
                    PyRuntimeError::new_err(
                        "The `url_for` method can only be used inside a Speedy application or with a router.",
                    )
                })?,
        };

        let url_path = match path_params {
            Some(kwargs) => provider.call_method("url_path_for", (name,), Some(kwargs))?,
            None => provider.call_method1("url_path_for", (name,))?,
        };

        let base_url = self.base_url(py)?;
        let absolute = url_path.call_method1("make_absolute_url", (base_url,))?;
        downcast_to_py::<URL>(&absolute)
    }

    #[getter]
    fn scope(&self, py: Python<'_>) -> Py<PyDict> {
        self.scope.clone_ref(py)
    }
}

#[pyclass(extends = HTTPConnection, subclass, module = "speedy.requests")]
pub struct Request {
    receive: Py<PyAny>,
    send: Py<PyAny>,
}

#[pymethods]
impl Request {
    #[new]
    fn new(
        py: Python<'_>,
        scope: Py<PyDict>,
        receive: Py<PyAny>,
        send: Py<PyAny>,
    ) -> PyResult<PyClassInitializer<Request>> {
        let scope_type: String = scope
            .bind(py)
            .get_item("type")?
            .ok_or_else(|| PyKeyError::new_err("type"))?
            .extract()?;
        if scope_type != "http" {
            return Err(PyAssertionError::new_err(()));
        }
        let base = HTTPConnection::new(py, scope, None)?;
        Ok(PyClassInitializer::from(base).add_subclass(Request { receive, send }))
    }

    #[getter]
    fn method(slf: &Bound<'_, Self>, py: Python<'_>) -> PyResult<String> {
        let base = slf.borrow().into_super();
        base.scope
            .bind(py)
            .get_item("method")?
            .ok_or_else(|| PyKeyError::new_err("method"))?
            .extract()
    }

    #[getter]
    fn receive(&self, py: Python<'_>) -> Py<PyAny> {
        self.receive.clone_ref(py)
    }

    #[getter(_send)]
    fn get_send(&self, py: Python<'_>) -> Py<PyAny> {
        self.send.clone_ref(py)
    }
}

fn char_offset_for_line_col(text: &str, line: usize, column: usize) -> usize {
    let line_start = if line <= 1 {
        0
    } else {
        text.chars()
            .enumerate()
            .filter(|&(_, ch)| ch == '\n')
            .nth(line - 2)
            .map(|(idx, _)| idx + 1)
            .unwrap_or_else(|| text.chars().count())
    };
    line_start + column.saturating_sub(1)
}

fn json_decode_error(py: Python<'_>, msg: &str, doc: &str, pos: usize) -> PyErr {
    let bounded_pos = pos.min(doc.len());
    let lineno = doc[..bounded_pos].matches('\n').count() + 1;
    let colno = match doc[..bounded_pos].rfind('\n') {
        Some(idx) => bounded_pos - idx,
        None => bounded_pos + 1,
    };
    let errmsg = format!("{msg}: line {lineno} column {colno} (char {pos})");

    let err = JSONDecodeError::new_err(errmsg);
    let value = err.value(py);
    let _ = value.setattr("msg", msg);
    let _ = value.setattr("doc", doc);
    let _ = value.setattr("pos", pos);
    let _ = value.setattr("lineno", lineno);
    let _ = value.setattr("colno", colno);
    err
}

fn big_int_from_decimal_str(py: Python<'_>, s: &str) -> PyResult<Py<PyAny>> {
    let (negative, digits) = match s.strip_prefix('-') {
        Some(rest) => (true, rest),
        None => (false, s),
    };
    if digits.is_empty() || !digits.bytes().all(|b| b.is_ascii_digit()) {
        return Err(PyValueError::new_err(format!("invalid integer literal in JSON number: {s:?}")));
    }

    let ten = 10i32.into_pyobject(py)?.into_any();
    let acc = digits
        .bytes()
        .try_fold(0i32.into_pyobject(py)?.into_any().unbind(), |acc, byte| {
            let digit = (byte - b'0') as i32;
            PyResult::Ok(acc.bind(py).mul(&ten)?.add(digit.into_pyobject(py)?)?.unbind())
        })?;

    Ok(if negative {
        acc.bind(py).call_method0("__neg__")?.unbind()
    } else {
        acc
    })
}

fn json_number_to_py(py: Python<'_>, n: &serde_json::Number) -> PyResult<Py<PyAny>> {
    if let Some(v) = n.as_i64() {
        return Ok(v.into_pyobject(py)?.into_any().unbind());
    }
    if let Some(v) = n.as_u64() {
        return Ok(v.into_pyobject(py)?.into_any().unbind());
    }
    if let Some(v) = n.as_f64() {
        if n.to_string().contains(['.', 'e', 'E']) {
            return Ok(v.into_pyobject(py)?.into_any().unbind());
        }
    }
    big_int_from_decimal_str(py, &n.to_string())
}

fn json_value_to_py(py: Python<'_>, value: &serde_json::Value) -> PyResult<Py<PyAny>> {
    match value {
        serde_json::Value::Null => Ok(py.None()),
        serde_json::Value::Bool(b) => Ok(b.into_pyobject(py)?.to_owned().into_any().unbind()),
        serde_json::Value::Number(n) => json_number_to_py(py, n),
        serde_json::Value::String(s) => Ok(PyString::new(py, s).into_any().unbind()),
        serde_json::Value::Array(items) => {
            let converted = items
                .iter()
                .map(|v| json_value_to_py(py, v))
                .collect::<PyResult<Vec<_>>>()?;
            Ok(PyList::new(py, converted)?.into_any().unbind())
        }
        serde_json::Value::Object(map) => {
            let dict = PyDict::new(py);
            map.iter()
                .try_for_each(|(k, v)| dict.set_item(k, json_value_to_py(py, v)?))?;
            Ok(dict.into_any().unbind())
        }
    }
}

#[pyfunction]
pub fn parse_json(py: Python<'_>, body: &[u8]) -> PyResult<Py<PyAny>> {
    let text = std::str::from_utf8(body).map_err(|e| json_decode_error(py, &format!("invalid utf-8: {e}"), "", 0))?;
    serde_json::from_str::<serde_json::Value>(text)
        .map_err(|e| {
            let pos = char_offset_for_line_col(text, e.line(), e.column());
            json_decode_error(py, &e.to_string(), text, pos)
        })
        .and_then(|value| json_value_to_py(py, &value))
}

#[pyfunction]
pub fn parse_urlencoded_form(body: &[u8]) -> Vec<(String, String)> {
    form_urlencoded::parse(body)
        .map(|(k, v)| (k.into_owned(), v.into_owned()))
        .collect()
}
