use std::collections::HashMap;
use std::sync::OnceLock;

use indexmap::IndexMap;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};
use regex::Regex;

const TOKEN_CHARS: &str = r"a-zA-Z0-9!#$%&'*+\-.^_`|~";

static PARAM_RE: OnceLock<Regex> = OnceLock::new();

fn param_re() -> PyResult<&'static Regex> {
    if let Some(re) = PARAM_RE.get() {
        return Ok(re);
    }
    let compiled = Regex::new(&format!(
        r#";[ \t\n\r\x0c\x0b]*([{t}]+)=(?:([{t}]+)|"([^"]*)")"#,
        t = TOKEN_CHARS
    ))
    .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok(PARAM_RE.get_or_init(|| compiled))
}

fn fix_firefox_quote_escapes(value: &str) -> String {
    let chars: Vec<char> = value.chars().collect();
    (0..chars.len())
        .scan(false, |skip, i| {
            if *skip {
                *skip = false;
                return Some(None);
            }
            if chars[i] == '\\' && chars.get(i + 1) == Some(&'"') {
                let rest: String = chars[i + 2..].iter().collect();
                if !(rest.starts_with("; ") || rest.trim_start().is_empty()) {
                    *skip = true;
                    return Some(Some("%22".to_string()));
                }
            }
            Some(Some(chars[i].to_string()))
        })
        .flatten()
        .collect()
}

fn parse_params(value: &str) -> PyResult<Vec<(String, String)>> {
    Ok(param_re()?
        .captures_iter(value)
        .map(|caps| {
            let key = caps[1].to_lowercase();
            let value = match caps.get(2) {
                Some(m) => m.as_str().to_string(),
                None => caps[3].replace("%22", "\""),
            };
            (key, value)
        })
        .collect())
}

#[pyfunction]
pub fn parse_content_header(value: &str) -> PyResult<(String, HashMap<String, String>)> {
    let fixed = fix_firefox_quote_escapes(value);
    let (main_value, params_part) = match fixed.find(';') {
        Some(idx) => (fixed[..idx].trim(), &fixed[idx..]),
        None => (fixed.trim(), ""),
    };
    let params = parse_params(params_part)?.into_iter().collect();
    Ok((main_value.to_lowercase(), params))
}

fn decode_rfc2231(value: &str) -> (Option<String>, Option<String>, String) {
    let parts: Vec<&str> = value.splitn(3, '\'').collect();
    if parts.len() <= 2 {
        return (None, None, value.to_string());
    }
    (Some(parts[0].to_string()), Some(parts[1].to_string()), parts[2].to_string())
}

#[derive(Default)]
struct FormPart {
    file_name: Option<String>,
    charset: String,
    field_name: Option<String>,
    headers: Vec<(String, String)>,
}

impl FormPart {
    fn new() -> Self {
        FormPart {
            charset: "utf-8".to_string(),
            ..Default::default()
        }
    }
}

fn encode_content_disposition(part: &mut FormPart, params: &HashMap<String, String>, py: Python<'_>) -> PyResult<()> {
    part.field_name = params.get("name").cloned();
    part.file_name = params.get("filename").cloned();
    if part.file_name.is_none() {
        if let Some(filename_star) = params.get("filename*") {
            let (encoding, _lang, raw_value) = decode_rfc2231(filename_star);
            let charset = encoding.unwrap_or_else(|| part.charset.clone());
            let unquote = py.import("urllib.parse")?.getattr("unquote")?;
            let decoded: String = unquote.call1((raw_value, charset))?.extract()?;
            part.file_name = Some(decoded);
        }
    }
    Ok(())
}

fn validation_exception(py: Python<'_>, message: String) -> PyErr {
    match py
        .import("speedy.exceptions")
        .and_then(|m| m.getattr("ValidationException"))
        .and_then(|cls| cls.call1((message.clone(),)))
    {
        Ok(exc) => PyErr::from_value(exc),
        Err(_) => PyValueError::new_err(message),
    }
}

#[pyclass(module = "speedy.multipart")]
pub struct MultiPartFormParser {
    body: Vec<u8>,
    boundary: Vec<u8>,
    multipart_limit: usize,
}

#[pymethods]
impl MultiPartFormParser {
    #[new]
    #[pyo3(signature = (body, boundary, multipart_limit=1000))]
    fn new(body: Vec<u8>, boundary: Vec<u8>, multipart_limit: usize) -> Self {
        MultiPartFormParser {
            body,
            boundary,
            multipart_limit,
        }
    }

