use std::fs::File;
use std::hash::{DefaultHasher, Hash, Hasher};
use std::io::{Cursor, Read, Seek, SeekFrom, Write};
use std::sync::Arc;

use indexmap::IndexMap;
use pyo3::exceptions::{PyAttributeError, PyIndexError, PyKeyError, PyOSError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{IntoPyDict, PyBool, PyBytes, PyDict, PyList, PyString, PyTuple, PyType};
use uriparse::Authority;
use url::form_urlencoded;

type Key = Arc<str>;

fn state_exception(py: Python<'_>, message: String) -> PyErr {
    match py
        .import("speedy.exceptions")
        .and_then(|m| m.getattr("StateException"))
        .and_then(|cls| cls.call1((message.clone(),)))
    {
        Ok(exc) => PyErr::from_value(exc),
        Err(_) => PyValueError::new_err(message),
    }
}

fn deepcopy_pydict<'py>(py: Python<'py>, dict: &Bound<'py, PyDict>) -> PyResult<Bound<'py, PyDict>> {
    let deepcopy = py.import("copy")?.getattr("deepcopy")?;
    deepcopy.call1((dict,))?.cast_into::<PyDict>().map_err(Into::into)
}

fn index_map_from_pydict(dict: &Bound<'_, PyDict>) -> PyResult<IndexMap<Key, Py<PyAny>>> {
    dict.iter()
        .map(|(key, value)| Ok((Key::from(key.extract::<String>()?), value.unbind())))
        .collect()
}

fn pydict_from_index_map<'py>(py: Python<'py>, map: &IndexMap<Key, Py<PyAny>>) -> Bound<'py, PyDict> {
    let dict = PyDict::new(py);
    map.iter().for_each(|(k, v)| {
        dict.set_item(k.as_ref(), v.clone_ref(py))
            .expect("set_item on a fresh dict cannot fail");
    });
    dict
}

fn coerce_state(py: Python<'_>, state: &Bound<'_, PyAny>, copy_data: bool) -> PyResult<IndexMap<Key, Py<PyAny>>> {
    if let Ok(existing) = state.extract::<PyRef<'_, ImmutableState>>() {
        return if copy_data {
            let deep = deepcopy_pydict(py, &pydict_from_index_map(py, &existing.data))?;
            index_map_from_pydict(&deep)
        } else {
            Ok(existing
                .data
                .iter()
                .map(|(k, v)| (k.clone(), v.clone_ref(py)))
                .collect())
        };
    }

    let raw_dict: Bound<'_, PyDict> = if let Ok(d) = state.cast::<PyDict>() {
        d.clone()
    } else {
        let abc = py.import("collections.abc")?;
        let is_mapping_or_iterable =
            state.is_instance(&abc.getattr("Mapping")?)? || state.is_instance(&abc.getattr("Iterable")?)?;
        if !is_mapping_or_iterable {
            return Err(state_exception(py, format!("Invalid state type: {}", state.get_type())));
        }
        py.get_type::<PyDict>().call1((state,))?.cast_into::<PyDict>()?
    };

    let final_dict = if copy_data {
        deepcopy_pydict(py, &raw_dict)?
    } else {
        raw_dict
    };
    index_map_from_pydict(&final_dict)
}

#[pyclass(mapping, subclass, module = "speedy.datastructures")]
pub struct ImmutableState {
    data: IndexMap<Key, Py<PyAny>>,
}

#[pymethods]
impl ImmutableState {
    #[new]
    #[pyo3(signature = (state, copy_data=true))]
    fn new(py: Python<'_>, state: &Bound<'_, PyAny>, copy_data: bool) -> PyResult<Self> {
        Ok(ImmutableState {
            data: coerce_state(py, state, copy_data)?,
        })
    }

    fn __getitem__(&self, py: Python<'_>, key: String) -> PyResult<Py<PyAny>> {
        self.data
            .get(key.as_str())
            .map(|v| v.clone_ref(py))
            .ok_or_else(|| PyKeyError::new_err(key))
    }

    fn __getattr__(&self, py: Python<'_>, key: String) -> PyResult<Py<PyAny>> {
        self.data
            .get(key.as_str())
            .map(|v| v.clone_ref(py))
            .ok_or_else(|| PyAttributeError::new_err(format!("Attribute `{key}` not found")))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let keys: Vec<&str> = self.data.keys().map(|k| k.as_ref()).collect();
        let list = PyList::new(py, keys)?;
        Ok(list.call_method0("__iter__")?.unbind())
    }

    fn __len__(&self) -> usize {
        self.data.len()
    }

    fn __repr__(slf: &Bound<'_, Self>) -> PyResult<String> {
        let py = slf.py();
        let class_name: String = slf.get_type().getattr("__name__")?.extract()?;
        let dict_repr = pydict_from_index_map(py, &slf.borrow().data).repr()?;
        Ok(format!("{class_name}({dict_repr})"))
    }

    fn __eq__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        let b: Bound<'_, PyDict> = if let Ok(other_state) = other.extract::<PyRef<'_, ImmutableState>>() {
            pydict_from_index_map(py, &other_state.data)
        } else {
            let mapping_abc = py.import("collections.abc")?.getattr("Mapping")?;
            if !other.is_instance(&mapping_abc)? {
                return Ok(PyBool::new(py, false).to_owned().into_any().unbind());
            }
            py.get_type::<PyDict>().call1((other,))?.cast_into::<PyDict>()?
        };

        let a = pydict_from_index_map(py, &self.data);
        let equal = a.eq(&b)?;
        Ok(PyBool::new(py, equal).to_owned().into_any().unbind())
    }

    fn __copy__(slf: &Bound<'_, Self>) -> PyResult<Py<PyAny>> {
        let py = slf.py();
        let data_dict = pydict_from_index_map(py, &slf.borrow().data);
        let cls = slf.get_type();
        Ok(cls.call1((data_dict, false))?.unbind())
    }

    #[getter(_data)]
    fn get_data(&self, py: Python<'_>) -> Py<PyDict> {
        pydict_from_index_map(py, &self.data).unbind()
    }

    fn keys(&self, py: Python<'_>) -> PyResult<Py<PyList>> {
        let keys: Vec<&str> = self.data.keys().map(|k| k.as_ref()).collect();
        Ok(PyList::new(py, keys)?.unbind())
    }

    fn as_dict(&self, py: Python<'_>) -> Py<PyDict> {
        pydict_from_index_map(py, &self.data).unbind()
    }

    fn mutable_copy(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let deep = deepcopy_pydict(py, &pydict_from_index_map(py, &self.data))?;
        let data = index_map_from_pydict(&deep)?;
        let initializer = PyClassInitializer::from(ImmutableState { data }).add_subclass(State {});
        Ok(Py::new(py, initializer)?.into_any())
    }
}

#[pyclass(mapping, extends = ImmutableState, subclass, module = "speedy.datastructures")]
pub struct State {}

