from datetime import datetime, timedelta
import numpy as np
import math

import util
from util import parsedate, cache

"""
This file holds all the so-called data generators. Those take save data
and generate data points out of them. There are multiple data generator
functions here, one for each plot
"""

def gen_manip(xml, analysis):
	x = analysis.datetimes
	y = [math.log(max(m*100, 0.01)) / math.log(10) for m in analysis.manipulations]
	ids = analysis.scores
	return ((x, y), ids)

# This is only an approximation of the actual game mechanics
def score_to_msd(score):
	overall = float(score.findtext(".//Overall"))
	percentage = float(score.findtext("WifeScore"))
	percentage = min(0.965, percentage) # Cap to 96.5%, like in the real game
	return overall * (0.93 / percentage)

def score_to_wifescore(score):
	overall = float(score.findtext(".//Overall"))
	return overall

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
# A session is defined to end when there's no play in 20 minutes or more
def divide_into_sessions(xml):
	if cache("sessions_division_cache"):
		return cache("sessions_division_cache")
	
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
			sessions.append(current_session)
			current_session = []
			s_start = zipped[i][1]
		current_session.append(zipped[i])
	
	return cache("sessions_division_cache", sessions)

# Return format: [[a,a...],[b,b...],[c,c...],[d,d...],[e,e...],[f,f...],[g,g...]]
def gen_week_skillsets(xml):
	# Divide scores into weeks
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


def gen_most_played_charts(xml, num_charts):
	charts_num_plays = []
	for chart in xml.iter("Chart"):
		score_filter = lambda s: float(s.findtext("WifeScore")) > 0.5
		num_plays = len([s for s in chart.iter("Score") if score_filter(s)])
		if num_plays > 0: charts_num_plays.append((chart, num_plays))
	
	charts_num_plays.sort(key=lambda pair: pair[1], reverse=True)
	return charts_num_plays[:num_charts]

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

def gen_hit_distribution(xml, analysis):
	buckets = analysis.offset_buckets
	return (list(buckets.keys()), list(buckets.values()))

def calc_ratings_for_sessions(xml):
	if cache("calc_ratings_for_sessions"):
		return cache("calc_ratings_for_sessions")
	
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
	
	return cache("calc_ratings_for_sessions", session_rating_pairs)

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

