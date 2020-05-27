use std::path::PathBuf;
use itertools::{izip/*, Itertools*/};
use rayon::prelude::*;
use pyo3::prelude::*;
use crate::{ok_or_continue, some_or_continue};
use crate::util;
use crate::wife::wife3;


// IMPORTANT ANNOUNCE FOR WIFE POINTS:
// In this crate, wife points are scaled to a maximum of 1 (not 2 like in the Etterna source code)!

const OFFSET_BUCKET_RANGE: u64 = 180;
const NUM_OFFSET_BUCKETS: u64 = 2 * OFFSET_BUCKET_RANGE + 1;

const FASTEST_JACK_WINDOW_SIZE: u64 = 30;

// Note subsets will not be searched above size min_num_notes + NOTE_SUBSET_SEARCH_SPACE_SIZE will
// be searched. The reason we can get away doing this is because it's very unlikely that a, say,
// 120 combo is gonna have a faster nps than a 100 combo
const NOTE_SUBSET_SEARCH_SPACE_SIZE: u64 = 20;

#[pyclass]
#[derive(Default, Debug)]
pub struct ReplaysAnalysis {
	#[pyo3(get)]
	pub score_indices: Vec<u64>, // the indices of the scores whose analysis didn't fail
	#[pyo3(get)]
	pub manipulations: Vec<f32>,
	#[pyo3(get)]
	pub deviation_mean: f32, // mean of all non-cb offsets
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
	pub standard_deviation: f32,
	#[pyo3(get)]
	pub fastest_combo: FastestComboInfo,
	#[pyo3(get)]
	pub fastest_combo_scorekey: String,
	#[pyo3(get)]
	pub fastest_jack: FastestComboInfo,
	#[pyo3(get)]
	pub fastest_jack_scorekey: String,
	#[pyo3(get)]
	pub fastest_acc: FastestComboInfo,
	#[pyo3(get)]
	pub fastest_acc_scorekey: String,
}

#[pyclass]
#[derive(Default, Debug, Clone)]
pub struct FastestComboInfo {
	#[pyo3(get)]
	start_second: f32,
	#[pyo3(get)]
	end_second: f32,
	#[pyo3(get)]
	length: u64,
	#[pyo3(get)]
	speed: f32,
}

#[derive(Default)]
struct ScoreAnalysis {
	// a percentage (from 0.0 to 1.0) that says how many notes were hit out of order
	manipulation: f32,
	// the thing that's called "mean" in Etterna eval screen, except that it only counts non-CBs
	deviation_mean: f32,
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
	// the note subset (with >= 100 notes) with the highest nps (`speed` = nps)
	fastest_combo: Option<FastestComboInfo>,
	// like fastest_combo, but it's only for a single finger, and with a different window -
	// FASTEST_JACK_WINDOW_SIZE - too
	fastest_jack: Option<FastestComboInfo>,
	// like fastest_combo, but `speed` is not simply nps but nps*(wifescore in that window) instead.
	// For example, if you played 10 nps with an accuracy equivalent to 98%, `speed` would be 9.8
	fastest_acc: Option<FastestComboInfo>,
}

pub fn parse_sm_float(string: &[u8]) -> Option<f32> {
	let string = &string[..string.len()-1]; // cut off last digit to speed up float parsing
	return lexical_core::parse_lossy(string).ok();
	
	/*
	// For performance reasons, this assumes that the passed-in bytestring is in the format
	// -?[01]\.\d{6} (optionally a minus, then 0 or 1, a dot, and then 6 floating point digits. (This
	// function only parses 5 of those floating point digits though). Example string: "-0.010371"
	
	let is_negative = string[0] == b'-';
	let string = if is_negative { &string[1..] } else { string }; // Strip minus
	
	let mut digits_part: u32 = 0;
	digits_part += (string[6] - b'0') as u32 * 1;
	digits_part += (string[5] - b'0') as u32 * 10;
	digits_part += (string[4] - b'0') as u32 * 100;
	digits_part += (string[3] - b'0') as u32 * 1000;
	digits_part += (string[2] - b'0') as u32 * 10000;
	digits_part += (string[0] - b'0') as u32 * 100000;
	
	let mut number = digits_part as f32 / 100000 as f32;
	
	if is_negative {
		number = -number;
	}
	
	return Some(number);
	*/
}

