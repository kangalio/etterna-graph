use crate::ok_or_continue;
use rayon::prelude::*;
use pyo3::prelude::*;


#[pyclass]
#[derive(Default)]
pub struct ReplaysAnalysis {
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
	// 361 entries: 180 in each direction, and one for the middle (0ms)
	#[pyo3(get)]
	pub sub_93_offset_buckets: Vec<u64>,
}

#[derive(Default)]
struct ScoreAnalysis {
	manipulation: f64,
	deviation_mean: f64,
	notes_per_column: [u64; 4],
	cbs_per_column: [u64; 4],
	longest_mcombo: u64,
	sub_93_offset_buckets: Vec<u64>,
}

// like slice.split(b'\n'), but with optimizations based on a minimum line length assumption
mod split_newlines {
	pub struct SplitNewlines<'a> {
		bytes: &'a [u8],
		min_line_length: usize,
		current_pos: usize, // the only changing field in here
	}
	
	impl<'a> Iterator for SplitNewlines<'a> {
		type Item = &'a [u8];
		
		fn next(&mut self) -> Option<Self::Item> {
			// Check stop condition
			if self.current_pos >= self.bytes.len() {
				return None;
			}
			
			let start_pos = self.current_pos;
			self.current_pos += self.min_line_length; // skip ahead as far as we can get away with
			
			while let Some(&c) = self.bytes.get(self.current_pos) {
				if c == b'\n' { break }
				self.current_pos += 1;
			}
			let line = &self.bytes[start_pos..self.current_pos];
			
			self.current_pos += 1; // Advance one to be on the start of a line again
			return Some(line);
		}
	}
	
	pub fn split_newlines<'a>(bytes: &'a [u8], min_line_length: usize) -> SplitNewlines<'a> {
		return SplitNewlines { bytes, min_line_length, current_pos: 0 };
	}
}
use split_newlines::split_newlines;


// Analyze a single score's replay
fn analyze(path: &str, wifescore: f64) -> Option<ScoreAnalysis> {
	let bytes = std::fs::read(path).ok()?;
	
	let mut score = ScoreAnalysis::default();
	
	let mut prev_tick: u64 = 0;
	let mut mcombo: u64 = 0;
	let mut num_notes: u64 = 0; // we can't derive this from notes_per_column cuz those exclude 5k+
	let mut num_manipped_notes: u64 = 0;
	let mut deviation_sum: f64 = 0.0;
	let mut sub_93_offset_buckets = vec![0u64; 361];
	for line in split_newlines(&bytes, 5) {
		if line.len() == 0 || line[0usize] == b'H' { continue }
		
		let mut token_iter = line.splitn(3, |&c| c == b' ');
		
		let tick = token_iter.next().expect("Missing tick token");
		let tick: u64 = ok_or_continue!(btoi::btou(tick));
		let deviation = token_iter.next().expect("Missing tick token");
		let deviation: f64 = ok_or_continue!(lexical::parse_lossy(&deviation));
		// "column" has the remainer of the string, luckily we just care about the first column
		let column = token_iter.next().expect("Missing tick token");
		let column: u64 = (column[0] - b'0') as u64;
		
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
		
		if wifescore < 0.93 {
			let deviation_ms_rounded = (deviation * 1000f64).round() as i64;
			let bucket_index = deviation_ms_rounded + 180i64;
			if bucket_index >= 0 && bucket_index < sub_93_offset_buckets.len() as i64 {
				sub_93_offset_buckets[bucket_index as usize] += 1;
			}
		}
		
		prev_tick = tick;
	}
	
	score.deviation_mean = deviation_sum / num_notes as f64;
	score.manipulation = num_manipped_notes as f64 / num_notes as f64;
	score.sub_93_offset_buckets = sub_93_offset_buckets;
	
	return Some(score);
}

#[pymethods]
impl ReplaysAnalysis {
	#[new]
	pub fn create(prefix: &str, scorekeys: Vec<&str>, wifescores: Vec<f64>) -> Self {
		let mut analysis = Self::default();
		analysis.sub_93_offset_buckets = vec![0; 361];
		
		let score_analyses: Vec<_> = scorekeys
				.par_iter()
				.zip(wifescores)
				.map(|(scorekey, wifescore)| {
					let replay_path = prefix.to_string() + scorekey;
					let score_option = analyze(&replay_path, wifescore);
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
			for i in 0..score.sub_93_offset_buckets.len() {
				analysis.sub_93_offset_buckets[i] += score.sub_93_offset_buckets[i];
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
