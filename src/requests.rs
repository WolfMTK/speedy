use pyo3::exceptions::{PyAssertionError, PyKeyError, PyRuntimeError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyString};
use pyo3::{PyTypeCheck, intern};
use url::form_urlencoded;

use crate::datastructures::{
    Address, Headers, QueryParams, State, URL, extract_host_port, get_raw_from_inputs, url_from_scope,
};

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

impl HTTPConnection {
    fn from_scope(scope: Py<PyDict>) -> Self {
        Self {
            scope,
            cached_url: None,
            cached_base_url: None,
            cached_headers: None,
            cached_query_params: None,
            cached_cookies: None,
            cached_state: None,
        }
    }
}

#[pymethods]
impl HTTPConnection {
    #[new]
    #[pyo3(signature = (scope, receive=None))]
    fn new(py: Python<'_>, scope: Py<PyDict>, receive: Option<Py<PyAny>>) -> PyResult<Self> {
        if !scope_type_in(scope.bind(py), &["http", "websocket"])? {
            return Err(PyAssertionError::new_err(()));
        }
        let _ = receive;
        Ok(Self::from_scope(scope))
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
            .map(String::as_str)
            .flat_map(parse_cookie_header)
            .try_for_each(|(name, value)| result.set_item(name, value))?;

        let cookies = result.unbind();
        self.cached_cookies = Some(cookies.clone_ref(py));
        Ok(cookies)
    }

    #[getter]
    fn client(&self, py: Python<'_>) -> PyResult<Option<Address>> {
        match self.scope.bind(py).get_item("client")? {
            Some(value) if !value.is_none() => {
                let (host, port) = extract_host_port(&value)?;
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
            let shared_key = intern!(py, "speedy.state");
            let state_obj = match scope.get_item(shared_key)? {
                Some(shared) => shared,
                None => {
                    if scope.get_item("state")?.is_none() {
                        scope.set_item("state", PyDict::new(py))?;
                    }
                    let state_dict = scope.get_item("state")?;
                    let created = py.get_type::<State>().call1((state_dict, false))?;
                    scope.set_item(shared_key, &created)?;
                    created
                }
            };

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
    #[pyo3(signature = (scope, receive=None, send=None))]
    fn new(
        py: Python<'_>,
        scope: Py<PyDict>,
        receive: Option<Py<PyAny>>,
        send: Option<Py<PyAny>>,
    ) -> PyResult<PyClassInitializer<Request>> {
        if !scope_type_in(scope.bind(py), &["http"])? {
            return Err(PyAssertionError::new_err(()));
        }
        let receive = channel_or_placeholder(py, receive, "empty_receive")?;
        let send = channel_or_placeholder(py, send, "empty_send")?;
        Ok(PyClassInitializer::from(HTTPConnection::from_scope(scope)).add_subclass(Request { receive, send }))
    }

    #[getter]
    fn method(slf: &Bound<'_, Self>, py: Python<'_>) -> PyResult<Py<PyString>> {
        let base = slf.borrow().into_super();
        Ok(base
            .scope
            .bind(py)
            .get_item(intern!(py, "method"))?
            .ok_or_else(|| PyKeyError::new_err("method"))?
            .cast_into::<PyString>()?
            .unbind())
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

#[pyfunction]
pub fn parse_urlencoded_form(body: &[u8]) -> Vec<(String, String)> {
    form_urlencoded::parse(body)
        .map(|(k, v)| (k.into_owned(), v.into_owned()))
        .collect()
}

fn percent_decode(value: &str) -> String {
    percent_encoding::percent_decode_str(value)
        .decode_utf8()
        .map_or_else(|_| value.to_owned(), |decoded| decoded.into_owned())
}

fn parse_cookie_header(header: &str) -> impl Iterator<Item = (String, String)> + '_ {
    header.split(';').filter_map(|chunk| {
        let (name, value) = chunk.split_once('=').unwrap_or(("", chunk));
        let (name, value) = (name.trim(), value.trim());
        if name.is_empty() && value.is_empty() {
            return None;
        }
        Some((percent_decode(name), percent_decode(value)))
    })
}

fn scope_type_in(scope: &Bound<'_, PyDict>, allowed: &[&str]) -> PyResult<bool> {
    let scope_type = scope
        .get_item(intern!(scope.py(), "type"))?
        .ok_or_else(|| PyKeyError::new_err("type"))?;
    Ok(allowed.contains(&scope_type.cast::<PyString>()?.to_str()?))
}

fn channel_or_placeholder(py: Python<'_>, given: Option<Py<PyAny>>, placeholder: &str) -> PyResult<Py<PyAny>> {
    match given {
        Some(channel) => Ok(channel),
        None => Ok(py.import("speedy.requests")?.getattr(placeholder)?.unbind()),
    }
}