// The caller still has to scale the returned nps by the music rate
// `seconds` must be sorted
fn find_fastest_note_subset(seconds: &[f32],
		min_num_notes: u64,
		max_num_notes: u64, // inclusive
	) -> FastestComboInfo {
	
	let mut fastest = FastestComboInfo {
		start_second: 0.0, end_second: 0.0, length: 0, // dummy values
		speed: 0.0,
	};
	
	if seconds.len() <= min_num_notes as usize { return fastest }
	
	// Do a moving average for every possible subset length (except the large lengths cuz it's
	// unlikely that there'll be something relevant there)
	let end_n = std::cmp::min(seconds.len(), max_num_notes as usize + 1);
	for n in (min_num_notes as usize)..end_n {
		for i in 0..=(seconds.len() - n - 1) {
			let end_i = i + n;
			let nps: f32 = (end_i - i) as f32 / (seconds[end_i] - seconds[i]);
			
			// we do >= because than we can potentially catch later - longer - subsets as well.
			// a 30 NPS subset is more impressive at window size 110 than at window size 100.
			if nps >= fastest.speed {
				fastest = FastestComboInfo {
					length: n as u64,
					start_second: seconds[i],
					end_second: seconds[end_i],
					speed: nps,
				};
			}
		}
	}
	
	return fastest;
}

// The caller still has to scale the returned nps by the music rate
// `seconds` must be sorted, and in the same order as `wife_pts`
fn find_fastest_note_subset_wife_pts(seconds: &[f32],
		min_num_notes: u64,
		max_num_notes: u64, // inclusive
		wife_pts: &[f32],
	) -> FastestComboInfo {
	
	assert!(wife_pts.len() == seconds.len());
	
	let mut fastest = FastestComboInfo {
		start_second: 0.0, end_second: 0.0, length: 0, // dummy values
		speed: 0.0,
	};
	
	if seconds.len() <= min_num_notes as usize {
		// If the combo is too short to detect any subsets, we return early
		return fastest;
	}
	
	let mut wife_pts_sum_start = wife_pts[0..min_num_notes as usize].iter().sum();
	
	// Do a moving average for every possible subset length
	let end_n = std::cmp::min(seconds.len(), max_num_notes as usize + 1);
	for n in (min_num_notes as usize)..end_n {
		// Instead of calculating the sum of the local wife_pts window for every iteration, we keep
		// a variable to it and simply update it on every iteration instead -> that's faster
		let mut wife_pts_sum: f32 = wife_pts_sum_start;
		
		for i in 0..=(seconds.len() - n - 1) {
			let end_i = i + n;
			let mut nps: f32 = (end_i - i) as f32 / (seconds[end_i] - seconds[i]);
			
			nps *= wife_pts_sum / n as f32; // multiply by wife points
			
			if nps >= fastest.speed { // why >=? see other note subset function
				fastest = FastestComboInfo {
					length: n as u64,
					start_second: seconds[i],
					end_second: seconds[end_i],
					speed: nps,
				};
			}
			
			// Move the wife_pts_sum window one place forward
			wife_pts_sum -= wife_pts[i];
			wife_pts_sum += wife_pts[end_i];
		}
		
		// Update the initial window sum
		wife_pts_sum_start += wife_pts[n];
	}
	
	return fastest;
}

