#[macro_export]
macro_rules! ok_or_continue {
	( $e:expr ) => (
		match $e {
			Ok(value) => value,
			Err(_e) => {
				continue;
			},
		}
	)
}

#[macro_export]
macro_rules! some_or_continue {
	( $e:expr ) => (
		match $e {
			Some(value) => value,
			None => {
				continue
			},
		}
	)
}

pub struct SplitNewlines<'a> {
	bytes: &'a [u8],
	min_line_length: usize,
	current_pos: usize, // the only changing field in here
}

impl<'a> Iterator for SplitNewlines<'a> {
	type Item = &'a [u8];
	
	fn next(&mut self) -> Option<Self::Item> {
		// Check stop condition
		if self.current_pos >= self.bytes.len() {
			return None;
		}
		
		let start_pos = self.current_pos;
		self.current_pos += self.min_line_length; // skip ahead as far as we can get away with
		
		while let Some(&c) = self.bytes.get(self.current_pos) {
			if c == b'\n' { break }
			self.current_pos += 1;
		}
		let line = &self.bytes[start_pos..self.current_pos];
		
		self.current_pos += 1; // Advance one to be on the start of a line again
		return Some(line);
	}
}

// like slice.split(b'\n'), but with optimizations based on a minimum line length assumption
pub fn split_newlines<'a>(bytes: &'a [u8], min_line_length: usize) -> SplitNewlines<'a> {
	return SplitNewlines { bytes, min_line_length, current_pos: 0 };
}

// Extracts a string based on a prefix and a postfix. If prefix or postfix couldn't be found,
// returns None.
pub fn extract_str<'a>(string: &'a str, before: &str, after: &str) -> Option<&'a str> {
	let before_index = string.find(before)?;
	let start_index = before_index + before.len();
	
	let end_index = start_index + string[start_index..].find(after)?;
	
	return Some(&string[start_index..end_index]);
}
