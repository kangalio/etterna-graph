use itertools::izip;


pub fn rescore(note_seconds: &[f32], hit_seconds: &[f32], deviations: &[f32]) -> f32 {
	let mut wifescore_sum = 0.0;
	for (&note_second, &hit_second, &deviation) in izip!(note_seconds, hit_seconds, deviations) {
		let my_deviation = hit_second - note_second;
		wifescore_sum += crate::wife3(note_second - hit_second);
	}
	
	let wifescore = wifescore_sum / note_seconds.len() as f32;
	return wifescore;
} 