fn find_fastest_combo_in_score(seconds: &[f32], are_cbs: &[bool],
		min_num_notes: u64,
		max_num_notes: u64,
		// if this is provided, the nps will be multiplied by wife pts. the 'nps' is practically
		// 'wife points per second' then
		wife_pts: Option<&[f32]>,
		rate: f32,
	) -> FastestComboInfo {
	
	assert_eq!(seconds.len(), are_cbs.len());
	if let Some(wife_pts) = wife_pts {
		assert_eq!(seconds.len(), wife_pts.len());
	}
	
	// The nps track-keeping here is ignoring rate! rate is only applied at the end
	let mut fastest_combo = FastestComboInfo::default();
	
	let mut combo_start_i: Option<usize> = Some(0);
	
	// is called on every cb (cuz that ends a combo) and at the end (cuz that also ends a combo)
	let mut trigger_combo_end = |combo_end_i| {
		if let Some(combo_start_i) = combo_start_i {
			// the position of all notes, in seconds, within a full combo
			let combo = &seconds[combo_start_i..combo_end_i];
			
			let fastest_note_subset;
			if let Some(wife_pts) = wife_pts {
				let wife_pts_slice = &wife_pts[combo_start_i..combo_end_i];
				fastest_note_subset = find_fastest_note_subset_wife_pts(combo,
						min_num_notes,
						max_num_notes,
						wife_pts_slice);
			} else {
				fastest_note_subset = find_fastest_note_subset(combo,
						min_num_notes,
						max_num_notes);
			}
			
			if fastest_note_subset.speed > fastest_combo.speed {
				fastest_combo = fastest_note_subset;
			}
		}
		combo_start_i = None; // Combo is handled now, a new combo yet has to begin
	};
	
	for (i, &is_cb) in are_cbs.iter().enumerate() {
		if is_cb {
			trigger_combo_end(i);
		}
	}
	trigger_combo_end(seconds.len());
	
	fastest_combo.speed *= rate;
	
	return fastest_combo;
}

fn put_deviations_into_buckets(deviations: &[f32]) -> Vec<u64> {
	let mut offset_buckets = vec![0u64; NUM_OFFSET_BUCKETS as usize];
	
	for deviation in deviations {
		let deviation_ms_rounded = (deviation * 1000f32).round() as i64;
		let bucket_index = deviation_ms_rounded + OFFSET_BUCKET_RANGE as i64;
		
		if bucket_index >= 0 && bucket_index < offset_buckets.len() as i64 {
			offset_buckets[bucket_index as usize] += 1;
		}
	}
	
	return offset_buckets;
}

fn parse_replay_file(path: &str) -> Option<(Vec<u64>, Vec<f32>, Vec<u8>)> {
	let bytes = std::fs::read(path).ok()?;
	let approx_max_num_lines = bytes.len() / 16; // 16 is a pretty good appproximation	
	
	let mut ticks = Vec::with_capacity(approx_max_num_lines);
	let mut deviations = Vec::with_capacity(approx_max_num_lines);
	let mut columns = Vec::with_capacity(approx_max_num_lines);
	for line in util::split_newlines(&bytes, 5) {
		if line.len() == 0 || line[0usize] == b'H' { continue }
		
		let mut token_iter = line.splitn(3, |&c| c == b' ');
		
		let tick = token_iter.next().expect("Missing tick token");
		let tick: u64 = ok_or_continue!(btoi::btou(tick));
		let deviation = token_iter.next().expect("Missing tick token");
		let deviation = some_or_continue!(parse_sm_float(deviation)) as f32;
		// remainder has the rest of the string in one slice, without any whitespace info or such.
		// luckily we know the points of interest's exact positions, so we can just directly index
		// into the remainder string to get what we need
		let remainder = token_iter.next().expect("Missing tick token");
		let column: u8 = remainder[0] - b'0';
		let note_type: u8 = if remainder.len() >= 3 { remainder[2] - b'0' } else { 1 };
		
		// We don't want hold ends, mines, lifts etc
		if note_type != 1 { continue }
		
		ticks.push(tick);
		deviations.push(deviation);
		columns.push(column);
	}
	
	return Some((ticks, deviations, columns));
}

