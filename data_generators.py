from datetime import datetime, timedelta
import numpy as np
from collections import Counter
import math

import util
from util import parsedate

"""
This file holds all the so-called data generators. Those take save data
and generate scatter points out of them. There are multiple data
generator functions here, one for each scatter plot
"""

# This method does not model the actual game mechanics 100% accurately
def map_wifescore(score):
	overall = float(score.findtext(".//Overall"))
	percentage = float(score.findtext("WifeScore"))
	return overall * percentage / 0.93

def map_manip(score, replays):
	replayfile = replays.get(score.attrib.get("Key"))
	if replayfile is None: return None
	
	num_manipulations, num_total = 0, 0
	previous_time = 0
	for line in replayfile:
		try: time = float(line.split(" ")[0])
		except ValueError: continue
		
		if time < previous_time: num_manipulations += 1
		num_total += 1
		
		previous_time = time
	
	percent_manipulated = num_manipulations / num_total * 100
	percent_manipulated = max(percent_manipulated, 0.01) # Clamp
	return math.log(percent_manipulated) / math.log(10)

def map_accuracy(score):
	percent = float(score.find("WifeScore").text)*100
	if percent <= -400: return None # Those are weird
	if percent > 100: return None
	return -(math.log(100 - percent) / math.log(10))

def map_scores(xml, mapper, *mapper_args, discard_errors=True):
	x, y = [], []
	ids = []
	for score in xml.iter("Score"):
		if discard_errors:
			try: value = (mapper)(score, *mapper_args)
			except: continue
		else:
			value = (mapper)(score, *mapper_args)
		if value is None: continue
		
		x.append(parsedate(score.findtext("DateTime")))
		y.append(value)
		ids.append(score)
	
	return ((x, y), ids)

def gen_wifescore(xml): return map_scores(xml, map_wifescore)
def gen_manip(xml, replays): return map_scores(xml, map_manip, replays, discard_errors=False)
def gen_accuracy(xml): return map_scores(xml, map_accuracy)

# Returns list of sessions where a session is [(Score, datetime)]
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

# Returns ({datetime: session length}, [session])
def gen_session_length(xml):
	sessions = divide_into_sessions(xml)
	x, y = [], []
	for s in sessions:
		x.append(s[0][1]) # Datetime [1] of first play [0] in session
		y.append((s[-1][1]-s[0][1]).total_seconds() / 60) # Length in minutes
	
	return ((x, y), sessions)

# Return format: [[a,a...],[b,b...],[c,c...],[d,d...],[e,e...],[f,f...],[g,g...]]
def gen_session_skillsets(xml):
	# Divide scores into 'sessions' which are actually whole weeks
	sessions = []
	current_session = []
	previous_week = -1
	for score in sorted(xml.iter("Score"), key=lambda s: s.findtext("DateTime")):
		datetime = parsedate(score.findtext("DateTime"))
		week = datetime.isocalendar()[1]
		if previous_week != week:
			sessions.append(current_session)
			current_session = []
			previous_week = week
		current_session.append((score, datetime))
	sessions = sessions[1:]
	
	diffsets = []
	previous_week = -1
	for session in sessions:
		week = session[0][1].isocalendar()[1]
		if week != previous_week:
			#i += 1
			previous_week = week
		
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
	
	return (range(len(diffsets)), diffsets)

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
	return zip(*[(i, num_plays[i]) for i in range(24)])

def gen_session_plays(xml):
	sessions = divide_into_sessions(xml)
	nums_plays = [len(session) for session in sessions]
	nums_sessions_with_x_plays = Counter(nums_plays)
	return nums_sessions_with_x_plays

def gen_most_played_charts(xml, num_charts):
	charts_num_plays = []
	for chart in xml.iter("Chart"):
		score_filter = lambda s: float(s.findtext("WifeScore")) > 0.5
		num_plays = len([s for s in chart.iter("Score") if score_filter(s)])
		if num_plays > 0: charts_num_plays.append((chart, num_plays))
	
	charts_num_plays.sort(key=lambda pair: pair[1], reverse=True)
	return charts_num_plays[:num_charts]

def gen_cb_probability(xml, replays_dir):
	# {combo length: (base number, cb number)
	base = [0] * 10000
	cbs = [0] * 10000
	for score in xml.iter("Score"):
		try: replayfile = open(replays_dir+"/"+score.attrib['Key'])
		except: continue

		# TODO choose J4/J5/... time window depending on play data
		great_window = 0.09 # 'Great' time window, seconds, Wife J4
		combo = 0
		base[combo] += 1
		for line in replayfile.readlines():
			deviation = float(line.split(" ")[1])
			if deviation <= great_window:
				combo += 1
			else:
				cbs[combo] += 1
				combo = 0
			base[combo] += 1
		
	# Find first combo that was never reached (0), starting with combo 1
	max_combo = base.index(0, 1)
	result = {i: (cbs[i]/base[i]) for i in range(max_combo) if base[i] >= 0}
	return result

