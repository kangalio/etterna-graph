use super::Wife;


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

pub struct Wife3;

impl Wife3 {
	const INNER_MINE_HIT_WEIGHT: f32 = -7.0;
	const INNER_HOLD_DROP_WEIGHT: f32 = -4.5;
	const INNER_MISS_WEIGHT: f32 = -5.5;

	// Takes a hit deviation in seconds and returns the wife3 score, scaled to max=2 (!). Sign of
	// parameter doesn't matter. This is a Rust translation of
	// https://github.com/etternagame/etterna/blob/develop/src/RageUtil/Utils/RageUtil.h#L163
	fn calc_inner(deviation: f32/*, ts: f32*/) -> f32 {
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
			(maxms - zero) * Self::INNER_MISS_WEIGHT / (max_boo_weight - zero)
		} else {
			Self::INNER_MISS_WEIGHT
		};
		
		return score;
	}
}

impl Wife for Wife3 {
	// wrap the actual constants to revert the max=2 scaling
	const MINE_HIT_WEIGHT: f32 = Self::INNER_MINE_HIT_WEIGHT / 2.0;
	const HOLD_DROP_WEIGHT: f32 = Self::INNER_HOLD_DROP_WEIGHT / 2.0;
	const MISS_WEIGHT: f32 = Self::INNER_MISS_WEIGHT / 2.0;

	fn calc(deviation: f32) -> f32 {
		return Self::calc_inner(deviation) / 2.0; // Divide by two to revert the max=2 scaling
	}
}