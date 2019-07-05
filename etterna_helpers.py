def parse_sm(data):
	bpm = 200
	measure_time = 60/bpm * 4

	# chords: [(int, (bool, bool, bool, bool))]
	chords = []

	def process_measure():
		for (i, row) in enumerate(rows):
			time = measure_i*192 + i*192/len(rows)
			taps = tuple([col in "12" for col in row])
			if taps == (False, False, False, False): continue
			chords.append((time, taps))

	rows = []
	measure_i = 0
	for line in data.splitlines():
		if line.startswith(",") or line.startswith(";"):
			process_measure()
			rows = []
			measure_i += 1
		elif len(line) == 4: rows.append(line)

	return chords
