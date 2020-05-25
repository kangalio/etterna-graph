use std::path::PathBuf;
use itertools::{izip/*, Itertools*/};
use rayon::prelude::*;
use pyo3::prelude::*;
use crate::{ok_or_continue, some_or_continue};
use crate::util::split_newlines;
use crate::wife::wife3;


// IMPORTANT ANNOUNCE FOR WIFE POINTS:
// In this crate, wife points are scaled to a maximum of 1 (not 2 like in the Etterna source code)!

static OFFSET_BUCKET_RANGE: u64 = 180;
static NUM_OFFSET_BUCKETS: u64 = 2 * OFFSET_BUCKET_RANGE + 1;

static FASTEST_JACK_WINDOW_SIZE: u64 = 30;

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
	// like offset_buckets, but for, well, sub 93% scores only
	sub_93_offset_buckets: Vec<u64>,
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
		wife_pts: Option<&[f64]>, // if this is provided, the nps will be multiplied by wife pts
	) -> FastestComboInfo {
	
	let mut fastest = FastestComboInfo {
		start_second: 0.0, end_second: 0.0, length: 0, // dummy values
		speed: 0.0,
	};
	
	if seconds.len() <= min_num_notes as usize { return fastest }
	
	// Do a moving average for every possible subset length
	for n in (min_num_notes as usize)..=(seconds.len() - 1) {
		// Instead of calculating the sum of the local wife_pts window for every iteration, we keep
		// a variable to it and simply update it on every iteration instead -> that's faster
		let mut wife_pts_sum: f64 = 0.0; // that default value won't be used
		if let Some(wife_pts) = wife_pts {
			wife_pts_sum = wife_pts[0..n].iter().sum();
		}
		
		for i in 0..=(seconds.len() - n - 1) {
			let end_i = i + n;
			let mut nps: f64 = (end_i - i) as f64 / (seconds[end_i] - seconds[i]);
			
			if let Some(wife_pts) = wife_pts {
				nps *= wife_pts_sum / wife_pts.len() as f64; // multiply by wife points
			}
			
			if nps > fastest.speed {
				fastest.length = n as u64;
				fastest.start_second = seconds[i];
				fastest.end_second = seconds[end_i];
				fastest.speed = nps;
			}
			
			if let Some(wife_pts) = wife_pts {
				// Move the wife_pts_sum window one place forward
				wife_pts_sum -= wife_pts[i];
				wife_pts_sum += wife_pts[end_i];
			}
		}
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
			let fastest_note_subset = find_fastest_note_subset(combo, min_num_notes, wife_pts);
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

// Analyze a single score's replay
fn analyze(path: &str, wifescore: f64, timing_info_maybe: Option<&crate::TimingInfo>, rate: f64)
		-> Option<ScoreAnalysis> {
	
	//~ if path != "/home/kangalioo/.etterna/Save/ReplaysV2/S91eb16d4c95874509b52426eb38c33d2da2286ac" {
		//~ return None;
	//~ }
	
	let bytes = std::fs::read(path).ok()?;
	let approx_max_num_lines = bytes.len() / 16; // 16 is a pretty good value for this
	
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
	let mut wife_pts = Vec::with_capacity(approx_max_num_lines); // wife points, scaled to max=1
	
	for line in split_newlines(&bytes, 5) {
		if line.len() == 0 || line[0usize] == b'H' { continue }
		
		let mut token_iter = line.splitn(3, |&c| c == b' ');
		
		let tick = token_iter.next().expect("Missing tick token");
		let tick: u64 = ok_or_continue!(btoi::btou(tick));
		let deviation = token_iter.next().expect("Missing tick token");
		let deviation: f64 = ok_or_continue!(lexical::parse_lossy(&deviation));
		// remainder has the rest of the string in one slice, without any whitespace info or such.
		// luckily we know the points of interest's exact positions, so we can just directly index
		// into the remainder string to get what we need
		let remainder = token_iter.next().expect("Missing tick token");
		let column: u64 = (remainder[0] - b'0') as u64;
		let note_type: u64 = if remainder.len() >= 3 { (remainder[2] - b'0') as u64 } else { 1 };
		if note_type != 1 { continue } // We don't want hold ends, mines, lifts etc
		
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
		wife_pts.push(wife3(deviation));
		
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
	trigger_finger_jack_end(&mut finger_hits[0]);
	trigger_finger_jack_end(&mut finger_hits[1]);
	trigger_finger_jack_end(&mut finger_hits[2]);
	trigger_finger_jack_end(&mut finger_hits[3]);
	
	fastest_jack.speed *= rate; // !
	// If the recorded fastest jack speed is 0 nps, then... there was nothing recorded at all and we
	// shouldn't return anything either
	score.fastest_jack = if fastest_jack.speed == 0.0 { None } else { Some(fastest_jack) };
	
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
				.par_iter()
				//~ .iter()
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
		for (i, score_analysis_option) in score_analyses.into_iter().enumerate() {
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
