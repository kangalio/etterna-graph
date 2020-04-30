from typing import *

import os
from itertools import groupby

import numpy as np

import util
from util import parsedate
import app


class PyReplaysAnalysis:
	def __init__(self):
		self.scores = []
		self.datetimes = []
		self.manipulations = []
		self.offset_mean = 0
		self.notes_per_column = [0, 0, 0, 0]
		self.cbs_per_column = [0, 0, 0, 0]
		# ~ self.offset_buckets = {} # TODO: implement this
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
def analyze(xml, replays) -> Optional[PyReplaysAnalysis]:
	from lib_replays_analysis import ReplaysAnalysis as RustReplaysAnalysis
	
	r = PyReplaysAnalysis()
	
	print("start chartkey collection")
	chartkeys: List[str] = []
	for chart in xml.iter("Chart"):
		chartkeys.extend(score.get("Key") for score in chart.iter("Score"))
	
	prefix = os.path.join(replays, "a")[:-1]
	print("starting analysis")
	rustr = RustReplaysAnalysis(prefix, chartkeys)
	print("finished analysis, start transfer")
	
	r.manipulations = rustr.manipulations
	
	if len(r.manipulations) == 0:
		# When no replay could be parsed correctly. For cases when
		# someone selects a legacy folder with 'correct' file names,
		# but unexcepted (legacy) content. Happened to Providence
		r = None
		util.logger.warning("No valid replays found at all in the directory")
		return None
	
	r.offset_mean = rustr.deviation_mean
	r.notes_per_column = rustr.notes_per_column
	r.cbs_per_column = rustr.cbs_per_column
	r.total_notes = sum(r.notes_per_column) # TODO: ehhh do with xml
	r.longest_mcombo = rustr.longest_mcombo
	r.num_near_hits = sum(r.notes_per_column) / sum(r.cbs_per_column)
	
	rust_longest_mcombo = rustr.longest_mcombo
	
	score_indices = rustr.score_indices
	i = -1
	next_index_index = 0
	for chart in xml.iter("Chart"):
		for score in chart.iter("Score"):
			i += 1
			if i == score_indices[next_index_index]:
				next_index_index += 1
				
				if score.get("Key") == rust_longest_mcombo[1]:
					r.longest_mcombo = (rust_longest_mcombo[0], chart)
				r.scores.append(score)
				r.datetimes.append(parsedate(score.findtext("DateTime")))
				if next_index_index >= len(score_indices): break
		else:
			continue
		break
	
	print("finished transfer")
	
	return r