def gen_hours_per_skillset(xml):
	hours = [0, 0, 0, 0, 0, 0, 0]
	
	for score in xml.iter("Score"):
		skillset_ssrs = score.find("SkillsetSSRs")
		if skillset_ssrs == None: continue
		diffs = [float(diff.text) for diff in skillset_ssrs[1:]]
		main_diff = diffs.index(max(diffs))
		
		length_hours = float(score.findtext("SurviveSeconds")) / 3600
		hours[main_diff] += length_hours
	
	return hours

def gen_plays_per_week(xml):
	datetimes = [parsedate(s.findtext("DateTime")) for s in xml.iter("Score")]
	datetimes.sort()
	
	weeks = {}
	week_end = datetimes[0]
	week_start = week_end - timedelta(weeks=1)
	i = 0
	while i < len(datetimes):
		if datetimes[i] < week_end:
			weeks[week_start] += 1
			i += 1
		else:
			week_start += timedelta(weeks=1)
			week_end += timedelta(weeks=1)
			weeks[week_start] = 0
	
	return (list(weeks.keys()), list(weeks.values()))
	
def gen_session_rating_improvement(xml):
	datetimes = []
	lengths = []
	sizes = []
	ids = []
	
	sessions = divide_into_sessions(xml)
	skillsets_values = [[], [], [], [], [], [], []]
	previous_overall = 0
	# For each session
	for (session_i, session) in enumerate(sessions):
		# For each score in the session
		for (score, datetime) in session:
			# For every skillset trained with the score
			for i in range(7):
				# Append it to the list of skillset training values
				player_skillsets = score.find("SkillsetSSRs")
				if player_skillsets == None: continue
				value = float(player_skillsets[i+1].text)
				skillsets_values[i].append(value)
		
		# Overall-rating delta
		ratings = util.find_ratings(skillsets_values)
		overall_delta = ratings[0] - previous_overall
		
		# Add bubble size, clamping to [4;100] pixels
		size = math.sqrt(max(0, overall_delta)) * 40
		sizes.append(min(150, max(4, size)))
		
		# Append session datetime and length
		datetimes.append(session[0][1])
		length = (session[-1][1] - session[0][1]).total_seconds() / 60
		lengths.append(length)
		
		ids.append((previous_overall, ratings[0], len(session), length))
		
		previous_overall = ratings[0]
	
	return ((datetimes, lengths, sizes), ids)

def gen_textbox_text(xml):
	text = ["Most played charts:"]
	charts = gen_most_played_charts(xml, num_charts=5)
	i = 1
	for (chart, num_plays) in charts:
		pack, song = chart.get("Pack"), chart.get("Song")
		text.append(f"{i}) \"{pack}\" -> \"{song}\" with {num_plays} scores")
		i += 1
	
	return "<br>".join(text)

def gen_textbox_text_2(xml):
	sessions = divide_into_sessions(xml)
	sessions = [(s, (s[-1][1]-s[0][1]).total_seconds()/60) for s in sessions]
	sessions.sort(key=lambda pair: pair[1], reverse=True) # Sort by length
	sessions = sessions[:5]
	
	text = ["Longest sessions:"]
	i = 1
	for (session, length) in sessions:
		num_plays = len(session)
		datetime = session[0][1]
		text.append(f"{i}) {datetime}, {round(length)} minutes long with {num_plays} scores")
		i += 1
	
	return "<br>".join(text)

def gen_textbox_text_3(xml):
	hours = gen_hours_per_skillset(xml)
	
	text = ["Hours spent training each skillset"]
	for i in range(7):
		skillset = util.skillsets[i]
		m_total = int(hours[i] * 60)
		h = int(m_total / 60)
		m = m_total - 60 * h
		text.append(f"- {skillset}: {h}h {m}min")
	
	return "<br>".join(text)

def gen_textbox_text_4(xml):
	from dateutil.relativedelta import relativedelta
	
	scores = list(xml.iter("Score"))
	hours = sum(float(s.findtext("SurviveSeconds")) / 3600 for s in scores)
	first_play_date = min([parsedate(s.findtext("DateTime")) for s in scores])
	duration = relativedelta(datetime.now(), first_play_date)
	
	return "<br>".join([
		f"You started playing {duration.years} years {duration.months} months ago",
		f"Total hours spent playing: {round(hours)} hours",
		f"Number of scores: {len(scores)}",
	])
