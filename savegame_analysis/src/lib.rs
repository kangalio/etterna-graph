#![allow(dead_code)]

mod replays_analysis;
mod skill_development_calc;
mod util;
pub use replays_analysis::*;
pub use skill_development_calc::*;

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
		let analysis = ReplaysAnalysis::create(prefix, &scorekeys);
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

#[pyclass]
pub struct PySkillTimeline {
	#[pyo3(get)]
	pub day_vector: Vec<String>,
	#[pyo3(get)]
	pub rating_vectors: [Vec<f64>; 7],
}

#[pymethods]
impl PySkillTimeline {
	#[new]
	pub fn create(xml_path: &str) -> Self {
		let timeline = SkillTimeline::create(xml_path);
		return Self {
			day_vector: timeline.day_vector,
			rating_vectors: timeline.rating_vectors
		};
	}
}

#[pymodule]
fn savegame_analysis(_py: Python, m: &PyModule) -> PyResult<()> {
	m.add_class::<PyReplaysAnalysis>()?;
	m.add_class::<PySkillTimeline>()?;
	
	return Ok(());
}
