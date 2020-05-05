use minidom::{Element, node::Node};
use itertools::Itertools;


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

trait XmlUtil {
	fn find(&self, name: &str) -> Option<&Self>;
	fn string(&self) -> Option<&str>;
}

impl XmlUtil for Element {
	fn find(&self, name: &str) -> Option<&Self> {
		for child in self.children() {
			if child.name() == name {
				return Some(child);
			}
		}
		return None
	}
	
	// Returns None if there are no child nodes or if the first child node is not a text node
	fn string(&self) -> Option<&str> {
		match self.nodes().next()? {
			Node::Text(string) => return Some(&string),
			_ => return None,
		}
	}
}

#[derive(Debug)]
pub struct SkillTimeline {
	pub day_vector: Vec<String>,
	pub rating_vectors: [Vec<f64>; 7],
}

impl SkillTimeline {
	fn get_scores(xml: &Element) -> Vec<&Element> {
		let mut scores = Vec::with_capacity(5000); // idk if that's a good capacity
		for section in xml.children() {
			if section.name() != "PlayerScores" { continue }
			for chart in section.children() {
				for scores_at in chart.children() {
					for score in scores_at.children() {
						scores.push(score);
					}
				}
			}
		}
		return scores;
	}
	
	fn add_score_to_vecs(ssr_vectors: &mut [Vec<f64>; 7], score: &Element) -> Option<()> {
		let skillset_ssrs = score.find("SkillsetSSRs")?;
		for skillset_elem in skillset_ssrs.children() {
			let value: f64 = skillset_elem.string()?.parse().ok()?;
			match skillset_elem.name() {
				"Stream" => ssr_vectors[0].push(value),
				"Jumpstream" => ssr_vectors[1].push(value),
				"Handstream" => ssr_vectors[2].push(value),
				"Stamina" => ssr_vectors[3].push(value),
				"JackSpeed" => ssr_vectors[4].push(value),
				"Chordjack" => ssr_vectors[5].push(value),
				"Technical" => ssr_vectors[6].push(value),
				_ => {} // can only be Overall, which we don't care about
			}
		}
		return Some(());
	}
	
	pub fn create(xml_path: &str) -> Self {
		let contents = std::fs::read_to_string(xml_path).expect("File read error");
		println!("parsing...");
		let xml = contents.parse().expect("XML parsing error");
		println!("done");
		
		let mut scores = Self::get_scores(&xml);
		scores.sort_unstable_by_key(|score| score.find("DateTime").expect("").string());
		
		let mut ssr_vectors: [Vec<f64>; 7] =
				[vec![], vec![], vec![], vec![], vec![], vec![], vec![]];
		let mut rating_vectors: [Vec<f64>; 7] =
				[vec![], vec![], vec![], vec![], vec![], vec![], vec![]];
		let mut day_vector: Vec<String> = vec![];
		for (day, scores) in &scores.iter()
				.group_by(|score| &score.find("DateTime").unwrap().string().unwrap()[..10]) {
			
			day_vector.push(day.to_owned());
			
			for score in scores {
				Self::add_score_to_vecs(&mut ssr_vectors, score); // returns None if it fails
			}
			
			for (i, ssr_vector) in ssr_vectors.iter().enumerate() {
				rating_vectors[i].push(calc_rating::calc_rating(&ssr_vector));
			}
		}
		
		return SkillTimeline { day_vector, rating_vectors };
	}
}
