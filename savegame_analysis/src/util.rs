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

pub struct CountInto<'a, I: Iterator> {
	iterator: I,
	count_variable: &'a mut usize,
}

impl<'a, I: Iterator> Iterator for CountInto<'a, I> {
	type Item = I::Item;

	fn next(&mut self) -> Option<I::Item> {
		let item = self.iterator.next();
		if item.is_some() {
			*self.count_variable += 1;
		}
		return item;
	}
}

pub trait MyItertools {
	fn count_into(self, count_variable: &mut usize) -> CountInto<Self>
			where Self: Iterator, Self: Sized;
}

impl<I: Iterator> MyItertools for I {
	// This function counts the number of elements in the iterator without consuming the iterator
	fn count_into(self, count_variable: &mut usize) -> CountInto<Self> {
		*count_variable = 0;
		return CountInto { iterator: self, count_variable };
	}
}

// Like slice.split(b'\n'), but with optimizations based on a minimum line length assumption
// When min_line_length is zero, the expected result for "xxx\n" would be ["xxx", ""]. However,
// the result is gonna be just ["xxx"]. I know it's unintuitive, but I dunno how to fix
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
	let start_index = match bstr.iter().position(|&c| !is_ascii_whitespace(c)) {
		Some(a) => a,
		None => return &bstr[..0], // when there's no non-whitespace char, return empty slice
	};
	let end_index = bstr.iter().rposition(|&c| !is_ascii_whitespace(c)).unwrap(); // can't panic
	return &bstr[start_index..=end_index]
}

// I wish I knew how to make this properly generic, over arbitrary number types
pub fn mean<I: Iterator>(iterator: I) -> f32
		where I::Item: std::ops::Deref<Target=f32> {
	
	let mut sum = 0.0;
	let mut count = 0;
	for value_ref in iterator {
		sum += *value_ref;
		count += 1;
	}
	return sum / count as f32;
}

pub fn is_ascii_whitespace(c: u8) -> bool {
	return c == b' ' || c == b'\t' || c == b'\n' || c == b'\r'
			|| c == 0x0c // form feed; an ASCII control symbol for a page break
			|| c == 0x0b; // vertical tab
}

pub fn longest_true_sequence<I>(iterator: I) -> u64
		where I: Iterator<Item=bool> {
	
	let mut longest_so_far = 0;
	let mut current_run = 0;
	for is_true in iterator {
		if is_true {
			current_run += 1;
		} else {
			if current_run > longest_so_far {
				longest_so_far = current_run;
				current_run = 0;
			}
		}
	}

	if current_run > longest_so_far {
		longest_so_far = current_run;
	}

	return longest_so_far;
}

#[cfg(test)]
mod tests {
	use super::*; // Use all functions above
	
	// Util function, other tests use this
	#[macro_export]
	macro_rules! assert_float_eq {
		($left: expr, $right: expr; epsilon = $epsilon: expr) => (
			// Evaluate expressions
			let left = $left;
			let right = $right;
			let delta = (right - left).abs();
			
			if delta > $epsilon {
				panic!("assertion failed: `(left =~ right)`
						  left: `{:?}`
						 right: `{:?}`
						 delta: `{:?}`",
						&left, &right, &delta);
			}
		)
	}
	
	#[test]
	fn test_split_newlines() {
		let text = b"10charssss\n6chars\n10charssss\n6chars\n";
		let lines: Vec<_> = split_newlines(text as &[u8], 6).collect();
		assert_eq!(lines, vec![b"10charssss" as &[u8], b"6chars" as &[u8], b"10charssss" as &[u8],
							   b"6chars" as &[u8]]);
		
		let lines: Vec<&[u8]> = split_newlines(text as &[u8], 7).collect();
		assert_eq!(lines, vec![b"10charssss" as &[u8], b"6chars\n10charssss" as &[u8],
							   b"6chars\n" as &[u8]]); // we expect the \n in here because it's
													   // covered by the skip-ahead length of 7
	}
	
	#[test]
	fn test_extract_str_and_bstr() {
		for (string, before, after, expected_outcome) in [
				("#TITLE:helo;", "#TITLE:", ";", Some("helo")),
				("#TITLE::::#TITLE:;", "#TITLE:", ";", Some(":::#TITLE:")),
				("#TITLE:helo:", "#TITLE:", ";", None),
				("#TITLE helo;", "#TITLE:", ";", None),
				].iter() {
			
			assert_eq!(extract_str(string, before, after), *expected_outcome);
			assert_eq!(extract_bstr(string.as_bytes(), before.as_bytes(), after.as_bytes()),
					expected_outcome.map(|s| s.as_bytes()));
		}
	}
	
	#[test]
	fn test_first_and_last_and_count() {
		assert_eq!(first_and_last_and_count("2357".chars()), (Some(('2', '7')), 4));
		assert_eq!(first_and_last_and_count("2".chars()), (None, 1));
		assert_eq!(first_and_last_and_count("".chars()), (None, 0));
	}
	
	#[test]
	fn test_is_sorted() {
		assert_eq!(is_sorted(&[1, 2, 3, 2]), false);
		assert_eq!(is_sorted(&[1, 2, 2, 3]), true);
	}
	
	#[test]
	fn test_trim_bstr() {
		assert_eq!(trim_bstr(b" hello world   "), b"hello world");
		assert_eq!(trim_bstr(b"hello world   "), b"hello world");
		assert_eq!(trim_bstr(b" hello world"), b"hello world");
		assert_eq!(trim_bstr(b"hello world"), b"hello world");
		assert_eq!(trim_bstr(b" hello world \n\n \t"), b"hello world");
	}
	
	#[test]
	fn test_mean() {
		assert_float_eq!(mean([0.0, 6.0, 1.0, 2.0].iter()), 2.25;
				epsilon=0.0001);
		assert_float_eq!(mean([0.0, 6.0, 1.0, 3.0].iter()), 2.5;
				epsilon=0.0001);
		assert_float_eq!(mean([-897193848.0, 69.0, 893784444.0, 211122.0, 422.0].iter()), -639558.2;
				epsilon=10.0); // heh, what a large epsilon value. needed though
	}
	
	#[test]
	fn test_is_ascii_whitespace() {
		let whitespace_chars: &[u8] = b" \t\n\r\x0c\x0b";
		for char_code in 0..=255u8 {
			assert_eq!(is_ascii_whitespace(char_code), whitespace_chars.contains(&char_code));
		}
	}
}
