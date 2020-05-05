mod replays_analysis;

use pyo3::prelude::*;

#[pyclass]
pub struct PyReplaysAnalysis {
	#[pyo3(get)]
	pub score_indices: Vec<u64>,
	#[pyo3(get)]
	pub manipulations: Vec<f64>,
	#[pyo3(get)]
	pub deviation_mean: f64, // mean of all non-cb offsets
	#[pyo3(get)]
	pub notes_per_column: [u64; 4],
	#[pyo3(get)]
	pub cbs_per_column: [u64; 4],
	#[pyo3(get)]
	pub longest_mcombo: (u64, String), // contains longest combo and the associated scorekey
}

#[pymethods]
impl PyReplaysAnalysis {
	#[new]
	pub fn create(prefix: &str, scorekeys: Vec<&str>) -> Self {
		let analysis = replays_analysis::ReplaysAnalysis::create(prefix, &scorekeys);
		return PyReplaysAnalysis {
			score_indices: analysis.score_indices,
			manipulations: analysis.manipulations,
			deviation_mean: analysis.deviation_mean,
			notes_per_column: analysis.notes_per_column,
			cbs_per_column: analysis.cbs_per_column,
			longest_mcombo: analysis.longest_mcombo,
		};
	}
}

#[pymodule]
fn savegame_analysis(_py: Python, m: &PyModule) -> PyResult<()> {
	m.add_class::<PyReplaysAnalysis>()?;
	
	return Ok(());
}
