from PyQt5.QtWidgets import QWidget, QProgressBar
import util
from util import parsedate

class ReplaysAnalysis:
	scores = []
	datetimes = []
	manipulations = []
	offset_mean = 0
	notes_per_column = [0, 0, 0, 0]
	cbs_per_column = [0, 0, 0, 0]
	offset_buckets = {}
	# This could also be implemented by counting the various note scores in 
	# the Etterna.xml, but it's easier to count in the replays.
	total_notes = 0
	longest_combo = [0, None] # Combo variables are lists of `[combo length, chart]`
	longest_mcombo = [0, None]
	num_near_hits = 0

# This function is responsible for replay analysis. Every chart that 
# uses replay data uses the data generated from this function.
def analyze(xml, replays):
	r = ReplaysAnalysis()
	
	#progress_bar = setup_progress_bar()
	
	def do_combo_end(combo, longest):
		global longest_combo, longest_combo_chart
		
		if combo > longest[0]:
			longest[0] = combo
			longest[1] = util.find_parent_chart(xml, score)
	
	# Remember if an exception was already logged to prevent spam logging
	exception_happened = False
	
	print("Collecting scores..")
	scores = list(xml.iter("Score"))
	print("done")
	
	#progress_bar = QProgressBar()
	#progress_bar.setMaximum(len(scores))
	#progress_bar.show()
	
	print("los gehts")
	for i, score in enumerate(scores):
		try:
			replay = util.read_replay(replays, score.get("Key"))
			if replay is None:
				continue
			
			previous_time = 0
			num_total = 0
			num_manipulated = 0
			near_offsets = []
			combo = 0 # Counter for combo
			mcombo = 0 # Counter for marvelous combo
			for line in replay:
				try:
					tokens = line.split(" ")
					time, column = int(tokens[0]), int(tokens[2])
					offset = float(tokens[1])
				except ValueError:
					continue
				
				if time < previous_time: num_manipulated += 1
				previous_time = time
				
				if abs(offset) < 0.1:
					near_offsets.append(offset)
					bucket_key = round(offset * 1000)
					r.offset_buckets[bucket_key] = r.offset_buckets.get(bucket_key, 0) + 1
				
				if abs(offset) > 0.09:
					do_combo_end(combo, r.longest_combo)
					combo = 0
					if column < 4: r.cbs_per_column[column] += 1
				else:
					combo += 1
				
				if abs(offset) > 0.0225:
					do_combo_end(mcombo, r.longest_mcombo)
					mcombo = 0
				else:
					mcombo += 1
				
				if column < 4: r.notes_per_column[column] += 1
				
				num_total += 1
			do_combo_end(combo, r.longest_combo)
			do_combo_end(mcombo, r.longest_mcombo)
			
			r.manipulations.append(num_manipulated / num_total)
			
			r.num_near_hits += len(near_offsets)
			r.offset_mean += sum(near_offsets)
			
			r.scores.append(score)
			r.datetimes.append(parsedate(score.findtext("DateTime")))
			
			r.total_notes += num_total
		except:
			# Only log once, to avoid spam
			if not exception_happened:
				util.logger.exception("replay analysis")
			exception_happened = True
		#progress_bar.setValue(i)
	
	if r.total_notes == 0:
		# When no replay could be parsed correctly. For cases when
		# someone selects a legacy folder with 'correct' file names,
		# but unexcepted (legacy) content. Happened to Providence
		r = None
		util.logger.warning("No valid replays found at all in the directory")
		return None
	
	r.offset_mean /= r.num_near_hits
	
	return r
