import numpy as np
import util
from util import parsedate

class ReplaysAnalysis:
	scores = [] # done
	datetimes = [] # done
	manipulations = [] # done
	offset_mean = 0 # done
	notes_per_column = [0, 0, 0, 0] # done
	cbs_per_column = [0, 0, 0, 0] # done
	offset_buckets = {}
	# This could also be implemented by counting the various note scores in 
	# the Etterna.xml, but it's easier to count in the replays.
	total_notes = 0 # done
	longest_mcombo = [0, None] # done
	num_near_hits = 0 # done

# https://stackoverflow.com/a/1066838/9946772
def runs_of_ones_array(bits):
	# make sure all runs of ones are well-bounded
	bounded = np.hstack(([0], bits, [0]))
	# get 1 at run starts and -1 at run ends
	difs = np.diff(bounded)
	run_starts, = np.where(difs > 0)
	run_ends, = np.where(difs < 0)
	return run_ends - run_starts

# This function is responsible for replay analysis. Every chart that 
# uses replay data uses the data generated from this function.
# It works in two phases; first all the data is read from the replay
# files and collected into three long NumPy arrays.
# In the second phase those arrays are analyzed.
def analyze(xml, replays):
	r = ReplaysAnalysis()
	
	# Remember if an exception was already logged to prevent spam logging
	exception_happened = False
	
	# DIY array list implementation for the array holding all values
	capacity = 10_000_000 # Initial array capacity for 10M notes
	length = 0 # Keeps track of how much of the arrays is filled
	all_rows = np.empty(capacity, dtype=np.uint32)
	all_offsets = np.empty(capacity, dtype=np.float32)
	all_columns = np.empty(capacity, dtype=np.uint8)
	
	boundaries = [] # Nested list [[0, 400, 850], [850, 1060], [1060...]...]
	
	# Collect notes into NumPy arrays
	for chart in xml.iter("Chart"):
		score_boundaries = []
		for score in chart.iter("Score"):
			try:
				replay = util.read_replay(replays, score.get("Key"))
				if replay is None: continue
				
				score_boundaries.append(length)
				
				r.scores.append(score)
				r.datetimes.append(parsedate(score.findtext("DateTime")))
				
				for line in replay:
					if not line[0].isdigit(): continue
					tokens = line.split(" ")
					all_rows[length] = int(tokens[0])
					all_offsets[length] = float(tokens[1])
					all_columns[length] = int(tokens[2])
					length += 1
					
					# Dynamically grow array if needed
					if length == capacity:
						capacity *= 2
						all_rows.resize(capacity)
						all_offsets.resize(capacity)
						all_columns.resize(capacity)
			except Exception:
				# Only log once, to avoid spam
				if not exception_happened:
					util.logger.exception("replay analysis")
				exception_happened = True
		score_boundaries.append(length)
		boundaries.append((chart, score_boundaries))
	
	if length == 0:
		# When no replay could be parsed correctly. For cases when
		# someone selects a legacy folder with 'correct' file names,
		# but unexcepted (legacy) content. Happened to Providence
		r = None
		util.logger.warning("No valid replays found at all in the directory")
		return None
	
	# Truncate my DIY ArrayList implementation to the correct length
	all_rows.resize(length)
	all_offsets.resize(length)
	all_columns.resize(length)
	
	# Find the number of notes per column matching the condition
	def get_num_notes_condition(condition=None):
		if condition:
			columns = np.where((condition(all_offsets)), all_columns, 99)
		else:
			columns = all_columns
		keys, values = np.unique(columns, return_counts=True)
		return values[:4]
	
	r.notes_per_column = get_num_notes_condition()
	r.cbs_per_column = get_num_notes_condition(lambda x: abs(x) > 0.09)
	
	r.total_notes = length
	
	great_or_better = abs(all_offsets < 0.09)
	r.num_near_hits = np.count_nonzero(great_or_better)
	r.offset_mean = np.average(all_offsets, weights=great_or_better)
	
	j = 0
	# Per score analysis
	for chart, score_boundaries in boundaries:
		for i in range(0, len(score_boundaries) - 1):
			score = r.scores[j]
			j += 1
			
			# Get the score-relavant data slice from the arrays
			start_index = score_boundaries[i]
			end_index = score_boundaries[i + 1]
			rows = all_rows[start_index:end_index]
			offsets = all_offsets[start_index:end_index]
			columns = all_columns[start_index:end_index]
			
			# Add manipulation value
			manip_proportion = (rows[1:] < rows[:-1]).sum() / rows.size
			r.manipulations.append(manip_proportion)
			
			# Check longest marvelous combo
			mcombos = runs_of_ones_array(abs(offsets) < 0.0225)
			longest_mcombo = mcombos.max() if len(mcombos) else 0
			if longest_mcombo > r.longest_mcombo[0]:
				r.longest_mcombo = [longest_mcombo, chart]
	
	# TODO: implement offset buckets
	
	return r
