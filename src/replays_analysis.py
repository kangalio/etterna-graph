from typing import *

import os
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
		self.total_notes = 0 # MOVE THIS!!!
		self.longest_mcombo = (0, None)
		self.num_near_hits = 0 # MOVE THIS!!!

# This function is responsible for replay analysis. Every chart that uses replay data has it from
# here.
# It works by:
# 1) Collecting all chartkeys into a list
# 2) Passing the list to lib_replays_analysis (written in Rust), which evaluates it blazingly fast ™
# 3) Transfer the data from Rusts's ReplaysAnalaysis object to an instance of our ReplaysAnalysis
#    class written in Python
# 3.1) This involves traversing the xml once again, to collect score datetimes and score xml objects
def analyze(xml, replays) -> Optional[ReplaysAnalysis]:
	from lib_replays_analysis import ReplaysAnalysis as RustReplaysAnalysis
	
	r = ReplaysAnalysis()
	
	chartkeys: List[str] = []
	for chart in xml.iter("Chart"):
		chartkeys.extend(score.get("Key") for score in chart.iter("Score"))
	
	prefix = os.path.join(replays, "a")[:-1]
	rustr = RustReplaysAnalysis(prefix, chartkeys)
	
	r.manipulations = rustr.manipulations
	
	if len(r.manipulations) == 0:
		# When no replay could be parsed correctly. For cases when
		# someone selects a legacy folder with 'correct' file names,
		# but unexcepted (legacy) content. Happened to Providence
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
	next_index_index = 0 # this thing is hacky
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
	
	return r