#[pymethods]
impl State {
    #[new]
    #[pyo3(signature = (state=None, copy_data=true))]
    fn new(py: Python<'_>, state: Option<&Bound<'_, PyAny>>, copy_data: bool) -> PyResult<PyClassInitializer<State>> {
        let empty_holder;
        let state_ref: &Bound<'_, PyAny> = match state {
            Some(s) => s,
            None => {
                empty_holder = PyDict::new(py).into_any();
                &empty_holder
            }
        };
        let data = coerce_state(py, state_ref, copy_data)?;
        Ok(PyClassInitializer::from(ImmutableState { data }).add_subclass(State {}))
    }

    fn __setitem__(self_: PyRefMut<'_, Self>, key: String, value: Py<PyAny>) {
        let mut base = self_.into_super();
        base.data.insert(Key::from(key), value);
    }

    fn __delitem__(self_: PyRefMut<'_, Self>, key: String) -> PyResult<()> {
        let mut base = self_.into_super();
        base.data
            .shift_remove(key.as_str())
            .map(|_| ())
            .ok_or_else(|| PyKeyError::new_err(key))
    }

    fn __setattr__(self_: PyRefMut<'_, Self>, key: String, value: Py<PyAny>) -> PyResult<()> {
        if key == "_data" || key == "_proxy" {
            return Err(PyAttributeError::new_err(format!(
                "Cannot set reserved attribute '{key}' via attribute notation. \
                 Use object.__setattr__() if you intend to modify internal state.",
            )));
        }
        let mut base = self_.into_super();
        base.data.insert(Key::from(key), value);
        Ok(())
    }

    fn __delattr__(self_: PyRefMut<'_, Self>, key: String) -> PyResult<()> {
        let mut base = self_.into_super();
        base.data
            .shift_remove(key.as_str())
            .map(|_| ())
            .ok_or_else(|| PyAttributeError::new_err(format!("Attribute {key} not found")))
    }

    fn copy(slf: &Bound<'_, Self>) -> PyResult<Py<PyAny>> {
        let py = slf.py();
        let data_dict = pydict_from_index_map(py, &slf.borrow().into_super().data);
        let cls = slf.get_type();
        Ok(cls.call1((data_dict, false))?.unbind())
    }

    fn immutable_copy(self_: PyRef<'_, Self>, py: Python<'_>) -> PyResult<Py<ImmutableState>> {
        let base = self_.into_super();
        let deep = deepcopy_pydict(py, &pydict_from_index_map(py, &base.data))?;
        let data = index_map_from_pydict(&deep)?;
        Py::new(py, ImmutableState { data })
    }
}

#[pyclass(module = "speedy.datastructures", frozen, skip_from_py_object)]
#[derive(Clone, PartialEq, Eq, Hash)]
pub struct Address {
    #[pyo3(get)]
    host: String,
    #[pyo3(get)]
    port: u16,
}

impl Address {
    fn as_tuple<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyTuple>> {
        PyTuple::new(
            py,
            [
                self.host.as_str().into_pyobject(py)?.into_any(),
                self.port.into_pyobject(py)?.into_any(),
            ],
        )
    }

    fn rich_compare(&self, py: Python<'_>, other: &Bound<'_, PyAny>, op: &str) -> PyResult<Py<PyAny>> {
        let self_tuple = self.as_tuple(py)?;
        let other_obj = if let Ok(other_addr) = other.extract::<PyRef<'_, Address>>() {
            other_addr.as_tuple(py)?.into_any()
        } else {
            other.clone()
        };
        Ok(self_tuple.as_any().call_method1(op, (other_obj,))?.unbind())
    }
}

#[pymethods]
impl Address {
    #[new]
    fn new(host: String, port: u16) -> Self {
        Self { host, port }
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let host_repr = PyString::new(py, &self.host).repr()?;
        Ok(format!("Address(host={host_repr}, port={})", self.port))
    }

    fn __len__(&self, py: Python<'_>) -> PyResult<usize> {
        Ok(self.as_tuple(py)?.len())
    }

    fn __getitem__(&self, py: Python<'_>, index: isize) -> PyResult<Py<PyAny>> {
        Ok(self.as_tuple(py)?.as_any().get_item(index)?.unbind())
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        Ok(self.as_tuple(py)?.as_any().call_method0("__iter__")?.unbind())
    }

    fn __eq__(&self, other: &Bound<'_, PyAny>) -> bool {
        if let Ok(other_addr) = other.extract::<PyRef<'_, Address>>() {
            return *self == *other_addr;
        }

        if let Ok((host, port)) = other.extract::<(String, u16)>() {
            return self.host == host && self.port == port;
        }

        false
    }

    fn __lt__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        self.rich_compare(py, other, "__lt__")
    }

    fn __le__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        self.rich_compare(py, other, "__le__")
    }

    fn __gt__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        self.rich_compare(py, other, "__gt__")
    }

    fn __ge__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        self.rich_compare(py, other, "__ge__")
    }

    fn __hash__(&self) -> u64 {
        let mut hasher = DefaultHasher::new();
        self.hash(&mut hasher);
        hasher.finish()
    }

    #[pyo3(signature = (**kwargs))]
    fn __replace__(&self, py: Python<'_>, kwargs: Option<Bound<'_, PyDict>>) -> PyResult<Py<PyAny>> {
        self._replace(py, kwargs)
    }

    fn count(&self, py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<usize> {
        self.as_tuple(py)?.as_any().call_method1("count", (value,))?.extract()
    }

    #[pyo3(signature = (value, start=0, stop=isize::MAX))]
    fn index(&self, py: Python<'_>, value: &Bound<'_, PyAny>, start: isize, stop: isize) -> PyResult<usize> {
        self.as_tuple(py)?
            .as_any()
            .call_method1("index", (value, start, stop))?
            .extract()
    }

    #[classattr]
    fn _fields() -> (&'static str, &'static str) {
        ("host", "port")
    }

    #[classattr]
    fn _field_defaults(py: Python<'_>) -> Py<PyDict> {
        PyDict::new(py).unbind()
    }

    fn _asdict(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let dict = PyDict::new(py);
        dict.set_item("host", &self.host)?;
        dict.set_item("port", self.port)?;
        Ok(dict.unbind())
    }

    #[classmethod]
    fn _make(cls: &Bound<'_, PyType>, iterable: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        let py = cls.py();
        let args = py.get_type::<PyTuple>().call1((iterable,))?.cast_into::<PyTuple>()?;
        Ok(cls.call1(args)?.unbind())
    }

    #[pyo3(signature = (**kwargs))]
    fn _replace(&self, py: Python<'_>, kwargs: Option<Bound<'_, PyDict>>) -> PyResult<Py<PyAny>> {
        let (host, port, unexpected) = match kwargs {
            Some(kwargs) => kwargs.iter().try_fold(
                (self.host.clone(), self.port, Vec::<String>::new()),
                |(host, port, mut unexpected), (key, value)| -> PyResult<_> {
                    let key_str: String = key.extract()?;
                    match key_str.as_str() {
                        "host" => Ok((value.extract()?, port, unexpected)),
                        "port" => Ok((host, value.extract()?, unexpected)),
                        _ => {
                            unexpected.push(key_str);
                            Ok((host, port, unexpected))
                        }
                    }
                },
            )?,
            None => (self.host.clone(), self.port, Vec::new()),
        };

        if !unexpected.is_empty() {
            let joined = unexpected
                .iter()
                .map(|k| format!("'{k}'"))
                .collect::<Vec<_>>()
                .join(", ");
            return Err(PyTypeError::new_err(format!("Got unexpected field names: [{joined}]")));
        }

        Ok(Py::new(py, Address { host, port })?.into_any())
    }
}

fn split_url(raw: &str) -> URL {
    let mut rest = raw;

    let fragment = if let Some(idx) = rest.find("#") {
        let fragment = rest[idx + 1..].to_string();
        rest = &rest[..idx];
        fragment
    } else {
        String::new()
    };

    let query = if let Some(idx) = rest.find("?") {
        let query = rest[idx + 1..].to_string();
        rest = &rest[..idx];
        query
    } else {
        String::new()
    };

    let (scheme, after_scheme) = split_scheme(rest);
    rest = after_scheme;

    let netloc = if let Some(stripped) = rest.strip_prefix("//") {
        let end = stripped.find("/").unwrap_or(stripped.len());
        let netloc = stripped[..end].to_string();
        rest = &stripped[end..];
        netloc
    } else {
        String::new()
    };

    URL {
        scheme,
        netloc,
        path: rest.to_string(),
        query,
        fragment,
    }
}

fn split_scheme(scheme: &str) -> (String, &str) {
    if let Some(colon_idx) = scheme.find(":") {
        let candidate = &scheme[..colon_idx];
        if !candidate.is_empty() && candidate.chars().enumerate().all(|(i, c)| is_scheme_char(c, i == 0)) {
            return (candidate.to_lowercase(), &scheme[colon_idx + 1..]);
        }
    }
    (String::new(), scheme)
}

