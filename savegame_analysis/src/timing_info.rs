use std::path::{PathBuf, Path};
use std::collections::HashMap;
use anyhow::{anyhow, Context, Result};
use walkdir::WalkDir;
use crate::util::extract_str;
use crate::{some_or_continue, ok_or_continue};

#[derive(Debug, PartialEq, Eq, Hash)]
pub struct SongId {
	pack: String,
	song: String,
}

pub type TimingInfoIndex = HashMap<SongId, TimingInfo>;

#[derive(Debug)]
pub struct TimingInfo {
	// List of (beat, bpm). Must be chronologically ordered!
	changes: Vec<(f64, f64)>,
}

impl TimingInfo {
	pub fn from_sm_bpm_string(string: &str) -> Result<Self> {
		// rough capacity approximation
		let mut changes = Vec::with_capacity(string.len() / 13);
		
		for pair in string.split(",") {
			let equal_sign_index = pair.find('=').ok_or(anyhow!("No equals sign in bpms entry"))?;
			let beat: f64 = pair[..equal_sign_index].trim().parse()?;
			let bpm: f64 = pair[equal_sign_index+1..].trim().parse()?;
			changes.push((beat, bpm));
		}
		
		// TODO: sort chronologically!
		
		return Ok(TimingInfo { changes });
	}
}

fn find_sm_like_from_root(base: &Path) -> Result<Vec<PathBuf>> {
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
	return Ok(sm_likes);
}

fn timing_info_from_sm(sm_path: &Path) -> Result<(SongId, TimingInfo)> {
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

pub fn build_timing_info_index(songs_root: &Path) -> Result<TimingInfoIndex> {
	let mut index = TimingInfoIndex::new();
	
	let paths = find_sm_like_from_root(&songs_root)
			.context("Couldn't collect sm-like song paths")?;
	for path in paths {
		let (song_id, timing_info) = match timing_info_from_sm(&path) {
			Ok(a) => a,
			Err(_e) => {
				//~ println!("Couldn't get timing info from sm: {:?}", _e);
				//~ println!();
				continue;
			}
		};
		
		index.insert(song_id, timing_info);
	}
	
	return Ok(index);
} 
