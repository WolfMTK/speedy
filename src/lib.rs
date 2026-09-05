mod datastructures;

use pyo3::prelude::*;

#[pymodule]
mod _speedy {
    #[pymodule_export]
    use crate::datastructures::{Address, ImmutableState, State, URL, URLPath};
}