fn is_scheme_char(c: char, first: bool) -> bool {
    if first {
        c.is_ascii_alphabetic()
    } else {
        c.is_ascii_alphanumeric() || c == '+' || c == '-' || c == '.'
    }
}

fn parse_authority(netloc: &str) -> Option<Authority<'static>> {
    if netloc.is_empty() {
        return None;
    }
    Authority::try_from(netloc).ok().map(|auth| auth.into_owned())
}

fn unsplit_url(scheme: &str, netloc: &str, path: &str, query: &str, fragment: &str) -> String {
    let mut result = String::new();
    let has_authority_prefix = !netloc.is_empty() || !scheme.is_empty();
    if !scheme.is_empty() {
        result.push_str(scheme);
        result.push(':');
    }
    if has_authority_prefix {
        result.push_str("//");
        result.push_str(netloc);
        if !path.is_empty() && !path.starts_with('/') {
            result.push('/');
        }
    }
    result.push_str(path);
    if !query.is_empty() {
        result.push('?');
        result.push_str(query);
    }
    if !fragment.is_empty() {
        result.push('#');
        result.push_str(fragment);
    }
    result
}

fn build_netloc(
    current_netloc: &str,
    hostname: Option<String>,
    port: Option<Option<u16>>,
    username: Option<Option<String>>,
    password: Option<Option<String>>,
) -> String {
    let host = hostname.unwrap_or_else(|| host_for_netloc_rebuild(current_netloc));

    let port_resolved = match port {
        Some(explicit) => explicit,
        None => port_from_netloc(current_netloc),
    };
    let username_resolved = match username {
        Some(explicit) => explicit,
        None => username_from_netloc(current_netloc),
    };
    let password_resolved = match password {
        Some(explicit) => explicit,
        None => password_from_netloc(current_netloc),
    };

    let mut netloc = host;
    if let Some(p) = port_resolved {
        netloc.push(':');
        netloc.push_str(&p.to_string());
    }
    if let Some(user) = username_resolved {
        let mut userpass = user;
        if let Some(pass) = password_resolved {
            userpass.push(':');
            userpass.push_str(&pass);
        }
        netloc = format!("{userpass}@{netloc}");
    }
    netloc
}

fn host_for_netloc_rebuild(netloc: &str) -> String {
    let after_at = netloc.rsplit_once("@").map(|(_, h)| h).unwrap_or(netloc);
    if after_at.ends_with("]") {
        after_at.to_string()
    } else {
        after_at
            .rsplit_once(":")
            .map(|(h, _)| h)
            .unwrap_or(after_at)
            .to_string()
    }
}

fn port_from_netloc(netloc: &str) -> Option<u16> {
    parse_authority(netloc)?.port()
}

fn username_from_netloc(netloc: &str) -> Option<String> {
    parse_authority(netloc)?.username().map(|u| u.to_string())
}

fn password_from_netloc(netloc: &str) -> Option<String> {
    parse_authority(netloc)?.password().map(|p| p.to_string())
}

fn encode_pairs(pairs: &[(String, String)]) -> String {
    form_urlencoded::Serializer::new(String::new())
        .extend_pairs(pairs)
        .finish()
}

fn extract_query_pairs(url: &URL, kwargs: &Bound<'_, PyDict>) -> PyResult<Vec<(String, String)>> {
    let initial: Vec<(String, String)> = form_urlencoded::parse(url.query.as_bytes())
        .map(|(k, v)| (k.into_owned(), v.into_owned()))
        .collect();
    kwargs
        .iter()
        .try_fold(initial, |mut pairs, (key, value)| -> PyResult<_> {
            let key_str: String = key.extract()?;
            let value_str: String = value.str()?.extract()?;
            pairs.retain(|(k, _)| k != &key_str);
            pairs.push((key_str, value_str));
            Ok(pairs)
        })
}

#[pyclass(module = "speedy.datastructures", skip_from_py_object)]
#[derive(Clone)]
pub struct URL {
    scheme: String,
    netloc: String,
    path: String,
    query: String,
    fragment: String,
}

impl URL {
    fn with_password(&self, new_password: &str) -> URL {
        let netloc = build_netloc(&self.netloc, None, None, None, Some(Some(new_password.to_string())));
        URL {
            scheme: self.scheme.clone(),
            netloc,
            path: self.path.clone(),
            query: self.query.clone(),
            fragment: self.fragment.clone(),
        }
    }
}

#[pymethods]
impl URL {
    #[new]
    #[pyo3(signature = (url=None))]
    fn new(url: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        let raw: String = match url {
            None => String::new(),
            Some(obj) => obj.str()?.extract::<String>()?,
        };
        let url = split_url(&raw);
        Ok(url)
    }

    fn __eq__(&self, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        if let Ok(other_url) = other.extract::<PyRef<'_, URL>>() {
            return Ok(self.__str__() == other_url.__str__());
        }
        if let Ok(other_str) = other.extract::<String>() {
            return Ok(self.__str__() == other_str);
        }
        Ok(false)
    }

    fn __str__(&self) -> String {
        unsplit_url(&self.scheme, &self.netloc, &self.path, &self.query, &self.fragment)
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let displayed = if self.password().is_some() {
            self.with_password("**********").__str__()
        } else {
            self.__str__()
        };
        let repr = PyString::new(py, &displayed).repr()?;
        Ok(format!("URL({repr})"))
    }

    #[getter]
    fn scheme(&self) -> &str {
        &self.scheme
    }

    #[getter]
    fn hostname(&self) -> Option<String> {
        let authority = parse_authority(&self.netloc)?;
        let host = authority.host().to_string();
        let stripped = host
            .strip_prefix("[")
            .and_then(|h| h.strip_suffix("]"))
            .unwrap_or(&host);
        if stripped.is_empty() {
            None
        } else {
            Some(stripped.to_lowercase())
        }
    }

    #[getter]
    fn port(&self) -> Option<u16> {
        port_from_netloc(&self.netloc)
    }

    #[getter]
    fn netloc(&self) -> &str {
        &self.netloc
    }

    #[getter]
    fn username(&self) -> Option<String> {
        username_from_netloc(&self.netloc)
    }

    #[getter]
    fn password(&self) -> Option<String> {
        password_from_netloc(&self.netloc)
    }

    #[getter]
    fn path(&self) -> &str {
        &self.path
    }

    #[getter]
    fn query(&self) -> &str {
        &self.query
    }

    #[getter]
    fn fragment(&self) -> &str {
        &self.fragment
    }

    #[getter]
    fn is_secure(&self) -> bool {
        self.scheme == "https" || self.scheme == "wss"
    }

    #[pyo3(signature = (**kwargs))]
    fn replace(&self, kwargs: Option<Bound<'_, PyDict>>) -> PyResult<URL> {
        let kwargs = match kwargs {
            Some(k) => k,
            None => return Ok(self.clone()),
        };

        let get_str = |name: &str| -> PyResult<Option<String>> {
            kwargs.get_item(name)?.map(|v| v.extract::<String>()).transpose()
        };
        let get_opt_str = |name: &str| -> PyResult<Option<Option<String>>> {
            match kwargs.get_item(name)? {
                None => Ok(None),
                Some(v) if v.is_none() => Ok(Some(None)),
                Some(v) => Ok(Some(Some(v.extract::<String>()?))),
            }
        };
        let get_opt_port = |name: &str| -> PyResult<Option<Option<u16>>> {
            match kwargs.get_item(name)? {
                None => Ok(None),
                Some(v) if v.is_none() => Ok(Some(None)),
                Some(v) => Ok(Some(Some(v.extract::<u16>()?))),
            }
        };

        let hostname = get_str("hostname")?;
        let port = get_opt_port("port")?;
        let username = get_opt_str("username")?;
        let password = get_opt_str("password")?;

        let touches_netloc_parts = hostname.is_some() || port.is_some() || username.is_some() || password.is_some();

        let new_netloc = if touches_netloc_parts {
            build_netloc(&self.netloc, hostname, port, username, password)
        } else {
            get_str("netloc")?.unwrap_or_else(|| self.netloc.clone())
        };

        Ok(URL {
            scheme: get_str("scheme")?.unwrap_or_else(|| self.scheme.clone()),
            netloc: new_netloc,
            path: get_str("path")?.unwrap_or_else(|| self.path.clone()),
            query: get_str("query")?.unwrap_or_else(|| self.query.clone()),
            fragment: get_str("fragment")?.unwrap_or_else(|| self.fragment.clone()),
        })
    }

    #[pyo3(signature = (**kwargs))]
    fn replace_query_params(&self, kwargs: Option<Bound<'_, PyDict>>) -> PyResult<URL> {
        let mut pairs: Vec<(String, String)> = Vec::new();
        if let Some(kwargs) = kwargs {
            for (key, value) in kwargs.iter() {
                let key_str: String = key.extract()?;
                let value_str: String = value.str()?.extract()?;
                pairs.push((key_str, value_str));
            }
        }
        Ok(URL {
            scheme: self.scheme.clone(),
            netloc: self.netloc.clone(),
            path: self.path.clone(),
            query: encode_pairs(&pairs),
            fragment: self.fragment.clone(),
        })
    }

    #[pyo3(signature = (**kwargs))]
    fn include_query_params(&self, kwargs: Option<Bound<'_, PyDict>>) -> PyResult<URL> {
        let pairs = match kwargs {
            Some(kwargs) => extract_query_pairs(self, &kwargs)?,
            None => form_urlencoded::parse(self.query.as_bytes())
                .map(|(k, v)| (k.into_owned(), v.into_owned()))
                .collect(),
        };
        Ok(URL {
            scheme: self.scheme.clone(),
            netloc: self.netloc.clone(),
            path: self.path.clone(),
            query: encode_pairs(&pairs),
            fragment: self.fragment.clone(),
        })
    }

    fn remove_query_params(&self, keys: &Bound<'_, PyAny>) -> PyResult<URL> {
        let keys_to_remove: Vec<String> = if let Ok(single) = keys.extract::<String>() {
            vec![single]
        } else {
            keys.try_iter()?
                .map(|item| item.and_then(|i| i.extract::<String>()))
                .collect::<PyResult<Vec<_>>>()?
        };

        let pairs: Vec<(String, String)> = form_urlencoded::parse(self.query.as_bytes())
            .map(|(k, v)| (k.into_owned(), v.into_owned()))
            .filter(|(k, _)| !keys_to_remove.contains(k))
            .collect();

        Ok(URL {
            scheme: self.scheme.clone(),
            netloc: self.netloc.clone(),
            path: self.path.clone(),
            query: encode_pairs(&pairs),
            fragment: self.fragment.clone(),
        })
    }
}

