use std::path::PathBuf;
use itertools::{izip/*, Itertools*/};
use rayon::prelude::*;
use pyo3::prelude::*;
use crate::{ok_or_continue, some_or_continue};
use crate::util::split_newlines;


static OFFSET_BUCKET_RANGE: u64 = 180;
static NUM_OFFSET_BUCKETS: u64 = 2 * OFFSET_BUCKET_RANGE + 1;

#[pyclass]
#[derive(Default, Debug)]
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
	#[pyo3(get)]
	pub offset_buckets: Vec<u64>,
	#[pyo3(get)]
	pub sub_93_offset_buckets: Vec<u64>,
	#[pyo3(get)]
	pub standard_deviation: f64,
	#[pyo3(get)]
	pub fastest_combo: FastestComboInfo,
}

#[pyclass]
#[derive(Default, Debug, Clone)]
pub struct FastestComboInfo {
	#[pyo3(get)]
	pub length: u64,
	#[pyo3(get)]
	pub nps: f64,
	#[pyo3(get)]
	pub scorekey: String,
}

#[derive(Default)]
struct ScoreAnalysis {
	// a percentage (from 0.0 to 1.0) that says how many notes were hit out of order
	manipulation: f64,
	// the thing that's called "mean" in Etterna eval screen, except that it only counts non-CBs
	deviation_mean: f64,
	// the number of notes counted for the deviation_mean
	num_deviation_notes: u64,
	// number of total notes for each column
	notes_per_column: [u64; 4],
	// number of combo-breakers for each column
	cbs_per_column: [u64; 4],
	// the length of the longest combo of marvelous-only hits
	longest_mcombo: u64,
	// a vector of size NUM_OFFSET_BUCKETS. Each number corresponds to a certain timing window,
	// for example the middle entry is for (-0.5ms - 0.5ms). each number stands for the number of
	// hits in the respective timing window
	offset_buckets: Vec<u64>,
	// like offset_buckets, but for, well, sub 93% scores only
	sub_93_offset_buckets: Vec<u64>,
	
	fastest_combo: Option<FastestComboInScoreInfo>,
}

#[derive(Default, Debug)]
struct FastestComboInScoreInfo {
	start_second: f64,
	end_second: f64,
	length: u64,
	nps: f64,
}

// The caller still has to scale the returned nps by the music rate
fn find_fastest_note_subset(seconds: &[f64]) -> FastestComboInScoreInfo {
	//~ println!("Starting new combo n={}", seconds.len());
	let mut fastest = FastestComboInScoreInfo {
		start_second: 0.0, end_second: 0.0, length: 0, // dummy values
		nps: 0.0,
	};
	
	// Do a moving average for every possible subset length
	for n in 100..=seconds.len() {
		for i in 0..=(seconds.len() - n) {
			let end_i = i + n - 1; // inclusive end index
			let nps = (end_i - i) as f64 / (seconds[end_i] - seconds[i]);
			if nps > fastest.nps {
				fastest.length = n as u64; // = end_i - i + 1
				fastest.start_second = seconds[i];
				fastest.end_second = seconds[end_i];
				fastest.nps = nps;
				//~ println!("Found new max nps (={:02.2}) from {:.2}s - {:.2}s (n={})", max_nps, second_range.0, second_range.1, n);
			}
		}
	}
	//~ println!();
	
	return fastest;
}

