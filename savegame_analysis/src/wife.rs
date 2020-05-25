static WIFE3_MINE_HIT_WEIGHT: f64 = -7.0;
static WIFE3_HOLD_DROP_WEIGHT: f64 = -4.5;
static WIFE3_MISS_WEIGHT: f64 = -5.5;

// Takes a hit deviation in sseconds and returns the wife3 score, scaled to max=1. This is a Rust
// translation of
// https://github.com/etternagame/etterna/blob/develop/src/RageUtil/Utils/RageUtil.h#L163
pub fn wife3(deviation: f64/*, ts: f64*/) -> f64 {
	static TS: f64 = 1.0; // Timing scale = 1 = J4
	
	// so judge scaling isn't so extreme
	static J_POW: f64 = 0.75;
	// min/max points
	static MAX_POINTS: f64 = 2.0;
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
		MAX_POINTS * libm::erfc((zero - maxms) / dev)
	} else if maxms <= max_boo_weight {
		(maxms - zero) * WIFE3_MISS_WEIGHT / (max_boo_weight - zero)
	} else {
		WIFE3_MISS_WEIGHT
	};
	
	return score / 2.0; // Revert the max=2 scaling
} 
