use std::path::{PathBuf, Path};
use std::collections::HashMap;
use anyhow::{anyhow, Context, Result};
use walkdir::WalkDir;
use crate::util::extract_str;
use crate::{some_or_continue, ok_or_continue};

#[derive(Debug, PartialEq, Eq, Hash)]
pub struct SongId {
	pub pack: String,
	pub song: String,
}

pub type TimingInfoIndex = HashMap<SongId, TimingInfo>;

#[derive(Debug)]
pub struct BpmChange {
	beat: f64,
	bpm: f64,
}

#[derive(Debug)]
pub struct TimingInfo {
	first_bpm: f64,
	// Must be chronologically ordered!
	changes: Vec<BpmChange>,
}

impl TimingInfo {
	pub fn from_sm_bpm_string(string: &str) -> Result<Self> {
		// rough capacity approximation
		let mut changes = Vec::with_capacity(string.len() / 13);
		
		for pair in string.split(",") {
			let equal_sign_index = pair.find('=').ok_or(anyhow!("No equals sign in bpms entry"))?;
			let beat: f64 = pair[..equal_sign_index].trim().parse()?;
			let bpm: f64 = pair[equal_sign_index+1..].trim().parse()?;
			changes.push(BpmChange { beat, bpm });
		}
		
		changes.sort_by(|a, b| a.beat.partial_cmp(&b.beat).unwrap());
		
		if changes[0].beat != 0.0 {
			return Err(anyhow!(format!("First bpm change is not at beat=0, it's {:?}", changes[0])));
		}
		let first_bpm = changes[0].bpm;
		changes.drain(0..1); // remove first entry (0.0=xxx)
		
		return Ok(TimingInfo { changes, first_bpm });
	}

	/// Input slice must be sorted!
	pub fn ticks_to_seconds(&self, ticks: &[u64]) -> Vec<f64> {
		assert!(crate::util::is_sorted(ticks)); // Parameter validation
		
		let mut cursor_beat: f64 = 0.0;
		let mut cursor_second: f64 = 0.0;
		let mut beat_time = 60.0 / self.first_bpm;
		
		// if a tick lies exactly on the boundary, if will _not_ be processed
		let mut ticks_i = 0;
		let mut seconds_vec = Vec::with_capacity(ticks.len());
		let mut convert_ticks_up_to = |beat: f64, cursor_second: f64, cursor_beat: f64, beat_time: f64| {
			while ticks_i < ticks.len() && ticks[ticks_i] as f64 / 48.0 < beat {
				let beat = ticks[ticks_i] as f64 / 48.0;
				let second = cursor_second + (beat - cursor_beat) * beat_time;
				seconds_vec.push(second);
				
				ticks_i += 1;
			}
		};
		
		for BpmChange { beat: change_beat, bpm: change_bpm } in &self.changes {
			convert_ticks_up_to(*change_beat, cursor_second, cursor_beat, beat_time);
			
			cursor_second += beat_time * (change_beat - cursor_beat);
			cursor_beat = *change_beat;
			beat_time = 60.0 / change_bpm;
		}
		
		// process all remaining ticks (i.e. all ticks coming after the last bpm change
		convert_ticks_up_to(f64::INFINITY, cursor_second, cursor_beat, beat_time);
		
		assert!(ticks.len() == seconds_vec.len()); // If this panics, the above code is wrong
		
		return seconds_vec;
	}
}

fn find_sm_like_from_root(base: &Path) -> Vec<PathBuf> {
	let mut sm_likes = Vec::new();
	
	for chart in WalkDir::new(base)
			.follow_links(true)
			.min_depth(3)
			.max_depth(3) {
		
		let chart = ok_or_continue!(chart);
		if !chart.file_type().is_file() { continue }
		
		let chart = chart.into_path();
		let extension = some_or_continue!(chart.extension());
		if extension == "sm" { // ssc not supported cuz it has split timing -> it's complicated
			sm_likes.push(chart);
		}
	}
	return sm_likes;
}

fn song_id_timing_info_from_sm(sm_path: &Path) -> Result<(SongId, TimingInfo)> {
	fn pack_name_from_sm_path(sm_path: &Path) -> Option<String> {
		let pack_name = sm_path.parent()?.parent()?.file_name()?;
		return Some(pack_name.to_string_lossy().into_owned()); // OsStr to String
	}
	
	// Read file
	let contents = std::fs::read(sm_path)
			.context(format!("Couldn't read sm file {:?}", sm_path))?;
	let contents = String::from_utf8_lossy(&contents);
	
	// Get metadata
	let pack_name = pack_name_from_sm_path(sm_path)
			.ok_or(anyhow!(format!("Couldn't get pack name from {:?}", sm_path)))?;
	let song_name = extract_str(&contents, "#TITLE:", ";")
			.ok_or(anyhow!("No song name found"))?;
	let song_id = SongId { pack: pack_name, song: song_name.to_owned() };
	
	// Get and parse bpm string
	let sm_bpm_string = extract_str(&contents, "#BPMS:", ";")
			.ok_or(anyhow!("No bpm string found"))?;
	let timing_info = TimingInfo::from_sm_bpm_string(sm_bpm_string)
			.context(format!("Failed parsing bpm string {:?}", sm_bpm_string))?;
	
	return Ok((song_id, timing_info));
}

pub fn timing_info_from_sm(sm_path: &Path) -> Result<TimingInfo> {
	return Ok(song_id_timing_info_from_sm(sm_path)?.1);
}

pub fn build_timing_info_index(songs_root: &Path) -> TimingInfoIndex {
	let mut index = TimingInfoIndex::new();
	
	let paths = find_sm_like_from_root(&songs_root);
	for path in paths {
		let (song_id, timing_info) = match song_id_timing_info_from_sm(&path) {
			Ok(a) => a,
			Err(_e) => {
				//~ println!("Couldn't get timing info from sm: {:?}", _e);
				//~ println!();
				continue;
			}
		};
		
		index.insert(song_id, timing_info);
	}
	
	return index;
} 
