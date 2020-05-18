#[macro_export]
macro_rules! ok_or_continue {
	( $e:expr ) => (
		//~ $e.unwrap()
		match $e {
			Ok(value) => value,
			Err(_e) => {
				//~ println!("skipped because of Err {:?}", _e);
				continue;
			},
		}
	)
}

#[macro_export]
macro_rules! some_or_continue {
	( $e:expr ) => (
		//~ $e.unwrap()
		match $e {
			Some(value) => value,
			None => {
				//~ println!("skipped because of None");
				continue
			},
		}
	)
}

// like slice.split(b'\n'), but with optimizations based on a minimum line length assumption
mod split_newlines {
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
	
	pub fn split_newlines<'a>(bytes: &'a [u8], min_line_length: usize) -> SplitNewlines<'a> {
		return SplitNewlines { bytes, min_line_length, current_pos: 0 };
	}
}
pub use split_newlines::split_newlines;
