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
	start_second: f64,
	#[pyo3(get)]
	end_second: f64,
	#[pyo3(get)]
	length: u64,
	#[pyo3(get)]
	speed: f64,
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
	// the note subset (with >= 100 notes) with the highest nps (`speed` = nps)
	fastest_combo: Option<FastestComboInfo>,
	// like fastest_combo, but it's only for a single finger, and with a different window -
	// FASTEST_JACK_WINDOW_SIZE - too
	fastest_jack: Option<FastestComboInfo>,
	// like fastest_combo, but `speed` is not simply nps but nps*(wifescore in that window) instead.
	// For example, if you played 10 nps with an accuracy equivalent to 98%, `speed` would be 9.8
	fastest_acc: Option<FastestComboInfo>,
}

// The caller still has to scale the returned nps by the music rate
fn find_fastest_note_subset(seconds: &[f64],
		min_num_notes: u64,
	) -> FastestComboInfo {
	
	let mut fastest = FastestComboInfo {
		start_second: 0.0, end_second: 0.0, length: 0, // dummy values
		speed: 0.0,
	};
	
	if seconds.len() <= min_num_notes as usize { return fastest }
	
	// Do a moving average for every possible subset length (except the large lengths cuz it's
	// unlikely that there'll be something relevant there)
	let end_n = std::cmp::min(seconds.len(), (min_num_notes + NOTE_SUBSET_SEARCH_SPACE_SIZE) as usize);
	for n in (min_num_notes as usize)..end_n {
		for i in 0..=(seconds.len() - n - 1) {
			let end_i = i + n;
			let nps: f64 = (end_i - i) as f64 / (seconds[end_i] - seconds[i]);
			
			if nps > fastest.speed {
				fastest.length = n as u64;
				fastest.start_second = seconds[i];
				fastest.end_second = seconds[end_i];
				fastest.speed = nps;
			}
		}
	}
	
	return fastest;
}