    fn parse_body(&self, py: Python<'_>) -> PyResult<Vec<Vec<u8>>> {
        let parts = split_on_boundary(&self.body, &self.boundary, self.multipart_limit + 3);
        let form_parts: Vec<Vec<u8>> = if parts.len() >= 2 {
            parts[1..parts.len() - 1].to_vec()
        } else {
            Vec::new()
        };

        if form_parts.len() > self.multipart_limit {
            return Err(validation_exception(
                py,
                format!("number of form parts exceeds allowed limit of {}", self.multipart_limit),
            ));
        }
        Ok(form_parts)
    }

    fn parse(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let mut fields: IndexMap<String, Vec<Py<PyAny>>> = IndexMap::new();

        for value in self.parse_body(py)? {
            let mut part = FormPart::new();
            let mut line_index = 2usize;

            loop {
                let Some(rel_end) = find_bytes(&value[line_index..], b"\r\n") else {
                    break;
                };
                let line_end_index = line_index + rel_end;
                let form_line = std::str::from_utf8(&value[line_index..line_end_index])
                    .map_err(|e| PyValueError::new_err(format!("invalid utf-8 in form header: {e}")))?;
                if form_line.is_empty() {
                    line_index = line_end_index + 2;
                    break;
                }
                line_index = line_end_index + 2;

                let colon_index = form_line
                    .find(':')
                    .ok_or_else(|| PyValueError::new_err("missing ':' in form part header"))?;
                let current_idx = colon_index + 2;
                let field = form_line[..colon_index].to_lowercase();
                let (header_value, params) = parse_content_header(&form_line[current_idx..])?;

                if field == "content-disposition" {
                    encode_content_disposition(&mut part, &params, py)?;
                } else if field == "content-type" {
                    part.charset = params.get("charset").cloned().unwrap_or_else(|| "utf-8".to_string());
                }
                part.headers.push((field, header_value));
            }

            let Some(field_name) = part.field_name.clone() else {
                continue;
            };
            let value_obj = build_field_value(py, &part, &value, line_index)?;
            fields.entry(field_name).or_default().push(value_obj);
        }

        let result = PyDict::new(py);
        for (name, values) in fields {
            match <[Py<PyAny>; 1]>::try_from(values) {
                Ok([single]) => result.set_item(name, single)?,
                Err(values) => result.set_item(name, PyList::new(py, values)?)?,
            }
        }
        Ok(result.unbind())
    }
}

fn build_field_value(py: Python<'_>, part: &FormPart, form: &[u8], line_index: usize) -> PyResult<Py<PyAny>> {
    let post_data = trim_boundary_padding(&form[line_index..]);

    if let Some(file_name) = &part.file_name {
        let headers_dict = PyDict::new(py);
        for (k, v) in &part.headers {
            headers_dict.set_item(k, v)?;
        }
        let upload_file_cls = py.import("speedy.datastructures")?.getattr("UploadFile")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("filename", file_name)?;
        kwargs.set_item("file_data", post_data)?;
        kwargs.set_item("headers", headers_dict)?;
        Ok(upload_file_cls.call((), Some(&kwargs))?.unbind())
    } else if !post_data.is_empty() {
        decode_with_charset(py, post_data, &part.charset)
    } else {
        Ok(py.None())
    }
}

fn decode_with_charset(py: Python<'_>, data: &[u8], charset: &str) -> PyResult<Py<PyAny>> {
    let bytes = PyBytes::new(py, data);
    Ok(bytes.call_method1("decode", (charset,))?.unbind())
}

fn trim_boundary_padding(data: &[u8]) -> &[u8] {
    let start = data
        .iter()
        .position(|b| !matches!(b, b'\r' | b'\n'))
        .unwrap_or(data.len());
    let end = data[start..]
        .iter()
        .rposition(|b| !matches!(b, b'\r' | b'\n' | b'-'))
        .map(|i| start + i + 1)
        .unwrap_or(start);
    &data[start..end]
}

fn find_bytes(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    haystack.windows(needle.len()).position(|window| window == needle)
}

fn split_on_boundary(body: &[u8], boundary: &[u8], max_splits: usize) -> Vec<Vec<u8>> {
    if boundary.is_empty() {
        return vec![body.to_vec()];
    }
    let mut rest = body;
    let mut done = false;
    let mut count = 0usize;
    std::iter::from_fn(move || {
        if done {
            return None;
        }
        if count >= max_splits {
            done = true;
            return Some(rest.to_vec());
        }
        match find_bytes(rest, boundary) {
            Some(idx) => {
                count += 1;
                let piece = rest[..idx].to_vec();
                rest = &rest[idx + boundary.len()..];
                Some(piece)
            }
            None => {
                done = true;
                Some(rest.to_vec())
            }
        }
    })
    .collect()
}
