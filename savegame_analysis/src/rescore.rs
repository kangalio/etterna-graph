use itertools::izip;


// This function is actually a perfect replica of Etterna's system (except for a single-digit number
// of outliers, I didn't care enough to debug those)
fn original_score(note_seconds: &[f32], hit_seconds: &[f32],
		num_mine_hits: u64, num_hold_drops: u64,
	) -> f32 {
	
	let mut wifescore_sum = 0.0;
	for (&note_second, &hit_second) in izip!(note_seconds, hit_seconds) {
		wifescore_sum += crate::wife3(note_second - hit_second);
	}
	
	let num_misses = note_seconds.len() - hit_seconds.len();
	
	// penalize misses, mine hits, and hold drops
	wifescore_sum += crate::WIFE3_MISS_WEIGHT * num_misses as f32;
	wifescore_sum += crate::WIFE3_MINE_HIT_WEIGHT * num_mine_hits as f32;
	wifescore_sum += crate::WIFE3_HOLD_DROP_WEIGHT * num_hold_drops as f32;
	
	let wifescore = wifescore_sum / note_seconds.len() as f32;
	return wifescore;
}

unsafe fn rescore_inner(note_seconds: &[f32], hit_seconds: &[f32],
		num_mine_hits: u64, num_hold_drops: u64,
	) -> f32 {
	
	// DON'T assert equal length of note_seconds and hit_seconds - this rescoring implementation is
	// supposed to be able to make use of ghost hits - i.e. more hits than notes. or, when you miss
	// a note, the corresponding 'hit' second doesn't show up in hit_seconds at all (cuz, well,
	// there _was_ no 'hit') - i.e. less hits than notes. conclusion: lengths can be different :)
	
	struct Note {
		second: f32,
		assigned_hit: Option<AssignedHit>,
	}
	
	struct AssignedHit {
		hit: *mut Hit,
		deviation: f32,
	}
	
	struct Hit {
		second: f32,
		assigned_note: Option<*const Note>,
	}
	
	impl Hit {
		unsafe fn find_matching_note(&mut self, notes: *mut Vec<Note>) {
			let mut best_note: Option<&mut Note> = None;
			let mut best_deviation = f32::INFINITY;
			
			// Find the best matching note that's either still free, or whose assigned hit is worse
			// than this one.
			for note in &mut *notes {
				let deviation = (note.second - self.second).abs();
				
				if deviation > best_deviation { continue }
				if deviation > 0.180 { continue } // this is too far to be considered a match
				
				println!("Found best note so far at {} (dev={})", note.second, deviation);
				
				if let Some(assigned_hit) = &note.assigned_hit {
					if assigned_hit.deviation < deviation {
						// the note already has an assigned hit that fits even better than this one
						// would, so we leave it be
						//~ println!("Already assigned to something better (dev={}) unfortunately..", assigned_hit.deviation);
						continue;
					}
					
					println!("Already assigned to hit {} (dev={}) but we could overwrite! :)",
							(*assigned_hit.hit).second, assigned_hit.deviation);
				}
				
				best_note = Some(note);
				best_deviation = deviation;
			}
			let best_note: &mut Note = match best_note {
				Some(a) => a,
				None => { // this hit has no place :'( in other words, it's a stray hit
					self.assigned_note = None;
					return
				}
			};
			
			println!("After iterating notes, the best note is at {}", best_note.second);
			
			// Save prev owner for later, so that we can make it find itself a new note later after
			// we assigned ourselves to the note (we can only do it _after_ we assigned ourselves,
			// cuz otherwise it's just gonna pick the same note again)
			let prev_assigned_hit_to_be_relocated: Option<*mut Hit> = best_note.assigned_hit
					.as_ref()
					.map(|assigned_hit| assigned_hit.hit);
			
			// Assign ourselves to the note
			best_note.assigned_hit = Some(AssignedHit { hit: self, deviation: best_deviation });
			self.assigned_note = Some(best_note as *const Note);
			
			// If the note previously had a hit assigned to it, we have just 
			if let Some(prev_assigned_hit_to_be_relocated) = prev_assigned_hit_to_be_relocated {
				println!(">>> Ah yes, it was already assigned. Starting inner re-find...");
				(*prev_assigned_hit_to_be_relocated).find_matching_note(notes);
				println!("<<< Inner re-find done");
			}
		}
	}
	
	let mut notes: Vec<Note> = note_seconds.into_iter()
			.map(|&second| Note { second, assigned_hit: None })
			.collect();
	
	let mut hits: Vec<Hit> = hit_seconds.into_iter()
			.map(|&second| Hit { second, assigned_note: None })
			.collect();
	
	for hit in &mut hits {
		println!("Initial search for hit at {}", hit.second);
		hit.find_matching_note(&mut notes);
		println!("Initial search for hit at {} completed -> {:?}", hit.second,
				hit.assigned_note.map(|n| (*n).second));
		println!(".");
	}
	
	println!(".");
	for hit in &hits {
		println!("Hit {} -> Note {:?}", hit.second, hit.assigned_note.map(|n| (*n).second));
	}
	
	let num_stray_taps = hits.iter().filter(|hit| hit.assigned_note.is_none()).count();
	let num_misses = notes.iter().filter(|note| note.assigned_hit.is_none()).count();
	
	let mut wifescore_sum: f32 = notes.iter()
			.filter_map(|note| note.assigned_hit.as_ref()) // only notes with assigned hits (i.e. notes that were hit)
			.map(|assigned_hit| crate::wife3(assigned_hit.deviation))
			.sum();
	
	// penalize
	wifescore_sum += crate::WIFE3_MISS_WEIGHT * num_misses as f32;
	wifescore_sum += crate::WIFE3_MISS_WEIGHT * num_stray_taps as f32;
	wifescore_sum += crate::WIFE3_MINE_HIT_WEIGHT * num_mine_hits as f32;
	wifescore_sum += crate::WIFE3_HOLD_DROP_WEIGHT * num_hold_drops as f32;
	
	let wifescore = wifescore_sum / notes.len() as f32;
	//~ panic!(); // REMEMBER
	return wifescore;
}

pub fn rescore(note_seconds: &[f32], hit_seconds: &[f32],
		num_mine_hits: u64, num_hold_drops: u64,
	) -> f32 {
	
	return unsafe { rescore_inner(note_seconds, hit_seconds, num_mine_hits, num_hold_drops) };
}

#[cfg(test)]
mod tests {
	use super::*;
	
	#[test]
	fn test_rescore() {
		rescore(&[0.0, 0.1, 0.2, 0.3, 0.4, 0.5],
				&[0.0, 0.07, 0.11, 0.24, 0.32, 0.50],
				0, 0);
	}
}