#[pyclass(module = "speedy.datastructures")]
pub struct URLPath {
    #[pyo3(get, set)]
    path: Py<PyAny>,
    #[pyo3(get, set)]
    base: Py<PyAny>,
}

impl URLPath {
    fn base_scheme_netloc_path(&self, py: Python<'_>) -> PyResult<URL> {
        let base = self.base.bind(py);
        if let Ok(url) = base.extract::<PyRef<'_, URL>>() {
            return Ok(url.to_owned());
        }
        let raw: String = base.str()?.extract()?;
        let url = split_url(&raw);
        Ok(url)
    }

    fn make_absolute_url(&self, py: Python<'_>) -> PyResult<String> {
        let url = self.base_scheme_netloc_path(py)?;
        let trimmed_base_path = url.path.trim_end_matches('/');
        let path_str: String = self.path.bind(py).str()?.extract()?;
        let combined_path = format!("{trimmed_base_path}{path_str}");
        Ok(unsplit_url(&url.scheme, &url.netloc, &combined_path, "", ""))
    }
}

#[pymethods]
impl URLPath {
    #[new]
    fn new(path: Py<PyAny>, base: Py<PyAny>) -> Self {
        URLPath { path, base }
    }

    fn __str__(&self, py: Python<'_>) -> PyResult<String> {
        self.make_absolute_url(py)
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let path_repr = self.path.bind(py).repr()?;
        let base_repr = self.base.bind(py).repr()?;
        Ok(format!("URLPath(path={path_repr}, base={base_repr})"))
    }
}

pub(crate) fn get_raw_from_inputs(
    headers: Option<&Bound<'_, PyAny>>,
    raw: Option<&Bound<'_, PyAny>>,
    scope: Option<&Bound<'_, PyDict>>,
) -> PyResult<Vec<(Vec<u8>, Vec<u8>)>> {
    if let Some(headers) = headers {
        if raw.is_some() {
            return Err(PyAttributeError::new_err("Cannot set both \"headers\" and \"raw\"."));
        }
        if scope.is_some() {
            return Err(PyAttributeError::new_err("Cannot set both \"headers\" and \"scope\"."));
        }
        headers
            .call_method0("items")?
            .try_iter()?
            .map(|item| {
                let (k, v): (String, String) = item?.extract()?;
                Ok((encode_latin1(&k.to_lowercase())?, encode_latin1(&v)?))
            })
            .collect()
    } else if let Some(raw) = raw {
        if scope.is_some() {
            return Err(PyAttributeError::new_err("Cannot set both \"raw\" and \"scope\"."));
        }
        raw.extract()
    } else if let Some(scope) = scope {
        let headers_list = scope
            .get_item("headers")?
            .ok_or_else(|| PyKeyError::new_err("headers"))?;
        headers_list.try_iter()?.map(|item| item?.extract()).collect()
    } else {
        Ok(Vec::new())
    }
}

pub(crate) fn encode_latin1(s: &str) -> PyResult<Vec<u8>> {
    s.chars()
        .map(|c| {
            let code = c as u32;
            if code > 0xFF {
                Err(PyValueError::new_err(format!(
                    "'latin-1' codec can't encode character '\\u{code:04x}'"
                )))
            } else {
                Ok(code as u8)
            }
        })
        .collect()
}

fn decode_latin1(bytes: &[u8]) -> String {
    bytes.iter().map(|&b| b as char).collect()
}

pub(crate) fn raw_to_pylist<'py>(py: Python<'py>, raw: &[(Vec<u8>, Vec<u8>)]) -> PyResult<Bound<'py, PyList>> {
    PyList::new(py, raw.iter().map(|(k, v)| (PyBytes::new(py, k), PyBytes::new(py, v))))
}

#[pyclass(mapping, subclass, module = "speedy.datastructures")]
pub struct Headers {
    pub(crate) raw: Vec<(Vec<u8>, Vec<u8>)>,
}

#[pymethods]
impl Headers {
    #[new]
    #[pyo3(signature = (headers=None, raw=None, scope=None))]
    fn new(
        headers: Option<&Bound<'_, PyAny>>,
        raw: Option<&Bound<'_, PyAny>>,
        scope: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Self> {
        Ok(Self {
            raw: get_raw_from_inputs(headers, raw, scope)?,
        })
    }

    fn __getitem__(&self, item: String) -> PyResult<String> {
        let header_key = encode_latin1(&item.to_lowercase())?;
        self.raw
            .iter()
            .find(|(k, _)| *k == header_key)
            .map(|(_, v)| decode_latin1(v))
            .ok_or_else(|| PyKeyError::new_err(item))
    }

    fn __contains__(&self, item: String) -> PyResult<bool> {
        let header_key = encode_latin1(&item.to_lowercase())?;
        Ok(self.raw.iter().any(|(k, _)| *k == header_key))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let keys: Vec<String> = self.raw.iter().map(|(k, _)| decode_latin1(k)).collect();
        let list = PyList::new(py, keys)?;
        Ok(list.call_method0("__iter__")?.unbind())
    }

    fn __len__(&self) -> usize {
        self.raw.len()
    }

    fn __eq__(&self, other: &Bound<'_, PyAny>) -> bool {
        let Ok(other_headers) = other.extract::<PyRef<'_, Headers>>() else {
            return false;
        };
        let mut a = self.raw.clone();
        let mut b = other_headers.raw.clone();
        a.sort();
        b.sort();
        a == b
    }