// Analyze a single score's replay
fn analyze(path: &str,
		timing_info_maybe: Option<&crate::TimingInfo>,
		rate: f32
	) -> Option<ScoreAnalysis> {
	
	// ticks is mutable because it needs to be sorted later
	let (mut ticks, deviations, columns) = parse_replay_file(path)?;
	
	let mut score = ScoreAnalysis::default();
	
	// tuple of vectors; first value is tick, first value is deviation
	let mut fastest_jack = FastestComboInfo::default();
	let mut finger_hits: [(Vec<u64>, Vec<f32>); 4] =
			[(vec![], vec![]), (vec![], vec![]), (vec![], vec![]), (vec![], vec![])];
	let mut trigger_finger_jack_end = |(ticks, deviations): &mut (Vec<_>, Vec<_>)| {
		let timing_info = match timing_info_maybe {
			Some(a) => a,
			None => return, // this score doesn't have timing info, no point in trying to measure jacks
		};
		
		ticks.sort();
		let mut seconds = timing_info.ticks_to_seconds(ticks);
		
		// Apply hit deviation to hit seconds
		for (deviation, second_ref) in deviations.iter().zip(&mut seconds) {
			*second_ref += deviation;
		}
		let seconds = seconds;
		
		for window in seconds.windows(FASTEST_JACK_WINDOW_SIZE as usize + 1) {
			let nps = FASTEST_JACK_WINDOW_SIZE as f32 / (window[FASTEST_JACK_WINDOW_SIZE as usize] - window[0]);
			if nps > fastest_jack.speed {
				fastest_jack = FastestComboInfo {
					start_second: window[0],
					end_second: window[FASTEST_JACK_WINDOW_SIZE as usize],
					speed: nps,
					length: FASTEST_JACK_WINDOW_SIZE as u64,
				}
			}
		}
		
		ticks.clear();
		deviations.clear();
	};
	
	let mut mcombo: u64 = 0;
	
	for (&tick, &deviation, &column) in izip!(&ticks, &deviations, &columns) {
		if column < 4 {
			score.notes_per_column[column as usize] += 1;
			
			// Fastest jack statistic
			if deviation.abs() <= 0.180 {
				finger_hits[column as usize].0.push(tick);
				finger_hits[column as usize].1.push(deviation);
			} else {
				trigger_finger_jack_end(&mut finger_hits[column as usize]);
			}
			
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
	}
	trigger_finger_jack_end(&mut finger_hits[0]);
	trigger_finger_jack_end(&mut finger_hits[1]);
	trigger_finger_jack_end(&mut finger_hits[2]);
	trigger_finger_jack_end(&mut finger_hits[3]);
	
	fastest_jack.speed *= rate; // !
	
	let num_notes: u64 = ticks.len() as u64;
	let wife_pts: Vec<f32> = deviations.iter().map(|&d| wife3(d as f32) as f32).collect();
	let are_cbs: Vec<bool> = deviations.iter().map(|d| d.abs() > 0.09).collect();
	let num_manipped_notes = ticks.windows(2).filter(|window| window[0] > window[1]).count();
	
	score.deviation_mean = util::mean(deviations.iter().filter(|d| d.abs() <= 0.09));
	// If the recorded fastest jack speed is 0 nps, then... there was nothing recorded at all and we
	// shouldn't return anything either
	score.fastest_jack = if fastest_jack.speed == 0.0 { None } else { Some(fastest_jack) };
	score.manipulation = num_manipped_notes as f32 / num_notes as f32;
	score.offset_buckets = put_deviations_into_buckets(&deviations);
	
	// need to do this to be able to convert to seconds. this must not be done too early though,
	// because part of the analysis depends on the unsorted-ness of the ticks!
	ticks.sort_unstable();
	
	if let Some(timing_info) = timing_info_maybe {
		// TODO the deviance is not applied yet. E.g. when the player starts tapping early and ending
		// the combo late, the calculated nps is higher than deserved
		let seconds = timing_info.ticks_to_seconds(&ticks);
		
		drop((&wife_pts, &seconds, &are_cbs));
		score.fastest_combo = Some(find_fastest_combo_in_score(&seconds, &are_cbs,
				100, 130, None, rate));
		score.fastest_acc = Some(find_fastest_combo_in_score(&seconds, &are_cbs,
				100, 130, Some(&wife_pts), rate));
	}
	
	return Some(score);
}

// This standard deviation function adheres Bessler's correction! (see comment inside)
fn calculate_standard_deviation(offset_buckets: &[u64], offset_bucket_range: u64) -> f32 {
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
	
	assert_eq!(offset_buckets.len() as u64, 2 * offset_bucket_range + 1);
	
	// util function
	let iter_bucket_contents_and_sizes = || offset_buckets.iter()
			.enumerate()
			.map(|(i, num_values_in_bucket)| (i as i64 - offset_bucket_range as i64, num_values_in_bucket));
	
	let mut values_sum = 0;
	let mut num_values = 0;
	for (value, &num_values_in_bucket) in iter_bucket_contents_and_sizes() {
		values_sum += value * num_values_in_bucket as i64;
		num_values += num_values_in_bucket;
	}
	
	let mean = values_sum / (num_values - 1) as i64;
	
	let mut squared_differences_sum = 0;
	for (value, &num_values_in_bucket) in iter_bucket_contents_and_sizes() {
		let squared_difference = (value - mean).pow(2);
		squared_differences_sum += num_values_in_bucket as i64 * squared_difference;
	}
	
	// Why are we calculating mean by dividing by `n-1` instead of `n`? This practice is called
	// "Bessel's correction". Explanation here: https://stats.stackexchange.com/q/3931
	let squared_differences_mean = squared_differences_sum as f32 / (num_values - 1) as f32;
	
	let standard_deviation = squared_differences_mean.sqrt();
	return standard_deviation;
}

#[pymethods]
impl ReplaysAnalysis {
	#[new]
	pub fn create(prefix: &str, scorekeys: Vec<&str>, wifescores: Vec<f32>,
			packs: Vec<&str>, songs: Vec<&str>,
			rates: Vec<f32>,
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
				.map(|(scorekey, wifescore_ref, pack, song, rate)| {
					let replay_path = prefix.to_string() + scorekey;
					let song_id = crate::SongId { pack: pack.to_string(), song: song.to_string() };
					let timing_info_maybe = timing_info_index.get(&song_id);
					let score = analyze(&replay_path, timing_info_maybe, *rate)?;
					return Some((scorekey, score, *wifescore_ref));
				})
				.collect();
		
		let mut deviation_mean_sum: f32 = 0.0;
		let mut longest_mcombo: u64 = 0;
		let mut longest_mcombo_scorekey: &str = "<no chart>";
		for (i, score_analysis_option) in score_analyses.into_iter().enumerate() {
			let (scorekey, score, wifescore) = some_or_continue!(score_analysis_option);
			
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
				if wifescore < 0.93 {
					analysis.sub_93_offset_buckets[i] += score.offset_buckets[i];
				}
			}
			
			if score.longest_mcombo > longest_mcombo {
				longest_mcombo = score.longest_mcombo;
				longest_mcombo_scorekey = scorekey;
			}
			
			if let Some(score_fastest_combo) = score.fastest_combo {
				if score_fastest_combo.speed > analysis.fastest_combo.speed {
					analysis.fastest_combo = score_fastest_combo;
					analysis.fastest_combo_scorekey = scorekey.to_string();
				}
			}
			
			if let Some(score_fastest_acc) = score.fastest_acc {
				if score_fastest_acc.speed > analysis.fastest_acc.speed {
					analysis.fastest_acc = score_fastest_acc;
					analysis.fastest_acc_scorekey = scorekey.to_string();
				}
			}
			
			if let Some(score_fastest_jack) = score.fastest_jack {
				if score_fastest_jack.speed > analysis.fastest_jack.speed {
					analysis.fastest_jack = score_fastest_jack;
					analysis.fastest_jack_scorekey = scorekey.to_string();
				}
			}
		}
		debug_assert!(analysis.manipulations.len() == analysis.score_indices.len());
		let num_scores = analysis.manipulations.len();
		
		analysis.deviation_mean = deviation_mean_sum / num_scores as f32;
		analysis.longest_mcombo = (longest_mcombo, longest_mcombo_scorekey.into());
		
		analysis.standard_deviation = calculate_standard_deviation(&analysis.offset_buckets,
				OFFSET_BUCKET_RANGE);
		
		return analysis;
	}
} 


