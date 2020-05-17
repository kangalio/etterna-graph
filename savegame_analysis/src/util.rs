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
