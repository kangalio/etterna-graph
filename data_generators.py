from datetime import datetime, timedelta
import numpy as np
import math

import util
from util import parsedate

"""
This file holds all the so-called data generators. Those take save data
and generate data points out of them. There are multiple data generator
functions here, one for each plot
"""

"""def extract_replay_data(xml, replays):
	all_times, all_offsets, all_columns = [], [], []
	for score in xml.iter("Score"):
		replay = replays.get(score.get("Key"))
		if replay is None: continue
		
		length = len(replay)
		times = np.empty(length)
		offsets = np.empty(length)
		columns = np.empty(length)
		for (i, line) in enumerate(replay):
			try:
				tokens = line.split(" ")
				times[i] = int(tokens[0])
				offsets[i] = float(tokens[1])
				columns[i] = int(tokens[2])
			except ValueError:
				continue
		
		all_times.append(times)
		all_offsets.append(offsets)
		all_columns.append(columns)
	
	return (times, offsets, columns)"""

# This function is responsible for replay analysis. Every chart that 
# uses replay data uses the data generated from this function.
scores = None
datetimes = None
manipulations = None
cbs_per_column = None
notes_per_column = None
offset_means = None
# This could also be implemented by counting the various note scores in 
# the Etterna.xml, but it's easier to count in the replays.
total_notes = None
def analyze_replays(xml, replays):
	#extract_replay_data(xml, replays)
	
	global scores, datetimes, manipulations, cbs_per_column, offset_means, total_notes, notes_per_column
	
	scores = []
	datetimes = []
	manipulations = []
	offset_means = []
	notes_per_column = [0, 0, 0, 0]
	cbs_per_column = [0, 0, 0, 0]
	total_notes = 0
	for score in xml.iter("Score"):
		replay = replays.get(score.get("Key"))
		if replay is None: continue
		
		previous_time = 0
		num_total = 0
		num_manipulated = 0
		offsets = []
		for line in replay:
			try:
				tokens = line.split(" ")
				time, column = int(tokens[0]), int(tokens[2])
				offset = float(tokens[1])
			except ValueError:
				continue
			
			if time < previous_time: num_manipulated += 1
			previous_time = time
			
			if column < 4: # Ignore 6-and-up-key scores
				if abs(offset) > 0.09: cbs_per_column[column] += 1
				notes_per_column[column] += 1
			
			offsets.append(offset)
			
			num_total += 1
		
		manipulations.append(num_manipulated / num_total)
		
		offset_means.append(sum(offsets) / len(offsets))
		
		scores.append(score)
		datetimes.append(parsedate(score.findtext("DateTime")))
		
		total_notes += num_total

def gen_manip(xml, replays):
	if manipulations is None: analyze_replays(xml, replays)
	
	x = datetimes
	y = [math.log(max(m*100, 0.01)) / math.log(10) for m in manipulations]
	ids = scores
	return ((x, y), ids)

# This method does not model the actual game mechanics 100% accurately
def score_to_wifescore(score):
	overall = float(score.findtext(".//Overall"))
	percentage = float(score.findtext("WifeScore"))
	return overall * percentage / 0.93

def score_to_accuracy(score):
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

def gen_wifescore(xml): return map_scores(xml, score_to_wifescore)
def gen_accuracy(xml): return map_scores(xml, score_to_accuracy)

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
"""
def gen_session_length(xml):
	sessions = divide_into_sessions(xml)
	x, y = [], []
	for s in sessions:
		x.append(s[0][1]) # Datetime [1] of first play [0] in session
		y.append((s[-1][1]-s[0][1]).total_seconds() / 60) # Length in minutes
	
	return ((x, y), sessions)
"""

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

"""
def gen_session_plays(xml):
	sessions = divide_into_sessions(xml)
	nums_plays = [len(session) for session in sessions]
	nums_sessions_with_x_plays = Counter(nums_plays)
	return nums_sessions_with_x_plays
"""

