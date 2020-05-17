use itertools::Itertools;
use pyo3::prelude::*;


mod calc_rating {
	fn is_rating_okay(rating: f64, ssrs: &[f64]) -> bool {
		let max_power_sum = 2f64.powf(rating / 10.0);
		
		let mut power_sum = 0.0;
		for ssr in ssrs {
			let power_sum_addendum = 2.0 / libm::erfc((ssr - rating) / 10.0) - 2.0;
			if power_sum_addendum > 0.0 {
				power_sum += power_sum_addendum;
			}
		}
		return power_sum < max_power_sum;
	}
	
	pub fn calc_rating(ssrs: &[f64]) -> f64 {
		let mut rating: f64 = 0.0;
		let mut resolution: f64 = 10.24;
		
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
		
		return rating;
	}
}

#[pyclass]
pub struct SkillTimeline {
	#[pyo3(get)]
	pub rating_vectors: [Vec<f64>; 7],
}

#[pymethods]
impl SkillTimeline {
	#[new]
	// used to be: pub fn create(ssr_vectors: [&[f64]; 7], day_ids: &[u64]) -> Self {
	pub fn create(ssr_vectors: Vec<Vec<f64>>, day_ids: Vec<u64>) -> Self {
		let mut rating_vectors: [Vec<f64>; 7] =
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