    fn __repr__(slf: &Bound<'_, Self>) -> PyResult<String> {
        let py = slf.py();
        let class_name: String = slf.get_type().getattr("__name__")?.extract()?;
        let this = slf.borrow();

        let as_dict = PyDict::new(py);
        this.raw
            .iter()
            .try_for_each(|(k, v)| as_dict.set_item(decode_latin1(k), decode_latin1(v)))?;

        if as_dict.len() == this.raw.len() {
            let dict_repr = as_dict.repr()?;
            Ok(format!("{class_name}({dict_repr})"))
        } else {
            let raw_repr = raw_to_pylist(py, &this.raw)?.repr()?;
            Ok(format!("{class_name}(raw={raw_repr})"))
        }
    }

    #[getter]
    fn raw(&self, py: Python<'_>) -> PyResult<Py<PyList>> {
        Ok(raw_to_pylist(py, &self.raw)?.unbind())
    }

    #[classmethod]
    fn from_scope(cls: &Bound<'_, PyType>, scope: &Bound<'_, PyDict>) -> PyResult<Py<PyAny>> {
        let kwargs = PyDict::new(cls.py());
        kwargs.set_item("scope", scope)?;
        Ok(cls.call((), Some(&kwargs))?.unbind())
    }

    fn keys(&self, py: Python<'_>) -> PyResult<Py<PyList>> {
        let keys: Vec<String> = self.raw.iter().map(|(k, _)| decode_latin1(k)).collect();
        Ok(PyList::new(py, keys)?.unbind())
    }

    fn values(&self, py: Python<'_>) -> PyResult<Py<PyList>> {
        let values: Vec<String> = self.raw.iter().map(|(_, v)| decode_latin1(v)).collect();
        Ok(PyList::new(py, values)?.unbind())
    }

    fn items(&self, py: Python<'_>) -> PyResult<Py<PyList>> {
        let items: Vec<(String, String)> = self
            .raw
            .iter()
            .map(|(k, v)| (decode_latin1(k), decode_latin1(v)))
            .collect();
        Ok(PyList::new(py, items)?.unbind())
    }

    fn getlist(&self, key: String) -> PyResult<Vec<String>> {
        let header_key = encode_latin1(&key.to_lowercase())?;
        Ok(self
            .raw
            .iter()
            .filter(|(k, _)| *k == header_key)
            .map(|(_, v)| decode_latin1(v))
            .collect())
    }

    #[pyo3(signature = (key, default=None))]
    fn get(&self, key: String, default: Option<Py<PyAny>>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let header_key = encode_latin1(&key.to_lowercase())?;
        match self.raw.iter().find(|(k, _)| *k == header_key) {
            Some((_, v)) => Ok(decode_latin1(v).into_pyobject(py)?.into_any().unbind()),
            None => Ok(default.unwrap_or_else(|| py.None())),
        }
    }

    fn mutablecopy(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let initializer = PyClassInitializer::from(Headers { raw: self.raw.clone() }).add_subclass(MutableHeaders {});
        Ok(Py::new(py, initializer)?.into_any())
    }
}

fn set_header(raw: &mut Vec<(Vec<u8>, Vec<u8>)>, key: &str, value: &str) -> PyResult<()> {
    let key_bytes = encode_latin1(&key.to_lowercase())?;
    let value_bytes = encode_latin1(value)?;

    let mut matched = raw
        .iter()
        .enumerate()
        .filter(|(_, (k, _))| *k == key_bytes)
        .map(|(index, _)| index);

    let updated_index = matched.next();
    let removed_indexes: Vec<usize> = matched.collect();

    match updated_index {
        Some(idx) => raw[idx] = (key_bytes, value_bytes),
        None => raw.push((key_bytes, value_bytes)),
    }

    removed_indexes.into_iter().rev().for_each(|idx| {
        raw.remove(idx);
    });
    Ok(())
}

fn is_mapping_instance(py: Python<'_>, obj: &Bound<'_, PyAny>) -> PyResult<bool> {
    let mapping_abc = py.import("collections.abc")?.getattr("Mapping")?;
    obj.is_instance(&mapping_abc)
}

fn apply_update(raw: &mut Vec<(Vec<u8>, Vec<u8>)>, other: &Bound<'_, PyAny>) -> PyResult<()> {
    other.call_method0("items")?.try_iter()?.try_for_each(|item| {
        let (k, v): (String, String) = item?.extract()?;
        set_header(raw, &k, &v)
    })
}

#[pyclass(mapping, extends = Headers, subclass, module = "speedy.datastructures")]
pub struct MutableHeaders {}