// The caller still has to scale the returned nps by the music rate
fn find_fastest_note_subset_wife_pts(seconds: &[f64],
		min_num_notes: u64,
		wife_pts: &[f64],
	) -> FastestComboInfo {
	
	assert!(wife_pts.len() == seconds.len());
	
	let mut fastest = FastestComboInfo {
		start_second: 0.0, end_second: 0.0, length: 0, // dummy values
		speed: 0.0,
	};
	if seconds.len() <= min_num_notes as usize {
		// If the combo is too short to detect any subset in, return default
		return fastest;
	}
	
	let mut wife_pts_sum_start = wife_pts[0..min_num_notes as usize].iter().sum();
	
	// Do a moving average for every possible subset length
	let end_n = std::cmp::min(seconds.len(), (min_num_notes + NOTE_SUBSET_SEARCH_SPACE_SIZE) as usize);
	for n in (min_num_notes as usize)..end_n {
		// Instead of calculating the sum of the local wife_pts window for every iteration, we keep
		// a variable to it and simply update it on every iteration instead -> that's faster
		let mut wife_pts_sum: f64 = wife_pts_sum_start;
		
		for i in 0..=(seconds.len() - n - 1) {
			let end_i = i + n;
			let mut nps: f64 = (end_i - i) as f64 / (seconds[end_i] - seconds[i]);
			
			nps *= wife_pts_sum / n as f64; // multiply by wife points
			
			if nps > fastest.speed {
				fastest.length = n as u64;
				fastest.start_second = seconds[i];
				fastest.end_second = seconds[end_i];
				fastest.speed = nps;
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

fn find_fastest_combo_in_score(seconds: &[f64], are_cbs: &[bool],
		min_num_notes: u64,
		wife_pts: Option<&[f64]>, // if this is provided, the nps will be multiplied by wife pts
		rate: f64,
	) -> FastestComboInfo {
	
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
				fastest_note_subset = find_fastest_note_subset_wife_pts(combo, min_num_notes, wife_pts_slice);
			} else {
				fastest_note_subset = find_fastest_note_subset(combo, min_num_notes);
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

fn put_deviations_into_buckets(deviations: &[f64]) -> Vec<u64> {
	let mut offset_buckets = vec![0u64; NUM_OFFSET_BUCKETS as usize];
	
	for deviation in deviations {
		let deviation_ms_rounded = (deviation * 1000f64).round() as i64;
		let bucket_index = deviation_ms_rounded + OFFSET_BUCKET_RANGE as i64;
		
		if bucket_index >= 0 && bucket_index < offset_buckets.len() as i64 {
			offset_buckets[bucket_index as usize] += 1;
		}
	}
	
	return offset_buckets;
}

fn parse_replay_file(path: &str) -> Option<(Vec<u64>, Vec<f64>, Vec<u8>)> {
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
		let deviation = &deviation[..deviation.len()-1]; // cut off last digit to speed up float parsing
		let deviation: f64 = ok_or_continue!(lexical::parse_lossy(deviation));
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
		rate: f64
	) -> Option<ScoreAnalysis> {
	
	// ticks is mutable because it needs to be sorted later
	let (mut ticks, deviations, columns) = parse_replay_file(path)?;
	
	let mut score = ScoreAnalysis::default();
	
	// tuple of vectors; first value is tick, first value is deviation
	let mut fastest_jack = FastestComboInfo::default();
	let mut finger_hits: [(Vec<u64>, Vec<f64>); 4] =
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
			let nps = FASTEST_JACK_WINDOW_SIZE as f64 / (window[FASTEST_JACK_WINDOW_SIZE as usize] - window[0]);
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
	let wife_pts: Vec<f64> = deviations.iter().map(|&d| wife3(d)).collect();
	let are_cbs: Vec<bool> = deviations.iter().map(|d| d.abs() > 0.09).collect();
	let num_manipped_notes = ticks.windows(2).filter(|window| window[0] < window[1]).count();
	
	score.deviation_mean = util::mean(deviations.iter().filter(|d| d.abs() <= 0.09));
	// If the recorded fastest jack speed is 0 nps, then... there was nothing recorded at all and we
	// shouldn't return anything either
	score.fastest_jack = if fastest_jack.speed == 0.0 { None } else { Some(fastest_jack) };
	score.manipulation = num_manipped_notes as f64 / num_notes as f64;
	score.offset_buckets = put_deviations_into_buckets(&deviations);
	
	ticks.sort_unstable(); // need to do this to be able to convert to seconds
	
	if let Some(timing_info) = timing_info_maybe {
		// TODO the deviance is not applied yet. E.g. when the player starts tapping early and ending
		// the combo late, the calculated nps is higher than deserved
		let seconds = timing_info.ticks_to_seconds(&ticks);
		
		drop((&wife_pts, &seconds, &are_cbs));
		score.fastest_combo = Some(find_fastest_combo_in_score(&seconds, &are_cbs, 100, None, rate));
		score.fastest_acc = Some(find_fastest_combo_in_score(&seconds, &are_cbs, 100, Some(&wife_pts), rate));
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
				//~ .par_iter()
				.iter()
				// must not filter_map here (need to keep indices accurate)!
				.map(|(scorekey, wifescore_ref, pack, song, rate)| {
					let replay_path = prefix.to_string() + scorekey;
					let song_id = crate::SongId { pack: pack.to_string(), song: song.to_string() };
					let timing_info_maybe = timing_info_index.get(&song_id);
					let score = analyze(&replay_path, timing_info_maybe, *rate)?;
					return Some((scorekey, score, *wifescore_ref));
				})
				.collect();
		
		let mut deviation_mean_sum: f64 = 0.0;
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
		
		analysis.deviation_mean = deviation_mean_sum / num_scores as f64;
		analysis.longest_mcombo = (longest_mcombo, longest_mcombo_scorekey.into());
		
		analysis.standard_deviation = calculate_standard_deviation(&analysis.offset_buckets);
		
		return analysis;
	}
} 
