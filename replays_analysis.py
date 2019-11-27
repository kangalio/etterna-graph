from itertools import groupby
import numpy as np
import util
from util import parsedate
import app

class ReplaysAnalysis:
	def __init__(self):
		self.scores = []
		self.datetimes = []
		self.manipulations = []
		self.offset_mean = 0
		self.notes_per_column = [0, 0, 0, 0]
		self.cbs_per_column = [0, 0, 0, 0]
		self.offset_buckets = {} # TODO: implement this
		# This could also be implemented by counting the notes of
		# the Etterna.xml, but it's easier to count in the replays.
		self.total_notes = 0
		self.longest_mcombo = (0, None)
		self.num_near_hits = 0

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
	
	# Happens when a marvelous combo ends
	def do_mcombo_end():
		if mcombo > r.longest_mcombo[0]:
			r.longest_mcombo = (mcombo, chart)
	
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
				
				# Variables for the manipulation analysis
				num_manipulated = 0
				num_total = 0
				previous_row = -1
				
				# Variable for longest marvelous combo analysis
				mcombo = 0
				
				for line in replay:
					if not line[0].isdigit(): continue
					tokens = line.split(" ")
					
					row = int(tokens[0])
					offset = float(tokens[1])
					all_rows.append(row)
					all_offsets.append(offset)
					all_columns.append(int(tokens[2]))
					
					if row < previous_row:
						num_manipulated += 1
					num_total += 1
					previous_row = row
					
					if abs(offset) < 0.0225:
						mcombo += 1
					else:
						do_mcombo_end()
						mcombo = 0
				
				do_mcombo_end()
				
				manip_proportion = num_manipulated / num_total
				r.manipulations.append(manip_proportion)
				
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
	
	# TODO: implement offset buckets
	
	return r