#[cfg(test)]
mod tests {
	use super::*;
	use crate::assert_float_eq;
	
	#[test]
	fn test_sm_float_parsing() {
		assert_float_eq!(parse_sm_float(b"-0.018477").unwrap(), -0.018477;
				epsilon=0.00001);
		assert_float_eq!(parse_sm_float(b"1.000000").unwrap(), 1.000000;
				epsilon=0.00001);
		assert_float_eq!(parse_sm_float(b"0.919191").unwrap(), 0.919191;
				epsilon=0.00001);
	}
	
	#[test]
	fn test_find_fastest_note_subset() {
		// This function tests both find_fastest_note_subset and it's wife_pts variant (in which
		// case the wife_pts parameter is a dummy vector filled with 1, so that the wife_pts
		// function should yield identical results to the standard variant). It asserts equality,
		// and also checks if the result length and speed match the expected result
		fn test_the_functions(seconds: &[f32], min_num_notes: u64, max_num_notes: u64,
				expected_length: u64, expected_speed: f32) {
			
			let fastest_subset = find_fastest_note_subset(&seconds,
					min_num_notes, max_num_notes);
			let fastest_wife_pts_subset = find_fastest_note_subset_wife_pts(&seconds,
					min_num_notes, max_num_notes,
					&vec![1.0; seconds.len()]);
			
			assert_eq!(fastest_subset.start_second, fastest_wife_pts_subset.start_second);
			assert_eq!(fastest_subset.end_second, fastest_wife_pts_subset.end_second);
			assert_eq!(fastest_subset.length, fastest_wife_pts_subset.length);
			assert_float_eq!(fastest_subset.speed, fastest_wife_pts_subset.speed;
					epsilon=0.00001);
			
			assert_eq!(fastest_subset.length, expected_length);
			assert_float_eq!(fastest_subset.speed, expected_speed;
					epsilon=0.00001);
		}
		
		let seconds: &[f32] = &[0.0, 3.0, 5.0, 6.0, 8.0];
		test_the_functions(seconds, 2, 99,
				2, 0.66666666666); // should detect [3, 5, 6)
		test_the_functions(seconds, 3, 99,
				3, 0.6); // should detect [3, 5, 6, 8)
		
		// DeltaEpsilon: "Can you find an example where, say, a window of combo 5 will be lower
		// than a window of combo 6." sure, here you go :)
		let seconds: &[f32] = &[0.0, 0.0, 1.0, 2.0, 3.0, 4.0, 4.0];
		test_the_functions(seconds, 5, 6,
				6, 1.5); // note that window size 6 is fastest! not 5
		// when we're restricted to window size 5 at max, the function will obviously not yield
		// the subset with 6 notes. Instead it will be the size-5 window which is, in fact, _slower_
		// than the size-6 window!
		test_the_functions(seconds, 5, 5,
				5, 1.25);
	}
	
	#[test]
	fn test_calculate_standard_deviation() {
		let buckets = [1, 0, 1];
		assert_float_eq!(calculate_standard_deviation(&buckets, 1), 1.4142135623730951;
				epsilon=0.000001);
		
		// taking the values out of the buckets: [-2, -1, -1, 0, 0, 0, 1, 1, 2]
		let buckets = [1, 2, 3, 2, 1];
		assert_float_eq!(calculate_standard_deviation(&buckets, 2), 1.224744871391589;
				epsilon=0.000001);
		
		// these buckets were randomly generated according to a gaussian distribution with sigma=3
		let buckets = [7, 20, 32, 93, 178, 333, 517, 829, 1050, 1230, 1363, 1253, 1072, 807, 558, 319, 178, 94, 43, 17, 4];
		assert_float_eq!(calculate_standard_deviation(&buckets, 10), 3.00175403186607;
				epsilon=0.0001);
	}
}
