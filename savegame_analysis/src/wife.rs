static WIFE3_MINE_HIT_WEIGHT: f32 = -7.0;
static WIFE3_HOLD_DROP_WEIGHT: f32 = -4.5;
static WIFE3_MISS_WEIGHT: f32 = -5.5;

// erf approxmation function, as used in Etterna (same file as in the link below)
fn ett_erf(x: f32) -> f32 {
	let exp = |x| std::f32::consts::E.powf(x);
	
	const A1: f32 = 0.254829592;
	const A2: f32 = -0.284496736;
	const A3: f32 = 1.421413741;
	const A4: f32 = -1.453152027;
	const A5: f32 = 1.061405429;
	const P: f32 = 0.3275911;

	let sign = if x < 0.0 { -1.0 } else { 1.0 };
	let x = x.abs();

	let t = 1.0 / (1.0 + P * x);
	let y = 1.0 - (((((A5 * t + A4) * t) + A3) * t + A2) * t + A1) * t * exp(-x * x);

	return sign * y;
}

// Takes a hit deviation in seconds and returns the wife3 score, scaled to max=2 (!). Sign of
// parameter doesn't matter. This is a Rust translation of
// https://github.com/etternagame/etterna/blob/develop/src/RageUtil/Utils/RageUtil.h#L163
fn wife3_inner(deviation: f32/*, ts: f32*/) -> f32 {
	const TS: f32 = 1.0; // Timing scale = 1 = J4
	
	// so judge scaling isn't so extreme
	const J_POW: f32 = 0.75;
	// min/max points
	const MAX_POINTS: f32 = 2.0;
	// offset at which points starts decreasing(ms)
	let ridic = 5.0 * TS;

	// technically the max boo is always 180ms above j4 however this is
	// immaterial to the end purpose of the scoring curve - assignment of point
	// values
	let max_boo_weight = 180.0 * TS;

	// need positive values for this
	let maxms = (deviation * 1000.0).abs();

	// case optimizations
	if maxms <= ridic {
		return MAX_POINTS;
	}

	// piecewise inflection
	let zero = 65.0 * TS.powf(J_POW);
	let dev = 22.7 * TS.powf(J_POW);

	let score = if maxms <= zero {
		MAX_POINTS * ett_erf((zero - maxms) / dev)
	} else if maxms <= max_boo_weight {
		(maxms - zero) * WIFE3_MISS_WEIGHT / (max_boo_weight - zero)
	} else {
		WIFE3_MISS_WEIGHT
	};
	
	return score;
}

pub fn wife3(deviation: f32) -> f32 {
	 return wife3_inner(deviation) / 2.0; // Divide by two to revert the max=2 scaling
}


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
