use itertools::izip;

mod matching_scorer;
pub use matching_scorer::MatchingScorer;

mod naive_scorer;
pub use naive_scorer::NaiveScorer;


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
}

/// Trait for a scorer that operates on a single column and evaluates all hits on that column - but
/// it needs the entire list of hits available to it at the same time
pub trait OneShotScoringSystem: Sized {
	fn evaluate(note_seconds: &[f32], hit_seconds: &[f32]) -> ScoringResult;
}

impl<S> OneShotScoringSystem for S where S: ScoringSystem {
	fn evaluate(note_seconds: &[f32], hit_seconds: &[f32]) -> ScoringResult {
		let mut scorer = Self::setup(note_seconds);
		for &hit_second in hit_seconds {
			scorer.handle_hit(hit_second);
		}
		return scorer.finish();
	}
}

pub fn rescore<S>(note_seconds_columns: &[Vec<f32>; 4], hit_seconds_columns: &[Vec<f32>; 4],
		num_mine_hits: u64, num_hold_drops: u64,
	) -> f32
		where S: OneShotScoringSystem {
	
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