def gen_most_played_charts(xml, num_charts):
	charts_num_plays = []
	for chart in xml.iter("Chart"):
		score_filter = lambda s: float(s.findtext("WifeScore")) > 0.5
		num_plays = len([s for s in chart.iter("Score") if score_filter(s)])
		if num_plays > 0: charts_num_plays.append((chart, num_plays))
	
	charts_num_plays.sort(key=lambda pair: pair[1], reverse=True)
	return charts_num_plays[:num_charts]

"""
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
"""

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

calc_ratings_for_sessions_cache = None
def calc_ratings_for_sessions(xml):
	global calc_ratings_for_sessions_cache
	if calc_ratings_for_sessions_cache: return calc_ratings_for_sessions_cache
	
	sessions = divide_into_sessions(xml)
	skillsets_values = [[], [], [], [], [], [], []]
	session_rating_pairs = []
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
		session_rating_pairs.append((session, ratings))
	
	calc_ratings_for_sessions_cache = session_rating_pairs
	return session_rating_pairs

def gen_session_rating_improvement(xml):
	datetimes, lengths, sizes, ids = [], [], [], []
	
	previous_overall = 0
	for (session, ratings) in calc_ratings_for_sessions(xml):
		# Overall-rating delta
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

def gen_skillset_development(xml):
	datetimes, all_ratings = [], []
	for (session, ratings) in calc_ratings_for_sessions(xml):
		datetimes.append(session[0][1])
		all_ratings.append(ratings)
	return (datetimes, all_ratings)

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

def gen_textbox_text_4(xml, replays):
	from dateutil.relativedelta import relativedelta
	
	if replays:
		if total_notes is None: analyse_replays(xml, replays)
		total_notes_string = util.abbreviate(total_notes, min_precision=3)
	else:
		total_notes_string = "[please load replay data]"
	
	scores = list(xml.iter("Score"))
	hours = sum(float(s.findtext("SurviveSeconds")) / 3600 for s in scores)
	first_play_date = min([parsedate(s.findtext("DateTime")) for s in scores])
	duration = relativedelta(datetime.now(), first_play_date)
	
	return "<br>".join([
		f"You started playing {duration.years} years {duration.months} months ago",
		f"Total hours spent playing: {round(hours)} hours",
		f"Number of scores: {len(scores)}",
		f"Total arrows hit: {total_notes_string}",
	])

def gen_textbox_text_5(xml, replays):
	global notes_per_column, cbs_per_column
	
	if replays:
		if cbs_per_column is None: analyze_replays(xml, replays)
		
		cb_ratio_per_column = [cbs/total for (cbs, total)
				in zip(cbs_per_column, notes_per_column)]
		cbs_string = ', '.join([f"{round(100*r, 2)}%" for r in cb_ratio_per_column])
		
		offset_mean = sum(offset_means) / len(offset_means)
		mean_string = f"{round(offset_mean * 1000, 1)}ms"
	else:
		cbs_string = "[please load replay data]"
		mean_string = "[please load replay data]"
	
	median_score_increase = round(calc_median_score_increase(xml), 1)
	
	return "<br>".join([
		f"Total CB percentage per column (left to right): {cbs_string}",
		f"Median score increase when immediately replaying a chart: {median_score_increase}%",
		f"Mean hit offset: {mean_string}",
	])

# Calculate the median score increase, when playing a chart twice
# successively
def calc_median_score_increase(xml):
	from statistics import median
	
	score_increases = []
	
	for chart in xml.iter("ScoresAt"):
		# Chronologically sorted scores
		scores = sorted(chart.iter("Score"), key=lambda s: s.findtext("DateTime"))
		
		for i in range(0, len(scores) - 1):
			datetime_1 = parsedate(scores[i].findtext("DateTime"))
			datetime_2 = parsedate(scores[i+1].findtext("DateTime"))
			time_delta =  datetime_2 - datetime_1
			play_time = float(scores[i].findtext("SurviveSeconds"))
			idle_time = time_delta.total_seconds() - play_time
			
			# If the same chart is played twice within 60 seconds
			if idle_time < 60:
				score_1 = float(scores[i].findtext("WifeScore"))
				score_2 = float(scores[i+1].findtext("WifeScore"))
				score_increase = 100 * (score_2 - score_1)
				score_increases.append(score_increase)
	
	return median(score_increases)
