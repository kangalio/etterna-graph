use super::Wife;


const INNER_MISS_WEIGHT: f32 = -8.0;
const INNER_HOLD_DROP_WEIGHT: f32 = -6.0;
const INNER_MINE_HIT_WEIGHT: f32 = -8.0;

pub struct Wife2;

impl Wife for Wife2 {
	const MISS_WEIGHT: f32 = INNER_MISS_WEIGHT / 2.0;
	const HOLD_DROP_WEIGHT: f32 = INNER_HOLD_DROP_WEIGHT / 2.0;
	const MINE_HIT_WEIGHT: f32 = INNER_MINE_HIT_WEIGHT / 2.0;

	fn calc(deviation: f32) -> f32 {
		const TS: f32 = 1.0; // hardcode judge to J4

		let maxms = (deviation * 1000.0).abs();
		let avedeviation = 95.0 * TS;
		let y: f32 = 1.0 - 2.0f32.powf(-maxms * maxms / (avedeviation * avedeviation));
		let y = y.powi(2);
		let score = (2.0 - -8.0) * (1.0 - y) + -8.0;

		return score / 2.0; // revert max=2 scaling
	}	
}
