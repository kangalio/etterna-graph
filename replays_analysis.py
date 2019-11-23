from itertools import groupby
import numpy as np
import util
from util import parsedate

class ReplaysAnalysis:
	def __init__(self):
		self.scores = [] # done
		self.datetimes = [] # done
		self.manipulations = [] # done
		self.offset_mean = 0 # done
		self.notes_per_column = [0, 0, 0, 0] # done
		self.cbs_per_column = [0, 0, 0, 0] # done
		self.offset_buckets = {}
		# This could also be implemented by counting the various note scores in 
		# the Etterna.xml, but it's easier to count in the replays.
		self.total_notes = 0 # done
		self.longest_mcombo = [0, None] # done
		self.num_near_hits = 0 # done

# This function is responsible for replay analysis. Every chart that 
# uses replay data uses the data generated from this function.
# It works in two phases; first all the data is read from the replay
# files and collected into three long NumPy arrays.
# In the second phase those arrays are analyzed.
def analyze(xml, replays):
	r = ReplaysAnalysis()
	
	# Remember if an exception was already logged to prevent spam logging
	exception_happened = False
	
	all_rows, all_offsets, all_columns = [], [], []
	
	boundaries = [] # Nested list [[0, 400, 850], [850, 1060], [1060...]...]
	
	# Collect notes into NumPy arrays
	for chart in xml.iter("Chart"):
		score_boundaries = []
		for score in chart.iter("Score"):
			try:
				replay = util.read_replay(replays, score.get("Key"))
				if replay is None: continue
				
				score_boundaries.append(len(all_rows))
				
				r.scores.append(score)
				r.datetimes.append(parsedate(score.findtext("DateTime")))
				
				for line in replay:
					if not line[0].isdigit(): continue
					tokens = line.split(" ")
					all_rows.append(int(tokens[0]))
					all_offsets.append(float(tokens[1]))
					all_columns.append(int(tokens[2]))
			except Exception:
				# Only log once, to avoid spam
				if not exception_happened:
					util.logger.exception("replay analysis")
				exception_happened = True
		score_boundaries.append(len(all_rows))
		boundaries.append((chart, score_boundaries))
	
	if len(all_rows) == 0:
		# When no replay could be parsed correctly. For cases when
		# someone selects a legacy folder with 'correct' file names,
		# but unexcepted (legacy) content. Happened to Providence
		r = None
		util.logger.warning("No valid replays found at all in the directory")
		return None
	
	all_rows = np.array(all_rows)
	all_offsets = np.array(all_offsets)
	all_columns = np.array(all_columns)
	
	# Find the number of notes per column matching the condition
	def get_num_notes_condition(condition=None):
		if condition:
			# Replace non-matches with column 99. Because this is 4-key
			# only, the 99th column will be sorted out later
			columns = np.where((condition(all_offsets)), all_columns, 99)
		else:
			columns = all_columns
		keys, values = np.unique(columns, return_counts=True)
		return values[:4]
	
	r.notes_per_column = get_num_notes_condition()
	r.cbs_per_column = get_num_notes_condition(lambda x: abs(x) > 0.09)
	
	r.total_notes = all_rows.size
	
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
			mcombos = [len(list(group)) for bit, group in groupby(abs(offsets) < 0.0225) if bit]
			longest_mcombo = max(mcombos) if len(mcombos) else 0
			if longest_mcombo > r.longest_mcombo[0]:
				r.longest_mcombo = [longest_mcombo, chart]
	
	# TODO: implement offset buckets
	
	return r