# Returns dict with pack names as keys and the respective "pack liking"
# as value. The liking value is currently simply the amount of recent
# plays in the pack. Recent = in the last `timespan_months` months
def generate_pack_likings(xml, timespan_months):
	SCORE_DATE_THRESHOLD = datetime.now() - timedelta(days=timespan_months*365//12)
	
	def condition(score):
		date_str = score.findtext("DateTime")
		if date_str is None: return False
		
		date = datetime.fromisoformat(date_str)
		return date > SCORE_DATE_THRESHOLD
	
	likings = {}
	for chart in xml.iter("Chart"):
		valid_plays = sum(1 for s in chart.iter("Score") if (condition)(s))
		pack = chart.get("Pack")
		
		if not pack in likings: likings[pack] = 0
		likings[pack] += valid_plays
	
	return likings

def gen_skillset_development(xml):
	datetimes, all_ratings = [], []
	for (session, ratings) in calc_ratings_for_sessions(xml):
		datetimes.append(session[0][1])
		all_ratings.append(ratings)
	return (datetimes, all_ratings)

def gen_text_most_played_charts(xml):
	text = ["Most played charts:"]
	charts = gen_most_played_charts(xml, num_charts=5)
	i = 1
	for (chart, num_plays) in charts:
		pack, song = chart.get("Pack"), chart.get("Song")
		text.append(f"{i}) \"{pack}\" -> \"{song}\" with {num_plays} scores")
		i += 1
	
	return "<br>".join(text)

def gen_text_longest_sessions(xml):
	sessions = divide_into_sessions(xml)
	sessions = [(s, (s[-1][1]-s[0][1]).total_seconds()/60) for s in sessions]
	sessions.sort(key=lambda pair: pair[1], reverse=True) # Sort by length
	sessions = sessions[:5]
	
	text = ["Longest sessions:"]
	i = 1
	for (session, length) in sessions:
		num_plays = len(session)
		datetime = str(session[0][1])[:-3] # Cut off seconds
		text.append(f"{i}) {datetime}, {round(length)} minutes, {num_plays} scores")
		i += 1
	
	return "<br>".join(text)

def gen_text_skillset_hours(xml):
	hours = gen_hours_per_skillset(xml)
	
	text = ["Hours spent training each skillset:"]
	for i in range(7):
		skillset = util.skillsets[i]
		m_total = int(hours[i] * 60)
		h = int(m_total / 60)
		m = m_total - 60 * h
		text.append(f"- {skillset}: {h}h {m}min")
	
	return "<br>".join(text)

# Parameter r is the ReplaysAnalysis
def gen_text_general_info(xml, r):
	from dateutil.relativedelta import relativedelta
	
	if r: # If ReplaysAnalysis is avilable
		total_notes_string = util.abbreviate(r.total_notes, min_precision=3)
		
		chart = r.longest_combo[1]
		long_combo_chart = f'"{chart.get("Pack")} -> "{chart.get("Song")}"'
		long_combo_str = f"{r.longest_combo[0]} on {long_combo_chart}"
		
		chart = r.longest_mcombo[1]
		long_mcombo_chart = f'"{chart.get("Pack")} -> "{chart.get("Song")}"'
		long_mcombo_str = f"{r.longest_mcombo[0]} on {long_mcombo_chart}"
	else:
		total_notes_string = "[please load replay data]"
		long_combo_str = "[please load replay data]"
		long_mcombo_str = "[please load replay data]"
	
	scores = list(xml.iter("Score"))
	hours = sum(float(s.findtext("SurviveSeconds")) / 3600 for s in scores)
	first_play_date = min([parsedate(s.findtext("DateTime")) for s in scores])
	duration = relativedelta(datetime.now(), first_play_date)
	
	return "<br>".join([
		f"You started playing {duration.years} years {duration.months} months ago",
		f"Total hours spent playing: {round(hours)} hours",
		f"Number of scores: {len(scores)}",
		f"Total arrows hit: {total_notes_string}",
		f"Longest combo: {long_combo_str}",
		f"Longest marvelous combo: {long_mcombo_str}",
	])

# a stands for ReplaysAnalysis
def gen_text_general_analysis_info(xml, a):
	if a:
		cb_ratio_per_column = [cbs/total for (cbs, total)
				in zip(a.cbs_per_column, a.notes_per_column)]
		cbs_string = ', '.join([f"{round(100*r, 2)}%" for r in cb_ratio_per_column])
		
		mean_string = f"{round(a.offset_mean * 1000, 1)}ms"
	else:
		cbs_string = "[please load replay data]"
		mean_string = "[please load replay data]"
	
	session_secs = xml.find("GeneralData").findtext("TotalSessionSeconds")
	play_secs = xml.find("GeneralData").findtext("TotalGameplaySeconds")
	play_percentage = round(100 * int(play_secs) / int(session_secs))
	
	median_score_increase = round(calc_median_score_increase(xml), 1)
	
	return "<br>".join([
		f"You spend {play_percentage}% of your sessions in gameplay",
		f"Total CB percentage per column (left to right): {cbs_string}",
		f"Median score increase when immediately replaying a chart: {median_score_increase}%",
		f"Mean hit offset: {mean_string}",
	])

def gen_text_most_played_packs(xml):
	likings = generate_pack_likings(xml, 6)
	
	sorted_packs = sorted(likings, key=likings.get, reverse=True)
	best_packs = sorted_packs[:min(12, len(sorted_packs))]
	text = ["Most played packs (last 6 months):"]
	for i, pack in enumerate(best_packs):
		if len(pack) > 25:
			pack_str = pack[:25] + "…"
		else:
			pack_str = pack
		text.append(f"{i+1}) {pack_str} with {likings[pack]} plays")
	
	return "<br>".join(text)

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
	
	if len(score_increases) == 0:
		return 0
	else:
		return median(score_increases)
