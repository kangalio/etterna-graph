from typing import *

import os
from itertools import groupby

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
		self.sub_93_offset_buckets = {}

# This function is responsible for replay analysis. Every chart that uses replay data has it from
# here.
# It works by:
# 1) Collecting all chartkeys into a list
# 2) Passing the list to lib_replays_analysis (written in Rust), which evaluates it blazingly fast™
# 3) Transfer the data from Rusts's ReplaysAnalaysis object to an instance of our ReplaysAnalysis
#    class written in Python
# 3.1) This involves traversing the xml once again, to collect score datetimes and score xml objects
def analyze(xml, replays) -> Optional[ReplaysAnalysis]:
	import savegame_analysis
	
	r = ReplaysAnalysis()
	
	chartkeys: List[str] = []
	wifescores: List[float] = []
	for chart in xml.iter("Chart"):
		for score in chart.iter("Score"):
			chartkeys.append(score.get("Key"))
			wifescores.append(float(score.findtext("SSRNormPercent")))
	
	prefix = os.path.join(replays, "a")[:-1]
	rustr = savegame_analysis.ReplaysAnalysis(prefix, chartkeys, wifescores)
	
	r.manipulations = rustr.manipulations
	
	if len(r.manipulations) == 0:
		# When no replay could be parsed correctly. For cases when
		# someone selects a legacy folder with 'correct' file names,
		# but unexcepted (legacy) content. Happened to Providence
		util.logger.warning("No valid replays found at all in the directory")
		return None
	
	# this is NOT part of replays analysis. this is xml analysis. this is in here anyway because
	# it's easier. this should really be moved into a separate xml analysis module (in case I'll
	# ever get around implementing that...?)
	r.total_notes = 0
	for tap_note_scores in xml.iter("TapNoteScores"):
		judgements = ["Miss", "W1", "W2", "W3", "W4", "W5"]
		r.total_notes += sum(int(tap_note_scores.findtext(x)) for x in judgements)
	
	r.offset_mean = rustr.deviation_mean
	r.notes_per_column = rustr.notes_per_column
	r.cbs_per_column = rustr.cbs_per_column
	r.longest_mcombo = rustr.longest_mcombo
	r.num_near_hits = sum(r.notes_per_column) / sum(r.cbs_per_column)
	
	for i, num_hits in enumerate(rustr.sub_93_offset_buckets):
		r.sub_93_offset_buckets[i - 180] = num_hits
	
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
