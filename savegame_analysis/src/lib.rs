#![allow(dead_code)]

mod replays_analysis;
pub use replays_analysis::*;

mod skill_development_calc;
pub use skill_development_calc::*;

mod timing_info;
pub use timing_info::*;

mod wife;
pub use wife::*;

pub mod util; // pub, because the stuff in util should be general-purpose anyway
// also, don't `use`, because the general-purpose stuff that's not really connected to the rest of
// the program shouldn't be in the same place as the rest of the program either.

use pyo3::prelude::*;


#[pymodule]
fn savegame_analysis(_py: Python, m: &PyModule) -> PyResult<()> {
	m.add_class::<ReplaysAnalysis>()?;
	m.add_class::<SkillTimeline>()?;
	
	return Ok(());
}