/*fn find_fastest_combo_in_score(seconds: &[f64], are_cbs: &[bool], rate: f64) -> FastestComboInScoreInfo {
	// The nps track-keeping here is ignoring rate! rate is only applied at the end
	let mut fastest_combo = FastestComboInScoreInfo { length: 0, nps: 0.0 };
	
	// Why is the combo counting done as it's done?
	// Say you have this sequence of hits (y=hit, n=cb): "nnyyyyynn". when evaluating the 5 combo in
	// there, in reality we're only evaluating the first four hits, _right_ up to a point just
	// before the fifth hit. That's because the cb notes afterwards might be completely ridiculously
	// placed notes, maybe just 1ms after the last hit.
	// Say we have "yyyyn", where the "y"'s have a constant interval of 1 second, while the "n"
	// comes just 1ms after the last "y".
	// First y is at 0s, last y is at 3s, last n is at 3.001s. Including the time from last "y" to
	// "n" would yield nps=4/3.001s=1.33 - which is plainly not true. The have an interval of 1s,
	// not 1.33s. That's why we only look up to just before the last _hit_ (not cb) - it correctly
	// yields nps=3/3s=1.
	// This was a very lengthy explanation that no one except me will ever read.
	let mut combo_len = 0;
	let mut combo_start = 0.0;
	for (&second, &is_cb) in seconds.iter().zip(are_cbs) {
		if is_cb {
			combo_len = 0;
			// combo_start is in an invalid state from here until the next non_cb
			continue;
		}
		
		if combo_len == 0 {
			combo_start = second;
		}
		
		if combo_len >= 100 {
			let nps = combo_len as f64 / (second - combo_start);
			if nps > fastest_combo.nps {
				fastest_combo = FastestComboInScoreInfo { length: combo_len, nps };
			}
		}
		
		combo_len += 1;
	}
	
	fastest_combo.nps *= rate;
	
	return fastest_combo;
}*/
fn find_fastest_combo_in_score(seconds: &[f64], are_cbs: &[bool], rate: f64) -> FastestComboInScoreInfo {
	// The nps track-keeping here is ignoring rate! rate is only applied at the end
	let mut fastest_combo = FastestComboInScoreInfo::default();
	
	//~ println!("New score");
	
	let mut combo_start_i: Option<usize> = Some(0);
	let mut initiate_combo_end = |combo_end_i| { // is called on every cb and at the end
		if let Some(combo_start_i) = combo_start_i {
			// the position of all notes, in seconds, within a full combo
			let combo = &seconds[combo_start_i..combo_end_i];
			let fastest_note_subset = find_fastest_note_subset(combo);
			if fastest_note_subset.nps > fastest_combo.nps {
				fastest_combo = fastest_note_subset;
			}
		}
		combo_start_i = None; // Combo is handled now, a new combo yet has to begin
	};
	
	for (i, &is_cb) in are_cbs.iter().enumerate() {
		if is_cb {
			initiate_combo_end(i);
		}
	}
	initiate_combo_end(seconds.len());
	
	//~ println!();
	
	fastest_combo.nps *= rate;
	
	return fastest_combo;
}

// Analyze a single score's replay
fn analyze(path: &str, wifescore: f64, timing_info_maybe: Option<&crate::TimingInfo>, rate: f64)
		-> Option<ScoreAnalysis> {
	
	let bytes = std::fs::read(path).ok()?;
	let approx_max_num_lines = bytes.len() / 16; // 16 is a pretty good value for this
	
	let mut score = ScoreAnalysis::default();
	
	let mut prev_tick: u64 = 0;
	let mut mcombo: u64 = 0;
	let mut num_notes: u64 = 0; // we can't derive this from notes_per_column cuz those exclude 5k+
	let mut num_deviation_notes: u64 = 0; // number of notes used in deviation calculation
	let mut num_manipped_notes: u64 = 0;
	let mut deviation_sum: f64 = 0.0;
	let mut offset_buckets = vec![0u64; NUM_OFFSET_BUCKETS as usize];
	let mut sub_93_offset_buckets = vec![0u64; NUM_OFFSET_BUCKETS as usize];
	let mut ticks = Vec::with_capacity(approx_max_num_lines);
	let mut are_cbs = Vec::with_capacity(approx_max_num_lines);
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
		
		ticks.push(tick);
		
		if tick < prev_tick {
			num_manipped_notes += 1;
		}
		
		if deviation.abs() <= 0.09 {
			deviation_sum += deviation;
			num_deviation_notes += 1;
			are_cbs.push(false);
		} else {
			are_cbs.push(true);
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
		
		let deviation_ms_rounded = (deviation * 1000f64).round() as i64;
		let bucket_index = deviation_ms_rounded + OFFSET_BUCKET_RANGE as i64;
		if bucket_index >= 0 && bucket_index < sub_93_offset_buckets.len() as i64 {
			offset_buckets[bucket_index as usize] += 1;
			if wifescore < 0.93 {
				sub_93_offset_buckets[bucket_index as usize] += 1;
			}
		}
		
		prev_tick = tick;
	}
	
	score.num_deviation_notes = num_deviation_notes;
	score.deviation_mean = deviation_sum / num_deviation_notes as f64;
	score.manipulation = num_manipped_notes as f64 / num_notes as f64;
	score.offset_buckets = offset_buckets;
	score.sub_93_offset_buckets = sub_93_offset_buckets;
	
	ticks.sort_unstable(); // need to do this to be able to convert to seconds
	
	if let Some(timing_info) = timing_info_maybe {
		// TODO the deviance is not applied yet. E.g. when the player starts tapping early and ending
		// the combo late, the calculated nps is higher than deserved
		let seconds = timing_info.ticks_to_seconds(&ticks);
		
		score.fastest_combo = Some(find_fastest_combo_in_score(&seconds, &are_cbs, rate));
	}
	
	return Some(score);
}

