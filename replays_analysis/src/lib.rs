#![allow(dead_code)]
use std::fs::File;
use std::io::{self, BufRead};
use pyo3::prelude::*;
use rayon::prelude::*;


fn read_lines(path: &str) -> io::Result<io::Lines<io::BufReader<File>>> {
	let file = File::open(path)?;
    return Ok(io::BufReader::new(file).lines());
}

#[pyclass(dict)]
#[derive(Default)]
pub struct ReplaysAnalysis {
	#[pyo3(get)]
	score_indices: Vec<u64>,
	#[pyo3(get)]
	manipulations: Vec<f64>,
	#[pyo3(get)]
	deviation_mean: f64, // mean of all non-cb offsets
	#[pyo3(get)]
	notes_per_column: [u64; 4],
	#[pyo3(get)]
	cbs_per_column: [u64; 4],
	#[pyo3(get)]
	_total_notes: u64, // TODO: implement by counting notes in xml
	#[pyo3(get)]
	longest_mcombo: (u64, String), // contains longest combo and the associated scorekey
}

#[derive(Default)]
struct ScoreAnalysis {
	manipulation: f64,
	deviation_mean: f64,
	notes_per_column: [u64; 4],
	cbs_per_column: [u64; 4],
	longest_mcombo: u64,
}

// Analyze a single score's replay
fn analyze(path: &str) -> Option<ScoreAnalysis> {
	let lines = read_lines(path).ok()?;
	
	let mut score = ScoreAnalysis::default();
	
	let mut prev_tick: u64 = 0;
	let mut mcombo: u64 = 0;
	let mut num_notes: u64 = 0; // we can't derive this from notes_per_column cuz those exclude 5k+
	let mut num_manipped_notes: u64 = 0;
	let mut deviation_sum: f64 = 0.0;
	for line in lines {
		let line = line.expect("the hell");
		if line.starts_with("H") { continue }
		
		let mut token_iter = line.split(" ");
		
		let tick = token_iter.next().expect("Missing tick token");
		let tick: u64 = match tick.parse() { Ok(a) => a, Err(_) => continue };
		let deviation = token_iter.next().expect("Missing tick token");
		let deviation: f64 = match deviation.parse() { Ok(a) => a, Err(_) => continue };
		let column = token_iter.next().expect("Missing tick token");
		let column: u64 = match column.parse() { Ok(a) => a, Err(_) => continue };
		
		num_notes += 1;
		
		if tick < prev_tick {
			num_manipped_notes += 1;
		}
		
		if deviation.abs() <= 0.09 {
			deviation_sum += deviation;
		}
		
		if column < 4 {
			score.notes_per_column[column as usize] += 1;
			
			if deviation.abs() > 0.09 {
				score.cbs_per_column[column as usize] += 1;
			}
		}
		
		if deviation.abs() <= 0.0225 {
			mcombo += 1;
		} else {
			if mcombo > score.longest_mcombo {
				score.longest_mcombo = mcombo;
			}
			mcombo = 0;
		}
		
		prev_tick = tick;
	}
	
	score.deviation_mean = deviation_sum / num_notes as f64;
	score.manipulation = num_manipped_notes as f64 / num_notes as f64;
	
	return Some(score);
}

#[pymethods]
impl ReplaysAnalysis {
	#[new]
	fn create(prefix: &str, scorekeys: Vec<&str>) -> Self {
		let mut analysis = Self::default();
		
		let score_analyses: Vec<_> = scorekeys.par_iter()
				.map(|scorekey| {
					let score_option = analyze(&(prefix.to_string() + scorekey));
					return (scorekey, score_option);
				})
				.collect();
		
		let mut deviation_mean_sum: f64 = 0.0;
		let mut longest_mcombo: u64 = 0;
		let mut longest_mcombo_scorekey: &str = "<no chart>";
		for (i, (scorekey, score_option)) in score_analyses.iter().enumerate() {
			let score = match score_option { Some(a) => a, None => continue };
			
			analysis.score_indices.push(i as u64);
			analysis.manipulations.push(score.manipulation);
			deviation_mean_sum += score.deviation_mean;
			for i in 0..4 {
				analysis.cbs_per_column[i] += score.cbs_per_column[i];
				analysis.notes_per_column[i] += score.notes_per_column[i];
			}
			if score.longest_mcombo > longest_mcombo {
				longest_mcombo = score.longest_mcombo;
				longest_mcombo_scorekey = scorekey;
			}
		}
		let num_scores = analysis.manipulations.len();
		analysis.deviation_mean = deviation_mean_sum / num_scores as f64;
		analysis.longest_mcombo = (longest_mcombo, longest_mcombo_scorekey.into());
		
		return analysis;
	}
}

#[pymodule]
fn lib_replays_analysis(_py: Python, m: &PyModule) -> PyResult<()> {
	m.add_class::<ReplaysAnalysis>()?;
	
	return Ok(());
}
