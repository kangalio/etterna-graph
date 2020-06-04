use itertools::izip;

mod matching_scorer;
pub use matching_scorer::MatchingScorer;


pub struct ScoringResult {
	wifescore_sum: f32,
	num_judged_notes: u64,
}

/// Trait for a scorer that operates on a single column and evaluates all hits on that column
pub trait ScoringSystem: Sized {
	/// Create a new scorer, ready to accept and handle hits
	fn setup(note_seconds: &[f32]) -> Self;

	/// Takes a hit by its position in the chart, in seconds. Returns the current scoring result
	fn handle_hit(&mut self, hit_second: f32) -> ScoringResult;

	/// No more hits are coming - finish up and return the final scoring result
	fn finish(self) -> ScoringResult;

	/// This method is a shorthand of the above three in the case that all hits are known already
	fn evaluate(note_seconds: &[f32], hit_seconds: &[f32]) -> ScoringResult {
		let mut scorer = Self::setup(note_seconds);
		for &hit_second in hit_seconds {
			scorer.handle_hit(hit_second);
		}
		return scorer.finish();
	}
}

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

pub fn rescore<S>(note_seconds_columns: &[Vec<f32>; 4], hit_seconds_columns: &[Vec<f32>; 4],
		num_mine_hits: u64, num_hold_drops: u64,
	) -> f32
		where S: ScoringSystem {
	
	let mut wifescore_sum = 0.0;
	let mut num_judged_notes = 0;
	for (note_seconds, hit_seconds) in izip!(note_seconds_columns, hit_seconds_columns) {
		let column_scoring_result = S::evaluate(&note_seconds, &hit_seconds);

		wifescore_sum += column_scoring_result.wifescore_sum;
		num_judged_notes += column_scoring_result.num_judged_notes;
	}

	wifescore_sum += crate::WIFE3_MINE_HIT_WEIGHT * num_mine_hits as f32;
	wifescore_sum += crate::WIFE3_HOLD_DROP_WEIGHT * num_hold_drops as f32;

	let wifescore = wifescore_sum / num_judged_notes as f32;
	return wifescore;
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
