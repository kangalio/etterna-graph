use itertools::Itertools;
use pyo3::prelude::*;


mod calc_rating {
	fn erfc(x: f32) -> f32 { libm::erfc(x as f64) as f32 }
	
	fn is_rating_okay(rating: f32, ssrs: &[f32]) -> bool {
		let max_power_sum = 2f32.powf(rating / 10.0);
		
		let power_sum: f32 = ssrs.iter()
				.map(|&ssr| 2.0 / erfc(0.1 * (ssr - rating)) - 2.0)
				.filter(|&x| x > 0.0)
				.sum();
		
		return power_sum < max_power_sum;
	}
	
	/*
	The idea is the following: we try out potential skillset rating values
	until we've found the lowest rating that still fits (I've called that
	property 'okay'-ness in the code).
	How do we know whether a potential skillset rating fits? We give each
	score a "power level", which is larger when the skillset rating of the
	specific score is high. Therefore, the user's best scores get the
	highest power levels.
	Now, we sum the power levels of each score and check whether that sum
	is below a certain limit. If it is still under the limit, the rating
	fits (is 'okay'), and we can try a higher rating. If the sum is above
	the limit, the rating doesn't fit, and we need to try out a lower
	rating.
	*/

	pub fn calc_rating(ssrs: &[f32]) -> f32 {
		let mut rating: f32 = 0.0;
		let mut resolution: f32 = 10.24;
		
		// Repeatedly approximate the final rating, with better resolution
		// each time
		while resolution > 0.01 {
			// Find lowest 'okay' rating with certain resolution
			while !is_rating_okay(rating + resolution, ssrs) {
				rating += resolution;
			}
			
			// Now, repeat with smaller resolution for better approximation
			resolution /= 2.0;
		}
		
		return rating * 1.04;
	}
}

#[pyclass]
pub struct SkillTimeline {
	#[pyo3(get)]
	pub rating_vectors: [Vec<f32>; 7],
}

#[pymethods]
impl SkillTimeline {
	#[new]
	// used to be: pub fn create(ssr_vectors: [&[f32]; 7], day_ids: &[u64]) -> Self {
	pub fn create(ssr_vectors: Vec<Vec<f32>>, day_ids: Vec<u64>) -> Self {
		let mut rating_vectors: [Vec<f32>; 7] =
				[vec![], vec![], vec![], vec![], vec![], vec![], vec![]];
		let mut index = 0;
		for (_day_id, day_ids) in &day_ids.iter().group_by(|&&x| x) {
			index += day_ids.count();
			for (i, ssr_vector) in ssr_vectors.iter().enumerate() {
				rating_vectors[i].push(calc_rating::calc_rating(&ssr_vector[..index]));
			}
		}
		
		return SkillTimeline { rating_vectors };
	}
}
