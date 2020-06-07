mod wife2;
pub use wife2::*;
mod wife3;
pub use wife3::*;


const INNER_STRAY_WEIGHT: f32 = -5.5; // this is an extension from me
pub const STRAY_WEIGHT: f32 = INNER_STRAY_WEIGHT / 2.0;

pub trait Wife {
	const MINE_HIT_WEIGHT: f32;
	const HOLD_DROP_WEIGHT: f32;
	const MISS_WEIGHT: f32;

	fn calc(deviation: f32) -> f32;

	// Misses must be present in the `deviations` slice in form of a `1.000000` value
	fn apply(deviations: &[f32], num_mine_hits: u64, num_hold_drops: u64) -> f32 {
		let mut wifescore_sum = 0.0;
		for &deviation in deviations {
			if (deviation - 1.0).abs() < 0.0001 { // it's a miss
				wifescore_sum += Self::MISS_WEIGHT;
			} else {
				wifescore_sum += Self::calc(deviation);
			}
		}

		wifescore_sum += num_mine_hits as f32 * Self::MINE_HIT_WEIGHT;
		wifescore_sum += num_hold_drops as f32 * Self::HOLD_DROP_WEIGHT;

		return wifescore_sum / deviations.len() as f32;
	}
}

pub fn wife2(deviation: f32) -> f32 { Wife2::calc(deviation) }
pub fn wife3(deviation: f32) -> f32 { Wife3::calc(deviation) }

#[cfg(test)]
mod tests {
	use super::*; // Use all functions above
	use crate::assert_float_eq;
	
	#[test]
	fn test_ett_erf() {
		for (x, expected_value) in [
				(-2.0, -0.995322265019),
				(-1.0, -0.84270079295),
				(0.0, 0.0),
				(1.0, 0.84270079295),
				(1.5, 0.966105146475),
				(2.0, 0.995322265019),
				(4.0, 0.999999984583)].iter() {
			
			assert_float_eq!(ett_erf(*x), *expected_value; epsilon=0.0001);
		}
	}
	
	#[test]
	fn test_wife3() {
		for (x, expected_value) in [
				(0.004, 1.0000000000),
				(0.014, 0.9985134006),
				(0.024, 0.9893599749),
				(0.054, 0.5068465471),
				(0.064, 0.0496764779),
				(0.074, -0.2152173966),
				(0.174, -2.6065220833),
				(0.184, -2.7500000000),
				(0.194, -2.7500000000)].iter() {
			
			assert_float_eq!(wife3(*x), *expected_value; epsilon=0.0001);
		}
	}
}
