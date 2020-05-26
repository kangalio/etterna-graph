#![allow(unused_imports)]
use std::path::{PathBuf, Path};
use std::collections::HashMap;
use anyhow::{anyhow, Context, Result};
use crate::util::{trim_bstr};
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
	pub fn from_sm_bpm_string(string: &[u8]) -> Result<Self> {
		// rough capacity approximation
		let mut changes = Vec::with_capacity(string.len() / 13);
		
		for pair in string.split(|&c| c == b',') {
			let equal_sign_index = pair.iter().position(|&c| c == b'=')
					.ok_or(anyhow!("No equals sign in bpms entry"))?;
			let beat: f64 = lexical_core::parse_lossy(trim_bstr(&pair[..equal_sign_index]))
					.map_err(|e| anyhow!(format!("{:?}", e)))?;
			let bpm: f64 = lexical_core::parse_lossy(trim_bstr(&pair[equal_sign_index+1..]))
					.map_err(|e| anyhow!(format!("{:?}", e)))?;
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

fn build_timing_info_index_into(cache_db: &Path, index: &mut TimingInfoIndex) -> Result<()> {
	let connection = sqlite::open(cache_db)?;
	let mut statement = connection.prepare("SELECT dir, title, bpms FROM songs")?;
	
	while let sqlite::State::Row = statement.next()? {
		let song_dir: String = ok_or_continue!(statement.read(0));
		let title: String = ok_or_continue!(statement.read(1));
		let bpm_string: String = ok_or_continue!(statement.read(2));
		
		// Turn `/Songs/mizuki/13kaidou/` into `mizuki`
		let song_dir = PathBuf::from(song_dir);
		let pack_name = song_dir.ancestors()
				.nth(1).expect("song doesn't belong to a pack")
				.file_name().expect("double dot as a pack name");
		let pack_name = pack_name.to_string_lossy().into_owned();
		
		let song_id = SongId { pack: pack_name, song: title };
		
		let timing_info = ok_or_continue!(TimingInfo::from_sm_bpm_string(bpm_string.as_bytes()));
		index.insert(song_id, timing_info);
	}
	
	return Ok(());
}

pub fn build_timing_info_index(cache_db: &Path) -> TimingInfoIndex {
	let mut index = TimingInfoIndex::new();
	if let Err(e) = build_timing_info_index_into(cache_db, &mut index) {
		println!("Couldn't built timing info index: {:?}", e);
	}
	return index;
} 
