mod datastructures;

use pyo3::prelude::*;

#[pymodule]
mod _speedy {
    use pyo3::prelude::*;

    #[pymodule_export]
    use crate::datastructures::{Address, Headers, ImmutableState, MutableHeaders, State, URL, URLPath};

    #[pymodule_init]
    fn init(m: &Bound<'_, PyModule>) -> PyResult<()> {
        let py = m.py();
        let mapping_abc = py.import("collections.abc")?.getattr("Mapping")?;
        mapping_abc.call_method1("register", (m.getattr("Headers")?,))?;
        Ok(())
    }
}
