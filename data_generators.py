from datetime import datetime, timedelta
import numpy as np
from collections import Counter

from util import parsedate

"""
This file holds all the so-called data generators. Those take save data
and generate scatter points out of them. There are multiple data
generator functions here, one for each scatter plot
"""

# This method does not model the actual game mechanics 100% accurately
def map_wifescore(score):
	try:
		overall = float(next(score.iter("Overall")).text)
		percentage = float(next(score.iter("WifeScore")).text)
		score = overall * percentage / 0.93
		return score
	except: return None

def map_manip(score, replays_dir):
	try: replayfile = open(replays_dir+"/"+score.attrib['Key'])
	except: return None

	times = []
	for line in replayfile.readlines():
		time_str = line.split(" ")[0]
		try: times.append(float(time_str))
		except ValueError: pass

	manipulations = 0
	i = 1
	for t in times[1:]:
		if times[i] < times[i-1]:
			manipulations += 1
		i += 1

	percent_manipulated = manipulations/len(times)*100
	return percent_manipulated

def map_accuracy(score):
	percent = float(score.find("WifeScore").text)*100
	if percent <= -400: return None # Those are weird
	return 100 - percent

sessions_division_cache = {}
def divide_into_sessions(xml, minplays=1):
	global sessions_division_cache
	if minplays in sessions_division_cache:
		return sessions_division_cache[minplays]
	
	session_end_threshold = timedelta(minutes=20)
	
	scores = list(xml.iter("Score"))
	datetimes = [parsedate(s.find("DateTime").text) for s in scores]
	zipped = zip(scores, datetimes)
	zipped = sorted(zipped, key=lambda pair: pair[1])
	
	s_start = datetimes[0]
	current_session = [zipped[0]]
	sessions = []
	for i in range(1, len(zipped)):
		datetime = zipped[i][1]
		if zipped[i][1] - zipped[i-1][1] > session_end_threshold:
			if len(current_session) >= minplays:
				sessions.append(current_session)
			current_session = []
			s_start = zipped[i][1]
		current_session.append(zipped[i])
	
	sessions_division_cache[minplays] = sessions
	return sessions

def gen_session_length(xml):
	sessions = divide_into_sessions(xml)
	result = {s[0][1]: (s[-1][1]-s[0][1]).total_seconds()/60 for s in sessions}
	return (result, sessions)

# Return format: [[a,a...],[b,b...],[c,c...],[d,d...],[e,e...],[f,f...],[g,g...]]
def gen_session_skillsets(xml):
	sessions = divide_into_sessions(xml, minplays=5)
	diffsets = []
	for session in sessions:
		diffset = [0,0,0,0,0,0,0]
		for score in session:
			skillset_ssrs = score[0].find("SkillsetSSRs")
			if skillset_ssrs == None: continue
			diffs = [float(diff.text) for diff in skillset_ssrs[1:]]
			main_diff = diffs.index(max(diffs))
			diffset[main_diff] += 1
		total = sum(diffset)
		if total == 0: continue
		diffset = [diff/total*100 for diff in diffset]
		diffsets.append(diffset)
	return list(zip(*diffsets)) # Transpose

def gen_plays_by_hour(xml):
	from datetime import time
	num_plays = [0] * 24
	for score in xml.iter("Score"):
		datetime = parsedate(score.find("DateTime").text)
		num_plays[datetime.hour] += 1
	
	# I tried to use a datetime as key (would be nicer to display), but
	# it doesn't play nicely with matplotlib, so we need to use an
	# integer to represent the hour of the day.
	#return {time(hour=i): num_plays[i] for i in range(24)}
	return {i: num_plays[i] for i in range(24)}

def gen_session_plays(xml):
	sessions = divide_into_sessions(xml)
	nums_plays = [len(session) for session in sessions]
	nums_sessions_with_x_plays = Counter(nums_plays)
	return nums_sessions_with_x_plays

def gen_chart_play_distr(xml):
	charts_nums_plays = []
	for chart in xml.iter("Chart"):
		score_filter = lambda s: float(s.findtext("WifeScore")) > 0.5
		num_plays = len([s for s in chart.iter("Score") if score_filter(s)])
		if num_plays > 0: charts_nums_plays.append(num_plays)
	
	return Counter(charts_nums_plays)
