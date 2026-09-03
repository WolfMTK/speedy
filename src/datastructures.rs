use std::sync::Arc;

use indexmap::IndexMap;
use pyo3::exceptions::{PyAttributeError, PyKeyError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyList};

type Key = Arc<str>;

fn state_exception(py: Python<'_>, message: String) -> PyErr {
    match py
        .import("speedy.exceptions")
        .and_then(|m| m.getattr("StateException"))
        .and_then(|cls| cls.call1((message.clone(),)))
    {
        Ok(exc) => PyErr::from_value(exc),
        Err(_) => pyo3::exceptions::PyValueError::new_err(message),
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

fn coerce_state(
    py: Python<'_>,
    state: &Bound<'_, PyAny>,
    copy_data: bool,
) -> PyResult<IndexMap<Key, Py<PyAny>>> {
    if let Ok(existing) = state.extract::<PyRef<'_, ImmutableState>>() {
        return if copy_data {
            let deep = deepcopy_pydict(py, &pydict_from_index_map(py, &existing.data))?;
            index_map_from_pydict(&deep)
        } else {
            Ok(existing.data.iter().map(|(k, v)| (k.clone(), v.clone_ref(py))).collect())
        };
    }

    let raw_dict: Bound<'_, PyDict> = if let Ok(d) = state.cast::<PyDict>() {
        d.clone()
    } else {
        let abc = py.import("collections.abc")?;
        let is_mapping_or_iterable = state.is_instance(&abc.getattr("Mapping")?)?
            || state.is_instance(&abc.getattr("Iterable")?)?;
        if !is_mapping_or_iterable {
            return Err(state_exception(
                py,
                format!("Invalid state type: {}", state.get_type()),
            ));
        }
        py.get_type::<PyDict>().call1((state,))?.cast_into::<PyDict>()?
    };

    let final_dict = if copy_data { deepcopy_pydict(py, &raw_dict)? } else { raw_dict };
    index_map_from_pydict(&final_dict)
}

#[pyclass(subclass, module = "speedy.datastructures")]
pub struct ImmutableState {
    data: IndexMap<Key, Py<PyAny>>,
}

#[pymethods]
impl ImmutableState {
    #[new]
    #[pyo3(signature = (state, copy_data=true))]
    fn new(py: Python<'_>, state: &Bound<'_, PyAny>, copy_data: bool) -> PyResult<Self> {
        Ok(ImmutableState { data: coerce_state(py, state, copy_data)? })
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

    #[getter(_data)]
    fn get_data(&self, py: Python<'_>) -> Py<PyDict> {
        pydict_from_index_map(py, &self.data).unbind()
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let keys: Vec<&str> = self.data.keys().map(|k| k.as_ref()).collect();
        let list = PyList::new(py, keys)?;
        Ok(list.call_method0("__iter__")?.unbind())
    }

    fn __len__(&self) -> usize {
        self.data.len()
    }

    fn keys(&self, py: Python<'_>) -> PyResult<Py<PyList>> {
        let keys: Vec<&str> = self.data.keys().map(|k| k.as_ref()).collect();
        Ok(PyList::new(py, keys)?.unbind())
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

#[pyclass(extends = ImmutableState, subclass, module = "speedy.datastructures")]
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
