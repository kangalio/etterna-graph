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
// returns None. UTF-8 safe too I think, even though it slices on byte indices.
pub fn extract_str<'a>(string: &'a str, before: &str, after: &str) -> Option<&'a str> {
	let before_index = twoway::find_str(string, before)?;
	let start_index = before_index + before.len();
	
	let end_index = start_index + twoway::find_str(&string[start_index..], after)?;
	
	return Some(&string[start_index..end_index]);
}

// The cooler ~~daniel~~ extract_str
pub fn extract_bstr<'a>(string: &'a [u8], before: &[u8], after: &[u8]) -> Option<&'a [u8]> {
	let before_index = twoway::find_bytes(string, before)?;
	let start_index = before_index + before.len();
	
	let end_index = start_index + twoway::find_bytes(&string[start_index..], after)?;
	
	return Some(&string[start_index..end_index]);
}

/// Returns the first element, the last element, and the total number of elements in the given
/// iterator. In case the iterator is empty or has only one element, None is returned instead of
/// the first and last element.
pub fn first_and_last_and_count<I: std::iter::Iterator>(mut iterator: I) -> (Option<(I::Item, I::Item)>, u64) {
	// exception case handling
	let first_elem = match iterator.next() {
		Some(a) => a,
		None => return (None, 0),
	};
	
	// count elements and keep track of last elem
	let mut count = 1; // we got one element already
	let mut last_seen_elem = None;
	for elem in iterator {
		last_seen_elem = Some(elem);
		count += 1;
	}
	
	// exception case handling
	let last_elem = match last_seen_elem {
		Some(a) => a,
		None => return (None, 1),
	};
	
	return (Some((first_elem, last_elem)), count);
}

/// Does exactly what it says on the box
pub fn is_sorted<T: Ord>(data: &[T]) -> bool {
	return data.windows(2).all(|w| w[0] <= w[1]);
}

pub fn trim_bstr(bstr: &[u8]) -> &[u8] {
	let is_not_whitespace = |&c| c != 0x20 && c != 0x09;
	let start_index = match bstr.iter().position(is_not_whitespace) {
		Some(a) => a,
		None => return &bstr[..0], // when there's no non-whitespace char, return empty slice
	};
	let end_index = bstr.iter().rposition(is_not_whitespace).unwrap(); // can't panic
	return &bstr[start_index..=end_index]
}

// I wish I knew how to make this properly generic, over arbitrary number types
pub fn mean<I: Iterator>(iterator: I) -> f32
		where I::Item: std::ops::Deref<Target=f32> {
	
	let mut sum = 0.0;
	let mut count = 0;
	for value in iterator {
		sum += *value;
		count += 1;
	}
	return sum / count as f32;
}