#[pymethods]
impl MutableHeaders {
    #[new]
    #[pyo3(signature = (headers=None, raw=None, scope=None))]
    fn new(
        headers: Option<&Bound<'_, PyAny>>,
        raw: Option<&Bound<'_, PyAny>>,
        scope: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<PyClassInitializer<MutableHeaders>> {
        let raw_vec = get_raw_from_inputs(headers, raw, scope)?;
        Ok(PyClassInitializer::from(Headers { raw: raw_vec }).add_subclass(MutableHeaders {}))
    }

    fn __setitem__(slf: PyRefMut<'_, Self>, key: String, value: String) -> PyResult<()> {
        let mut base = slf.into_super();
        set_header(&mut base.raw, &key, &value)
    }

    fn __delitem__(slf: PyRefMut<'_, Self>, key: String) -> PyResult<()> {
        let key_bytes = encode_latin1(&key.to_lowercase())?;
        let mut base = slf.into_super();
        base.raw.retain(|(k, _)| *k != key_bytes);
        Ok(())
    }

    fn __ior__(slf: &Bound<'_, Self>, other: &Bound<'_, PyAny>) -> PyResult<()> {
        let py = slf.py();
        if !is_mapping_instance(py, other)? {
            let type_name: String = other.get_type().getattr("__name__")?.extract()?;
            return Err(PyTypeError::new_err(format!("Expected a mapping but got {type_name}")));
        }
        let self_mut = slf.borrow_mut();
        let mut base = self_mut.into_super();
        apply_update(&mut base.raw, other)
    }

    fn __or__(slf: &Bound<'_, Self>, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        let py = slf.py();
        if !is_mapping_instance(py, other)? {
            let type_name: String = other.get_type().getattr("__name__")?.extract()?;
            return Err(PyTypeError::new_err(format!("Expected a mapping but got {type_name}")));
        }
        let mut new_raw = slf.borrow().into_super().raw.clone();
        apply_update(&mut new_raw, other)?;
        let initializer = PyClassInitializer::from(Headers { raw: new_raw }).add_subclass(MutableHeaders {});
        Ok(Py::new(py, initializer)?.into_any())
    }

    #[getter]
    fn raw(slf: &Bound<'_, Self>, py: Python<'_>) -> PyResult<Py<PyList>> {
        let base = slf.borrow().into_super();
        Ok(raw_to_pylist(py, &base.raw)?.unbind())
    }

    fn update(self_: PyRefMut<'_, Self>, other: &Bound<'_, PyAny>) -> PyResult<()> {
        let mut base = self_.into_super();
        apply_update(&mut base.raw, other)
    }

    fn append(self_: PyRefMut<'_, Self>, key: String, value: String) -> PyResult<()> {
        let key_bytes = encode_latin1(&key.to_lowercase())?;
        let value_bytes = encode_latin1(&value)?;
        let mut base = self_.into_super();
        base.raw.push((key_bytes, value_bytes));
        Ok(())
    }

    fn setdefault(self_: PyRefMut<'_, Self>, key: String, value: String) -> PyResult<String> {
        let key_bytes = encode_latin1(&key.to_lowercase())?;
        let mut base = self_.into_super();
        if let Some((_, v)) = base.raw.iter().find(|(k, _)| *k == key_bytes) {
            return Ok(decode_latin1(v));
        }
        let value_bytes = encode_latin1(&value)?;
        base.raw.push((key_bytes, value_bytes));
        Ok(value)
    }

    fn add_vary_header(self_: PyRefMut<'_, Self>, vary: String) -> PyResult<()> {
        let mut base = self_.into_super();
        let key_bytes = encode_latin1("vary")?;
        let existing = base
            .raw
            .iter()
            .find(|(k, _)| *k == key_bytes)
            .map(|(_, v)| decode_latin1(v));
        let new_value = match existing {
            Some(existing_val) => format!("{existing_val}, {vary}"),
            None => vary,
        };
        set_header(&mut base.raw, "vary", &new_value)
    }
}

fn dict_from_stack(py: Python<'_>, stack: &[(Py<PyAny>, Py<PyAny>)]) -> PyResult<Py<PyDict>> {
    stack
        .iter()
        .map(|(k, v)| (k.bind(py), v.bind(py)))
        .into_py_dict(py)
        .map(Bound::unbind)
}

fn check_args_len(len: usize) -> PyResult<()> {
    if len >= 2 {
        return Err(PyAttributeError::new_err("Too many arguments."));
    }

    Ok(())
}

fn build_items(
    arg0: Option<&Bound<'_, PyAny>>,
    kwargs: Option<&Bound<'_, PyDict>>,
) -> PyResult<Vec<(Py<PyAny>, Py<PyAny>)>> {
    let base = arg0.map_or_else(|| Ok(Vec::new()), extract_pairs)?;
    Ok(base
        .into_iter()
        .chain(kwargs.into_iter().flatten().map(|(k, v)| (k.unbind(), v.unbind())))
        .collect())
}

fn extract_pairs(value: &Bound<'_, PyAny>) -> PyResult<Vec<(Py<PyAny>, Py<PyAny>)>> {
    if !value.is_truthy()? {
        return Ok(Vec::new());
    }
    if value.hasattr("multi_items")? {
        let items = value.call_method0("multi_items")?;
        return pairs_from_iterable(&items);
    }
    if value.hasattr("items")? {
        let items = value.call_method0("items")?;
        return pairs_from_iterable(&items);
    }
    pairs_from_iterable(value)
}

fn pairs_from_iterable(value: &Bound<'_, PyAny>) -> PyResult<Vec<(Py<PyAny>, Py<PyAny>)>> {
    value.try_iter()?.map(|item| pair_from_any(&item?)).collect()
}

fn pair_from_any(item: &Bound<'_, PyAny>) -> PyResult<(Py<PyAny>, Py<PyAny>)> {
    let mut iter = item.try_iter()?;
    let first = match iter.next() {
        Some(v) => v?,
        None => return Err(PyValueError::new_err("not enough values to unpack (expected 2, got 0)")),
    };
    let second = match iter.next() {
        Some(v) => v?,
        None => return Err(PyValueError::new_err("not enough values to unpack (expected 2, got 1)")),
    };
    if iter.next().is_some() {
        return Err(PyValueError::new_err("too many values to unpack (expected 2)"));
    }
    Ok((first.unbind(), second.unbind()))
}

fn stack_without_key(
    py: Python<'_>,
    stack: &[(Py<PyAny>, Py<PyAny>)],
    key: &Bound<'_, PyAny>,
) -> PyResult<Vec<(Py<PyAny>, Py<PyAny>)>> {
    stack
        .iter()
        .try_fold(Vec::with_capacity(stack.len()), |mut acc, (k, v)| -> PyResult<_> {
            if !k.bind(py).eq(key)? {
                acc.push((k.clone_ref(py), v.clone_ref(py)));
            }
            Ok(acc)
        })
}

fn stack_values_for_key(
    py: Python<'_>,
    stack: &[(Py<PyAny>, Py<PyAny>)],
    key: &Bound<'_, PyAny>,
) -> PyResult<Vec<Py<PyAny>>> {
    stack.iter().try_fold(Vec::new(), |mut acc, (k, v)| -> PyResult<_> {
        if k.bind(py).eq(key)? {
            acc.push(v.clone_ref(py));
        }
        Ok(acc)
    })
}

fn stack_to_pylist<'py>(py: Python<'py>, stack: &[(Py<PyAny>, Py<PyAny>)]) -> PyResult<Bound<'py, PyList>> {
    let items = stack
        .iter()
        .map(|(k, v)| PyTuple::new(py, [k.clone_ref(py), v.clone_ref(py)]).map(|t| t.into_any()))
        .collect::<PyResult<Vec<_>>>()?;
    PyList::new(py, items)
}

fn pyobj_to_vec(value: &Bound<'_, PyAny>) -> PyResult<Vec<Py<PyAny>>> {
    value.try_iter()?.map(|item| Ok(item?.unbind())).collect()
}

#[pyclass(mapping, subclass, module = "speedy.datastructures")]
pub struct ImmutableMultiDict {
    stack: Vec<(Py<PyAny>, Py<PyAny>)>,
    dict: Py<PyDict>,
}

impl ImmutableMultiDict {
    fn from_stack(py: Python<'_>, stack: Vec<(Py<PyAny>, Py<PyAny>)>) -> PyResult<Self> {
        let dict = dict_from_stack(py, &stack)?;
        Ok(Self { stack, dict })
    }
}

fn delitem_impl(base: &mut ImmutableMultiDict, py: Python<'_>, key: &Bound<'_, PyAny>) -> PyResult<()> {
    if !base.dict.bind(py).contains(key)? {
        return Err(PyKeyError::new_err(key.clone().unbind()));
    }
    base.dict.bind(py).del_item(key)?;
    base.stack = stack_without_key(py, &base.stack, key)?;
    Ok(())
}

#[pymethods]
impl ImmutableMultiDict {
    #[new]
    #[pyo3(signature = (*args, **kwargs))]
    fn new(py: Python<'_>, args: &Bound<'_, PyTuple>, kwargs: Option<&Bound<'_, PyDict>>) -> PyResult<Self> {
        check_args_len(args.len())?;
        let arg0 = if args.is_empty() { None } else { Some(args.get_item(0)?) };
        let items = build_items(arg0.as_ref(), kwargs)?;
        Self::from_stack(py, items)
    }

    fn __setitem__(&mut self, py: Python<'_>, key: Py<PyAny>, values: &Bound<'_, PyAny>) -> PyResult<()> {
        let values_vec = pyobj_to_vec(values)?;
        let last = values_vec
            .last()
            .ok_or_else(|| PyIndexError::new_err("list index out of range"))?
            .clone_ref(py);
        let key_bound = key.bind(py).clone();
        let mut new_stack = stack_without_key(py, &self.stack, &key_bound)?;
        new_stack.extend(values_vec.iter().map(|v| (key.clone_ref(py), v.clone_ref(py))));
        self.stack = new_stack;
        self.dict.bind(py).set_item(key, last)?;
        Ok(())
    }

    fn __getitem__(&self, py: Python<'_>, key: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        self.dict
            .bind(py)
            .get_item(key)?
            .map(|v| v.unbind())
            .ok_or_else(|| PyKeyError::new_err(key.clone().unbind()))
    }

    fn __delitem__(&mut self, py: Python<'_>, key: &Bound<'_, PyAny>) -> PyResult<()> {
        delitem_impl(self, py, key)
    }

    fn __contains__(&self, py: Python<'_>, key: &Bound<'_, PyAny>) -> PyResult<bool> {
        self.dict.bind(py).contains(key)
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        self.dict.bind(py).len()
    }

