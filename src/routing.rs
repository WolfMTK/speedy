use matchit::Router;
use pyo3::prelude::*;
use pyo3::types::PyString;

#[pyclass(module = "speedy.routing")]
pub struct RouteTree {
    router: Router<usize>,
}

#[pymethods]
impl RouteTree {
    #[new]
    fn new() -> Self {
        Self { router: Router::new() }
    }

    fn insert(&mut self, key: &str, value: usize) -> bool {
        self.router.insert(key, value).is_ok()
    }

    fn at(&self, path: &Bound<'_, PyString>) -> Option<usize> {
        self.router.at(&path.to_string_lossy()).ok().map(|found| *found.value)
    }
}
