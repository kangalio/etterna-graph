#![allow(dead_code)]

mod replays_analysis;
mod skill_development_calc;
pub mod util; // pub, because the stuff in util should be general-purpose anyway
pub use replays_analysis::*;
pub use skill_development_calc::*;

use pyo3::prelude::*;

#[pymodule]
fn savegame_analysis(_py: Python, m: &PyModule) -> PyResult<()> {
	m.add_class::<ReplaysAnalysis>()?;
	m.add_class::<SkillTimeline>()?;
	
	return Ok(());
}