    fn __eq__(slf: &Bound<'_, Self>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        let py = slf.py();
        let self_type = slf.get_type();
        if !other.is_instance(&self_type)? {
            return Ok(false);
        }
        let other_ref = other.extract::<PyRef<'_, ImmutableMultiDict>>()?;
        let self_list = stack_to_pylist(py, &slf.borrow().stack)?;
        let other_list = stack_to_pylist(py, &other_ref.stack)?;
        let builtins = py.import("builtins")?;
        let sorted_self = builtins.call_method1("sorted", (self_list,))?;
        let sorted_other = builtins.call_method1("sorted", (other_list,))?;
        sorted_self.eq(sorted_other)
    }

    fn __repr__(slf: &Bound<'_, Self>) -> PyResult<String> {
        let py = slf.py();
        let class_name: String = slf.get_type().getattr("__name__")?.extract()?;
        let items_repr = stack_to_pylist(py, &slf.borrow().stack)?.repr()?;
        Ok(format!("{class_name}({items_repr})"))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        Ok(self.dict.bind(py).as_any().call_method0("__iter__")?.unbind())
    }

    #[pyo3(signature = (key, default=None))]
    fn get(&self, py: Python<'_>, key: &Bound<'_, PyAny>, default: Option<Py<PyAny>>) -> PyResult<Py<PyAny>> {
        match self.dict.bind(py).get_item(key)? {
            Some(v) => Ok(v.unbind()),
            None => Ok(default.unwrap_or_else(|| py.None())),
        }
    }

    #[pyo3(signature = (*args, **kwargs))]
    fn update(slf: &Bound<'_, Self>, args: &Bound<'_, PyTuple>, kwargs: Option<&Bound<'_, PyDict>>) -> PyResult<()> {
        let py = slf.py();
        check_args_len(args.len())?;
        let arg0 = args.iter().next();
        let items = build_items(arg0.as_ref(), kwargs)?;
        let value_dict = dict_from_stack(py, &items)?;
        let value_dict = value_dict.bind(py);

        let mut this = slf.borrow_mut();
        let mut new_stack = Vec::with_capacity(this.stack.len() + items.len());
        this.stack.iter().try_for_each(|(k, v)| -> PyResult<()> {
            if !value_dict.contains(k.bind(py))? {
                new_stack.push((k.clone_ref(py), v.clone_ref(py)));
            }
            Ok(())
        })?;
        new_stack.extend(items);
        this.stack = new_stack;

        let self_dict = this.dict.bind(py);
        value_dict.iter().try_for_each(|(k, v)| self_dict.set_item(k, v))
    }

    fn keys(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        Ok(self.dict.bind(py).call_method0("keys")?.unbind())
    }

    fn values(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        Ok(self.dict.bind(py).call_method0("values")?.unbind())
    }

    fn items(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        Ok(self.dict.bind(py).call_method0("items")?.unbind())
    }

    fn clear(&mut self, py: Python<'_>) -> PyResult<()> {
        self.dict.bind(py).clear();
        self.stack.clear();
        Ok(())
    }

    #[pyo3(signature = (key, default=None))]
    fn pop(&mut self, py: Python<'_>, key: &Bound<'_, PyAny>, default: Option<Py<PyAny>>) -> PyResult<Py<PyAny>> {
        self.stack = stack_without_key(py, &self.stack, key)?;
        let default = default.unwrap_or_else(|| py.None());
        Ok(self.dict.bind(py).call_method1("pop", (key, default))?.unbind())
    }

    fn popitem(&mut self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let item = self.dict.bind(py).call_method0("popitem")?;
        let key = item.get_item(0)?;
        self.stack = stack_without_key(py, &self.stack, &key)?;
        Ok(item.unbind())
    }

    fn poplist(&mut self, py: Python<'_>, key: &Bound<'_, PyAny>) -> PyResult<Py<PyList>> {
        let values = stack_values_for_key(py, &self.stack, key)?;
        self.stack = stack_without_key(py, &self.stack, key)?;
        self.dict.bind(py).call_method1("pop", (key, py.None()))?;
        Ok(PyList::new(py, values)?.unbind())
    }

    fn append(&mut self, py: Python<'_>, key: Py<PyAny>, value: Py<PyAny>) -> PyResult<()> {
        self.stack.push((key.clone_ref(py), value.clone_ref(py)));
        self.dict.bind(py).set_item(key, value)?;
        Ok(())
    }

    #[pyo3(name = "getList")]
    fn get_list(&self, py: Python<'_>, key: &Bound<'_, PyAny>) -> PyResult<Py<PyList>> {
        let values = stack_values_for_key(py, &self.stack, key)?;
        Ok(PyList::new(py, values)?.unbind())
    }

    fn multi_items(&self, py: Python<'_>) -> PyResult<Py<PyList>> {
        Ok(stack_to_pylist(py, &self.stack)?.unbind())
    }
}

#[pyclass(mapping, extends = ImmutableMultiDict, subclass, module = "speedy.datastructures")]
pub struct MultiDict {}

impl MultiDict {
    fn setlist_impl(
        base: &mut PyRefMut<'_, ImmutableMultiDict>,
        py: Python<'_>,
        key: Py<PyAny>,
        values: Vec<Py<PyAny>>,
    ) -> PyResult<()> {
        if values.is_empty() {
            base.stack = stack_without_key(py, &base.stack, key.bind(py))?;
            base.dict.bind(py).call_method1("pop", (key, py.None()))?;
        } else {
            let mut new_stack = stack_without_key(py, &base.stack, key.bind(py))?;
            new_stack.extend(values.iter().map(|v| (key.clone_ref(py), v.clone_ref(py))));
            base.stack = new_stack;
            let last = values.last().expect("checked non-empty above").clone_ref(py);
            base.dict.bind(py).set_item(key, last)?;
        }
        Ok(())
    }
}

#[pymethods]
impl MultiDict {
    #[new]
    #[pyo3(signature = (*args, **kwargs))]
    fn new(
        py: Python<'_>,
        args: &Bound<'_, PyTuple>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<PyClassInitializer<MultiDict>> {
        check_args_len(args.len())?;
        let arg0 = if args.is_empty() { None } else { Some(args.get_item(0)?) };
        let items = build_items(arg0.as_ref(), kwargs)?;
        let base = ImmutableMultiDict::from_stack(py, items)?;
        Ok(PyClassInitializer::from(base).add_subclass(MultiDict {}))
    }

    fn __setitem__(self_: PyRefMut<'_, Self>, py: Python<'_>, key: Py<PyAny>, value: Py<PyAny>) -> PyResult<()> {
        let mut base = self_.into_super();
        Self::setlist_impl(&mut base, py, key, vec![value])
    }

    fn __delitem__(self_: PyRefMut<'_, Self>, py: Python<'_>, key: &Bound<'_, PyAny>) -> PyResult<()> {
        let mut base = self_.into_super();
        delitem_impl(&mut base, py, key)
    }

    fn setlist(self_: PyRefMut<'_, Self>, py: Python<'_>, key: Py<PyAny>, values: &Bound<'_, PyAny>) -> PyResult<()> {
        let values_vec = pyobj_to_vec(values)?;
        let mut base = self_.into_super();
        Self::setlist_impl(&mut base, py, key, values_vec)
    }

    #[pyo3(signature = (key, default=None))]
    fn setdefault(
        self_: PyRefMut<'_, Self>,
        py: Python<'_>,
        key: Py<PyAny>,
        default: Option<Py<PyAny>>,
    ) -> PyResult<Py<PyAny>> {
        let mut base = self_.into_super();
        let key_bound = key.bind(py).clone();
        if let Some(value) = base.dict.bind(py).get_item(&key_bound)? {
            Ok(value.unbind())
        } else {
            let default_value = default.unwrap_or_else(|| py.None());
            base.stack.push((key.clone_ref(py), default_value.clone_ref(py)));
            base.dict.bind(py).set_item(key, default_value.clone_ref(py))?;
            Ok(default_value)
        }
    }
}