fn calculate_standard_deviation(offset_buckets: &[u64]) -> f64 {
	/*
	standard deviation is `sqrt(mean(square(values - mean(values)))`
	modified version with weights:
	`sqrt(mean(square(values - mean(values, weights)), weights))`
	or, with the "mean(values, weights)" construction expanded:
	
	sqrt(
		sum(
			weights
			*
			square(
				values
				-
				sum(values * weights) / sum(weights)))
		/
		sum(weights)
	)
	*/
	
	assert_eq!(offset_buckets.len() as u64, NUM_OFFSET_BUCKETS);
	
	// util function
	let iter_value_weight_pairs = || offset_buckets.iter()
			.enumerate()
			.map(|(i, weight)| (i as i64 - OFFSET_BUCKET_RANGE as i64, weight));
	
	let mut value_x_weights_sum = 0;
	let mut weights_sum = 0;
	for (value, &weight) in iter_value_weight_pairs() {
		value_x_weights_sum += value * weight as i64;
		weights_sum += weight;
	}
	
	let temp_value = value_x_weights_sum / weights_sum as i64;
	
	let mut temp_sum = 0;
	for (value, &weight) in iter_value_weight_pairs() {
		temp_sum += weight as i64 * (value - temp_value).pow(2);
	}
	
	let standard_deviation = (temp_sum as f64 / weights_sum as f64).sqrt();
	return standard_deviation;
}

#[pymethods]
impl ReplaysAnalysis {
	#[new]
	pub fn create(prefix: &str, scorekeys: Vec<&str>, wifescores: Vec<f64>,
			packs: Vec<&str>, songs: Vec<&str>,
			rates: Vec<f64>,
			cache_db_path: &str
		) -> Self {
		
		// Validate parameters
		assert_eq!(scorekeys.len(), wifescores.len());
		assert_eq!(scorekeys.len(), packs.len());
		assert_eq!(scorekeys.len(), songs.len());
		assert_eq!(scorekeys.len(), rates.len());
		
		// Setup rayon
		let rayon_config_result = rayon::ThreadPoolBuilder::new()
				.num_threads(20) // many threads because of file io
				.build_global();
		if let Err(e) = rayon_config_result {
			println!("Warning: rayon ThreadPoolBuilder failed: {:?}", e);
		}
		
		let mut analysis = Self::default();
		analysis.offset_buckets = vec![0; NUM_OFFSET_BUCKETS as usize];
		analysis.sub_93_offset_buckets = vec![0; NUM_OFFSET_BUCKETS as usize];
		
		let timing_info_index = crate::build_timing_info_index(&PathBuf::from(cache_db_path));
		
		let tuples: Vec<_> = izip!(scorekeys, wifescores, packs, songs, rates).collect();
		let score_analyses: Vec<_> = tuples
				.par_iter()
				// must not filter_map here (need to keep indices accurate)!
				.map(|(scorekey, wifescore, pack, song, rate)| {
					let replay_path = prefix.to_string() + scorekey;
					let song_id = crate::SongId { pack: pack.to_string(), song: song.to_string() };
					let timing_info_maybe = timing_info_index.get(&song_id);
					let score = analyze(&replay_path, *wifescore, timing_info_maybe, *rate)?;
					return Some((scorekey, score));
				})
				.collect();
		
		let mut deviation_mean_sum: f64 = 0.0;
		let mut longest_mcombo: u64 = 0;
		let mut longest_mcombo_scorekey: &str = "<no chart>";
		for (i, score_analysis_option) in score_analyses.iter().enumerate() {
			let (scorekey, score) = some_or_continue!(score_analysis_option);
			
			analysis.score_indices.push(i as u64);
			analysis.manipulations.push(score.manipulation);
			deviation_mean_sum += score.deviation_mean;
			
			for i in 0..4 {
				analysis.cbs_per_column[i] += score.cbs_per_column[i];
				analysis.notes_per_column[i] += score.notes_per_column[i];
			}
			
			// TODO use zipped iterators to avoid bounds-checking cost
			for i in 0..NUM_OFFSET_BUCKETS as usize {
				analysis.offset_buckets[i] += score.offset_buckets[i];
				analysis.sub_93_offset_buckets[i] += score.sub_93_offset_buckets[i];
			}
			
			if score.longest_mcombo > longest_mcombo {
				longest_mcombo = score.longest_mcombo;
				longest_mcombo_scorekey = scorekey;
			}
			
			if let Some(score_fastest_combo) = &score.fastest_combo {
				if score_fastest_combo.nps > analysis.fastest_combo.nps {
					analysis.fastest_combo = FastestComboInfo {
						nps: score_fastest_combo.nps,
						length: score_fastest_combo.length,
						scorekey: scorekey.to_string(),
					}
				}
			}
		}
		debug_assert!(analysis.manipulations.len() == analysis.score_indices.len());
		let num_scores = analysis.manipulations.len();
		
		analysis.deviation_mean = deviation_mean_sum / num_scores as f64;
		analysis.longest_mcombo = (longest_mcombo, longest_mcombo_scorekey.into());
		
		analysis.standard_deviation = calculate_standard_deviation(&analysis.offset_buckets);
		
		return analysis;
	}
} 
