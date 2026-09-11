mod _multipart;
mod datastructures;
mod requests;
mod responses;

use pyo3::prelude::*;

#[pymodule]
mod _speedy {
    use pyo3::prelude::*;

    #[pymodule_export]
    use crate::_multipart::{MultiPartFormParser, parse_content_header};
    #[pymodule_export]
    use crate::datastructures::{
        Address, Headers, ImmutableMultiDict, ImmutableState, MultiDict, MutableHeaders, QueryParams, State, URL,
        URLPath, UploadFile,
    };
    #[pymodule_export]
    use crate::requests::{HTTPConnection, Request, parse_json, parse_urlencoded_form};
    #[pymodule_export]
    use crate::responses::{
        Response, compute_etag, dump_json, multipart_closing_boundary, multipart_content_length,
        multipart_range_header, parse_range_header,
    };

    #[pymodule_init]
    fn init(m: &Bound<'_, PyModule>) -> PyResult<()> {
        let py = m.py();
        let mapping_abc = py.import("collections.abc")?.getattr("Mapping")?;
        mapping_abc.call_method1("register", (m.getattr("Headers")?,))?;
        mapping_abc.call_method1("register", (m.getattr("HTTPConnection")?,))?;
        m.add("JSONDecodeError", py.get_type::<crate::requests::JSONDecodeError>())?;
        m.add("MalformedRangeHeader", py.get_type::<crate::responses::MalformedRangeHeader>())?;
        m.add("RangeNotSatisfiable", py.get_type::<crate::responses::RangeNotSatisfiable>())?;
        Ok(())
    }
}