fn parse_query_string_pairs(bytes: &[u8]) -> Vec<(String, String)> {
    form_urlencoded::parse(bytes)
        .map(|(k, v)| (k.into_owned(), v.into_owned()))
        .collect()
}

fn pairs_to_pylist<'py>(py: Python<'py>, pairs: &[(String, String)]) -> PyResult<Bound<'py, PyList>> {
    let items = pairs
        .iter()
        .map(|(k, v)| PyTuple::new(py, [k.as_str(), v.as_str()]).map(|t| t.into_any()))
        .collect::<PyResult<Vec<_>>>()?;
    PyList::new(py, items)
}

#[pyclass(mapping, extends = ImmutableMultiDict, subclass, module = "speedy.datastructures")]
pub struct QueryParams {}

#[pymethods]
impl QueryParams {
    #[new]
    #[pyo3(signature = (*args, **kwargs))]
    fn new(
        py: Python<'_>,
        args: &Bound<'_, PyTuple>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<PyClassInitializer<QueryParams>> {
        check_args_len(args.len())?;
        let arg0 = if args.is_empty() { None } else { Some(args.get_item(0)?) };

        let transformed: Option<Bound<'_, PyAny>> = match &arg0 {
            None => None,
            Some(value) => {
                if let Ok(s) = value.extract::<String>() {
                    let pairs = parse_query_string_pairs(s.as_bytes());
                    Some(pairs_to_pylist(py, &pairs)?.into_any())
                } else if let Ok(b) = value.cast::<PyBytes>() {
                    let pairs = parse_query_string_pairs(b.as_bytes());
                    Some(pairs_to_pylist(py, &pairs)?.into_any())
                } else {
                    Some(value.clone())
                }
            }
        };

        let items = build_items(transformed.as_ref(), kwargs)?;

        let stack: Vec<(Py<PyAny>, Py<PyAny>)> = items
            .into_iter()
            .map(|(k, v)| -> PyResult<(Py<PyAny>, Py<PyAny>)> {
                let k_str = k.bind(py).str()?.into_any().unbind();
                let v_str = v.bind(py).str()?.into_any().unbind();
                Ok((k_str, v_str))
            })
            .collect::<PyResult<_>>()?;

        let base = ImmutableMultiDict::from_stack(py, stack)?;
        Ok(PyClassInitializer::from(base).add_subclass(QueryParams {}))
    }

    fn __str__(slf: &Bound<'_, Self>) -> PyResult<String> {
        let py = slf.py();
        let base = slf.borrow().into_super();
        let pairs: Vec<(String, String)> = base
            .stack
            .iter()
            .map(|(k, v)| -> PyResult<(String, String)> {
                Ok((k.bind(py).extract::<String>()?, v.bind(py).extract::<String>()?))
            })
            .collect::<PyResult<_>>()?;
        Ok(encode_pairs(&pairs))
    }

    fn __repr__(slf: &Bound<'_, Self>) -> PyResult<String> {
        let py = slf.py();
        let class_name: String = slf.get_type().getattr("__name__")?.extract()?;
        let s = Self::__str__(slf)?;
        let repr_s = PyString::new(py, &s).repr()?;
        Ok(format!("{class_name}({repr_s})"))
    }
}

enum Storage {
    Memory(Cursor<Vec<u8>>),
    Disk(File),
}

fn to_pyerr(e: std::io::Error) -> PyErr {
    PyOSError::new_err(e.to_string())
}

#[pyclass(subclass, module = "speedy.datastructures")]
pub struct UploadFile {
    #[pyo3(get, set)]
    filename: String,
    #[pyo3(get, set)]
    headers: Py<PyDict>,
    max_size: u64,
    storage: Storage,
}

impl UploadFile {
    fn roll_over_if_needed(&mut self) -> std::io::Result<()> {
        if let Storage::Memory(cursor) = &self.storage {
            if cursor.get_ref().len() as u64 > self.max_size {
                let position = cursor.position();
                let mut disk_file = tempfile::tempfile()?;
                disk_file.write_all(cursor.get_ref())?;
                disk_file.seek(SeekFrom::Start(position))?;
                self.storage = Storage::Disk(disk_file);
            }
        }
        Ok(())
    }

    fn write_bytes(&mut self, data: &[u8]) -> std::io::Result<usize> {
        let written = match &mut self.storage {
            Storage::Memory(cursor) => cursor.write(data)?,
            Storage::Disk(file) => file.write(data)?,
        };
        self.roll_over_if_needed()?;
        Ok(written)
    }

    fn read_bytes(&mut self, size: i64) -> std::io::Result<Vec<u8>> {
        let reader: &mut dyn Read = match &mut self.storage {
            Storage::Memory(cursor) => cursor,
            Storage::Disk(file) => file,
        };
        if size < 0 {
            let mut buf = Vec::new();
            reader.read_to_end(&mut buf)?;
            Ok(buf)
        } else {
            let mut buf = vec![0u8; size as usize];
            let n = reader.read(&mut buf)?;
            buf.truncate(n);
            Ok(buf)
        }
    }

    fn seek_to(&mut self, offset: i64) -> std::io::Result<u64> {
        match &mut self.storage {
            Storage::Memory(cursor) => cursor.seek(SeekFrom::Start(offset as u64)),
            Storage::Disk(file) => file.seek(SeekFrom::Start(offset as u64)),
        }
    }

    fn tell(&mut self) -> std::io::Result<u64> {
        match &mut self.storage {
            Storage::Memory(cursor) => cursor.stream_position(),
            Storage::Disk(file) => file.stream_position(),
        }
    }
}

#[pymethods]
impl UploadFile {
    #[new]
    #[pyo3(signature = (filename, *, file_data=None, size=1_048_576, headers=None))]
    fn new(
        py: Python<'_>,
        filename: String,
        file_data: Option<&[u8]>,
        size: u64,
        headers: Option<Py<PyDict>>,
    ) -> PyResult<Self> {
        let mut this = UploadFile {
            filename,
            headers: headers.unwrap_or_else(|| PyDict::new(py).unbind()),
            max_size: size,
            storage: Storage::Memory(Cursor::new(Vec::new())),
        };
        if let Some(data) = file_data {
            if !data.is_empty() {
                this.write_bytes(data).map_err(to_pyerr)?;
                this.seek_to(0).map_err(to_pyerr)?;
            }
        }
        Ok(this)
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let filename_repr = PyString::new(py, &self.filename).repr()?;
        let headers_repr = self.headers.bind(py).repr()?;
        Ok(format!("UploadFile(filename={filename_repr}, headers={headers_repr})"))
    }

    #[getter]
    fn content_type(&self, py: Python<'_>) -> PyResult<Option<String>> {
        match self.headers.bind(py).get_item("content-type")? {
            Some(value) => Ok(Some(value.extract()?)),
            None => Ok(None),
        }
    }

    #[getter]
    fn is_spooled_to_disk(&self) -> bool {
        matches!(self.storage, Storage::Disk(_))
    }

    fn _write_sync(&mut self, data: &[u8]) -> PyResult<usize> {
        self.write_bytes(data).map_err(to_pyerr)
    }

    #[pyo3(signature = (size=-1))]
    fn _read_sync(&mut self, size: i64) -> PyResult<Vec<u8>> {
        self.read_bytes(size).map_err(to_pyerr)
    }

    fn _seek_sync(&mut self, offset: i64) -> PyResult<u64> {
        self.seek_to(offset).map_err(to_pyerr)
    }

    fn _size_sync(&mut self) -> PyResult<u64> {
        self.tell().map_err(to_pyerr)
    }

    fn _close_sync(&mut self) -> PyResult<()> {
        self.storage = Storage::Memory(Cursor::new(Vec::new()));
        Ok(())
    }
}
