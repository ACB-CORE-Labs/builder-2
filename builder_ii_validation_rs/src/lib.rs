use pyo3::prelude::*;
use pyo3::types::PyDict;
use pythonize::depythonize;
use serde_json::Value;

mod validation;

#[pyfunction]
fn validate_artifact(
    py: Python<'_>,
    kind: &str,
    data: &Bound<'_, PyDict>,
) -> PyResult<(bool, Vec<String>)> {
    let json_data: Value = depythonize(data).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("Invalid input data: {}", e))
    })?;

    // Detach from the interpreter while validating.
    let errors = py.detach(|| validation::validate_artifact_core(kind, &json_data));

    let valid = errors.is_empty();
    Ok((valid, errors))
}

#[pymodule]
fn builder_ii_validation_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(validate_artifact, m)?)?;
    Ok(())
}
