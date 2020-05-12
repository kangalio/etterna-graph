from typing import *

import math
from datetime import datetime, timedelta
from collections import Counter

import util
from util import parsedate, cache, iter_scores


"""
This file holds all the so-called data generators. Those take save data
and generate data points out of them. There are multiple data generator
functions here, one for each plot
"""

def gen_manip(xml, analysis):
	x = analysis.datetimes
	y = [math.log(max(m * 100, 0.01)) / math.log(10) for m in analysis.manipulations]
	ids = analysis.scores
	return ((x, y), ids)

def score_to_wifescore(score):
	overall = float(score.findtext(".//Overall"))
	return overall

def score_to_accuracy(score):
	percent = float(score.findtext("SSRNormPercent")) * 100
	if percent <= -400: return None # Those are weird
	if percent > 100: return None
	return -(math.log(100 - percent) / math.log(10))

def score_to_ma(score):
	tap_note_scores = score.find("TapNoteScores")
	marvelouses = float(tap_note_scores.findtext("W1"))
	perfects = float(tap_note_scores.findtext("W2"))
	
	ma = marvelouses / perfects
	return math.log(ma) / math.log(10) # For log scale support

def map_scores(xml, mapper, *mapper_args, discard_errors=True, brush_color_over_10_notes=None):
	x, y = [], []
	ids = []
	if brush_color_over_10_notes:
		brushes = []
	for score in iter_scores(xml):
		if discard_errors:
			try: value = (mapper)(score, *mapper_args)
			except Exception: continue
		else:
			value = (mapper)(score, *mapper_args)
		if value is None: continue
		
		x.append(parsedate(score.findtext("DateTime")))
		y.append(value)
		ids.append(score)
		if brush_color_over_10_notes:
			tap_note_scores = score.find("TapNoteScores")
			if tap_note_scores:
				judgements = ["Miss", "W1", "W2", "W3", "W4", "W5"]
				total_notes = sum(int(tap_note_scores.findtext(x)) for x in judgements)
			else:
				total_notes = 500 # just assume 100 as a default yolo
			
			brushes.append(brush_color_over_10_notes if total_notes > 10 else "#AAAAAA")
	
	if brush_color_over_10_notes:
		return (((x, y), ids), brushes)
	else:
		return ((x, y), ids)

def gen_wifescore(xml): return map_scores(xml, score_to_wifescore)
def gen_accuracy(xml, color): return map_scores(xml, score_to_accuracy, brush_color_over_10_notes=color)
def gen_ma(xml): return map_scores(xml, score_to_ma)

# Returns list of sessions where a session is [(Score, datetime)]
# A session is defined to end when there's no play in 60 minutes or more
def divide_into_sessions(xml):
	if cache("sessions_division_cache"):
		return cache("sessions_division_cache")
	
	session_end_threshold = timedelta(hours=2)
	
	scores = list(iter_scores(xml))
	datetimes = [parsedate(s.find("DateTime").text) for s in scores]
	zipped = zip(scores, datetimes)
	zipped = sorted(zipped, key=lambda pair: pair[1])
	
	s_start = zipped[0][1]
	current_session = [zipped[0]]
	sessions = []
	for i in range(1, len(zipped)):
		datetime = zipped[i][1]
		idle_time = zipped[i][1] - zipped[i - 1][1]
		if idle_time > session_end_threshold:
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
	for score in sorted(iter_scores(xml), key=lambda s: s.findtext("DateTime")):
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
		
		diffset = [0, 0, 0, 0, 0, 0, 0]
		for score in session:
			skillset_ssrs = score[0].find("SkillsetSSRs")
			if skillset_ssrs is None: continue
			diffs = [float(diff.text) for diff in skillset_ssrs[1:]]
			main_diff = diffs.index(max(diffs))
			diffset[main_diff] += 1
		total = sum(diffset)
		if total == 0: continue
		diffset = [diff / total * 100 for diff in diffset]
		diffsets.append(diffset)
	
	return (range(len(diffsets)), diffsets)

def gen_plays_by_hour(xml):
	num_plays = [0] * 24
	for score in iter_scores(xml):
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
		score_filter = lambda s: float(s.findtext("SSRNormPercent")) > 0.5
		num_plays = len([s for s in iter_scores(chart) if score_filter(s)])
		if num_plays > 0: charts_num_plays.append((chart, num_plays))
	
	charts_num_plays.sort(key=lambda pair: pair[1], reverse=True)
	return charts_num_plays[:num_charts]

def gen_hours_per_skillset(xml):
	hours = [0, 0, 0, 0, 0, 0, 0]
	
	for score in iter_scores(xml):
		skillset_ssrs = score.find("SkillsetSSRs")
		if skillset_ssrs is None: continue
		diffs = [float(diff.text) for diff in skillset_ssrs[1:]]
		main_diff = diffs.index(max(diffs))
		
		length_hours = float(score.findtext("SurviveSeconds")) / 3600
		hours[main_diff] += length_hours
	
	return hours

def gen_hours_per_week(xml):
	scores = iter_scores(xml)
	pairs = [(s, parsedate(s.findtext("DateTime"))) for s in scores]
	pairs.sort(key=lambda pair: pair[1]) # Sort by datetime
	
	weeks = {}
	week_end = pairs[0][1] # First (earliest) datetime
	week_start = week_end - timedelta(weeks=1)
	i = 0
	while i < len(pairs):
		score, datetime = pairs[i][0], pairs[i][1]
		if datetime < week_end:
			score_seconds = float(score.findtext("SurviveSeconds")) or 0
			weeks[week_start] += score_seconds / 3600
			i += 1
		else:
			week_start += timedelta(weeks=1)
			week_end += timedelta(weeks=1)
			weeks[week_start] = 0
	
	return (list(weeks.keys()), list(weeks.values()))

def calc_average_hours_per_day(xml, timespan=timedelta(days=365/2)):
	scores = sorted(iter_scores(xml), key=lambda s: s.findtext("DateTime"))
	
	total_hours = 0
	for score in scores:
		total_hours += float(score.findtext("SurviveSeconds")) / 3600
	
	return total_hours / timespan.days

# OPTIONAL PLOTS BEGINNING

def gen_hit_distribution(xml, analysis):
	buckets = analysis.offset_buckets
	return (list(buckets.keys()), list(buckets.values()))

def gen_idle_time_buckets(xml):
	# Each bucket is 5 seconds. Total 10 minutes is tracked
	buckets = [0] * 600
	
	a, b = 0, 0
	
	scores = []
	for scoresat in xml.iter("ScoresAt"):
		rate = float(scoresat.get("Rate"))
		scores.extend(((score, rate) for score in iter_scores(scoresat)))
	
	# Sort scores by datetime, oldest first
	scores.sort(key=lambda pair: pair[0].findtext("DateTime"))
	
	last_play_end = None
	for score, rate in scores:
		a += 1
		datetime = util.parsedate(score.findtext("DateTime"))
		survive_seconds = float(score.findtext("SurviveSeconds"))
		#print(survive_seconds, rate)
		length = timedelta(seconds=survive_seconds*rate)
		
		#print("Datetime:", datetime)
		#print("Play length:", str(length)[:-7], "(according to SurviveSeconds)")
		if last_play_end is not None:
			idle_time = datetime - last_play_end
			if idle_time >= timedelta():
				bucket_index = int(idle_time.total_seconds() // 5)
				if bucket_index < len(buckets):
					buckets[bucket_index] += 1
			else:
				#print("Negative idle time!")
				b += 1
		
		last_play_end = datetime + length
		#print("Finished", last_play_end)
		#print()
	
	# ~ keys = [i * 5 for i in range(len(buckets))]
	keys = range(len(buckets))
	return (keys, buckets)

def gen_session_length(xml):
	sessions = divide_into_sessions(xml)
	x, y = [], []
	for s in sessions:
		x.append(s[0][1]) # Datetime [1] of first play [0] in session
		y.append((s[-1][1] - s[0][1]).total_seconds() / 60) # Length in minutes
	
	return (x, y)

def gen_session_plays(xml):
	sessions = divide_into_sessions(xml)
	nums_plays = [len(session) for session in sessions]
	nums_sessions_with_x_plays = Counter(nums_plays)
	return (list(nums_sessions_with_x_plays.keys()),
			list(nums_sessions_with_x_plays.values()))

# Currently broken
"""def gen_cb_probability(xml, analysis):
	# {combo length: (base number, cb number)
	base, cbs = analysis.combo_occurences, analysis.cbs_on_combo_len
	
	# Find first combo that was never reached (0), starting with combo 1
	max_combo = base.index(0, 1)
	result = {i: int(cbs[i]/base[i]) for i in range(max_combo)[:10] if base[i] >= 0}
	x_list = range(max_combo)
	return (x_list, [cbs[i]/base[i] for i in x_list])"""

def gen_plays_per_week(xml):
	datetimes = [parsedate(s.findtext("DateTime")) for s in iter_scores(xml)]
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

# OPTIONAL PLOTS END

def calc_ratings_for_sessions(xml):
	if cache("calc_ratings_for_sessions"):
		return cache("calc_ratings_for_sessions")
	
	sessions = divide_into_sessions(xml)
	skillsets_values = [[], [], [], [], [], [], []]
	session_rating_pairs = []
	# For each session
	for (session_i, session) in enumerate(sessions):
		# For each score in the session
		for (score, _score_datetime) in session:
			# For every skillset trained with the score
			for i in range(7):
				# Append it to the list of skillset training values
				player_skillsets = score.find("SkillsetSSRs")
				if player_skillsets is None: continue
				value = float(player_skillsets[i + 1].text)
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

# Returns tuple of `(max_combo_chart_element, max_combo_int)`
def find_longest_combo(xml):
	max_combo_chart = None
	max_combo = 0
	for chart in xml.iter("Chart"):
		for score in iter_scores(chart):
			combo = int(score.findtext("MaxCombo"))
			if combo > max_combo:
				max_combo = combo
				max_combo_chart = chart
	return max_combo_chart, max_combo

# Returns dict with pack names as keys and the respective "pack liking"
# as value. The liking value is currently simply the amount of plays in the pack
def generate_pack_likings(xml, months):
	likings = {}
	for chart in xml.iter("Chart"):
		num_relevant_plays = 0
		for score in iter_scores(chart):
			if util.score_within_n_months(score, months):
				num_relevant_plays += 1
		pack = chart.get("Pack")
		
		if pack not in likings: likings[pack] = 0
		likings[pack] += num_relevant_plays
	
	return likings

def calculate_total_wifescore(xml, months=6):
	weighted_sum = 0
	num_notes_sum = 0
	for score in iter_scores(xml):
		if not util.score_within_n_months(score, months): continue
		
		num_notes = sum([int(e.text) for e in score.find("TapNoteScores")])
		num_notes_sum += num_notes
		
		wifescore = float(score.findtext("SSRNormPercent"))
		weighted_sum += wifescore * num_notes
	return weighted_sum / num_notes_sum

def gen_skillset_development(xml):
	datetimes, all_ratings = [], []
	for (session, ratings) in calc_ratings_for_sessions(xml):
		datetimes.append(session[0][1])
		all_ratings.append(ratings)
	return (datetimes, all_ratings)

def gen_cmod_over_time(xml):
	datetime_cmod_map = {}
	for score in xml.iter("Score"):
		modifiers = score.findtext("Modifiers").split(", ")
		cmod = None
		receptor_size = None
		perspective_mod_multiplier = 1
		for modifier in modifiers:
			if cmod is None and modifier.startswith("C"):
				try:
					cmod = float(modifier[1:])
				except ValueError:
					continue
			elif receptor_size is None and modifier.endswith("Mini"):
				mini_percentage_string = modifier[:-4]
				if mini_percentage_string == "":
					receptor_size = 0.5
				else:
					if not mini_percentage_string.endswith("% "): continue # false positive
					mini = float(mini_percentage_string[:-2]) / 100
					receptor_size = 1 - mini / 2
			elif modifier == "Incoming":
				# This and the following three values were gathered through a quick-and-dirty
				# screen recording based test
				perspective_mod_multiplier = 1 / 1.2931
			elif modifier == "Space":
				perspective_mod_multiplier = 1 / 1.2414
			elif modifier == "Hallway":
				perspective_mod_multiplier = 1 / 1.2931
			elif modifier == "Distant":
				perspective_mod_multiplier = 1 / 1.2759
		if receptor_size is None: receptor_size = 1
		
		if cmod is None: continue # player's using xmod or something
		
		effective_cmod = cmod * receptor_size * perspective_mod_multiplier
		
		dt = parsedate(score.findtext("DateTime"))
		datetime_cmod_map[dt] = effective_cmod
	
	datetimes = list(sorted(datetime_cmod_map.keys()))
	cmods = [datetime_cmod_map[dt] for dt in datetimes]
	return datetimes, cmods
	
def count_nums_grades(xml):
	grades = []
	for score in util.iter_scores(xml):
		percent = float(score.findtext("SSRNormPercent"))
		grade = sum(percent >= t for t in util.grade_thresholds) - 1
		grades.append(util.grade_names[grade])
	return Counter(grades)

def gen_text_most_played_charts(xml, limit=5):
	text = ["Most played charts:"]
	charts = gen_most_played_charts(xml, num_charts=limit)
	i = 1
	for (chart, num_plays) in charts:
		pack, song = chart.get("Pack"), chart.get("Song")
		text.append(f"{i}) \"{pack}\" -> \"{song}\" with {num_plays} scores")
		i += 1
	
	if limit is not None:
		text.append(f'<a href="#read_more" style="color: {util.link_color}">Show all</a>')
	
	return "<br>".join(text)

def gen_text_longest_sessions(xml, limit=5):
	sessions = divide_into_sessions(xml)
	sessions = [(s, (s[-1][1] - s[0][1]).total_seconds() / 60) for s in sessions]
	sessions.sort(key=lambda pair: pair[1], reverse=True) # Sort by length
	sessions = sessions[:limit]
	
	text = ["Longest sessions:"]
	i = 1
	for (session, length) in sessions:
		num_plays = len(session)
		datetime = str(session[0][1])[:-3] # Cut off seconds
		text.append(f"{i}) {datetime}, {round(length)} minutes, {num_plays} scores")
		i += 1
	
	if limit is not None:
		text.append(f'<a href="#read_more" style="color: {util.link_color}">Show all</a>')
	
	return "<br>".join(text)

def gen_text_skillset_hours(xml):
	hours = gen_hours_per_skillset(xml)
	
	text = ["Hours spent training each skillset:"]
	for i in range(7):
		skillset = util.skillsets[i]
		text.append(f"- {skillset}: {util.timespan_str(hours[i])}")
	
	return "<br>".join(text)

# Parameter r is the ReplaysAnalysis
def gen_text_general_info(xml, r):
	from dateutil.relativedelta import relativedelta
	
	if r: # If ReplaysAnalysis is avilable
		total_notes_string = util.abbreviate(r.total_notes, min_precision=3)
		
		chart = r.longest_mcombo[1]
		long_mcombo_chart = f'"{chart.get("Pack")} -> "{chart.get("Song")}"'
		long_mcombo_str = f"{r.longest_mcombo[0]} on {long_mcombo_chart}"
	else:
		total_notes_string = "[please load replay data]"
		long_mcombo_str = "[please load replay data]"
	
	scores = list(iter_scores(xml))
	num_charts = len(list(xml.iter("Chart")))
	hours = sum(float(s.findtext("SurviveSeconds")) / 3600 for s in scores)
	first_play_date = min([parsedate(s.findtext("DateTime")) for s in scores])
	duration = relativedelta(datetime.now(), first_play_date)
	
	chart, combo = find_longest_combo(xml)
	long_combo_chart = f'"{chart.get("Pack")} -> "{chart.get("Song")}"'
	long_combo_str = f"{combo} on {long_combo_chart}"
	
	grade_strings = []
	grades = count_nums_grades(xml)
	for grade_name in util.grade_names[::-1]:
		num = grades[grade_name] # Number of scores with that grade
		# ~ grade_strings.append(f"{num}x {grade_name}")
		grade_strings.append(f"{grade_name}: {num}")
	grades_string = ", ".join(grade_strings)
	
	return "<br>".join([
		f"You started playing {duration.years} years {duration.months} months ago",
		f"Total hours spent playing: {round(hours)} hours",
		f"Number of scores: {len(scores)}",
		f"Number of unique files played: {num_charts}",
		f"Grades: {grades_string}",
		f"Total arrows hit: {total_notes_string}",
		f"Longest combo: {long_combo_str}",
		f"Longest marvelous combo: {long_mcombo_str}",
	])

# a stands for ReplaysAnalysis
def gen_text_general_analysis_info(xml, a):
	if a:
		cb_ratio_per_column = [cbs / total for (cbs, total)
				in zip(a.cbs_per_column, a.notes_per_column)]
		cbs_string = ', '.join([f"{round(100 * r, 2)}%" for r in cb_ratio_per_column])
		
		mean_string = f"{round(a.offset_mean * 1000, 1)}ms"
	else:
		cbs_string = "[please load replay data]"
		mean_string = "[please load replay data]"
	
	session_secs = int(xml.find("GeneralData").findtext("TotalSessionSeconds"))
	play_secs = int(xml.find("GeneralData").findtext("TotalGameplaySeconds"))
	if session_secs == 0: # Happened for BanglesOtter, for whatever reason
		play_percentage = 0
	else:
		play_percentage = round(100 * play_secs / session_secs)
	
	median_score_increase = round(calc_median_score_increase(xml), 1)
	
	average_hours = calc_average_hours_per_day(xml)
	average_hours_str = util.timespan_str(average_hours)
	
	session_date_threshold = datetime.now() - timedelta(days=7)
	sessions = divide_into_sessions(xml)
	num_sessions = len([s for s in sessions if s[0][1] > session_date_threshold])
	
	total_wifescore = calculate_total_wifescore(xml, months=6)
	total_wifescore_str = f"{round(total_wifescore * 100, 2)}%"
	
	return "<br>".join([
		f"You spend {play_percentage}% of your sessions in gameplay",
		f"Total CB percentage per column (left to right): {cbs_string}",
		f"Median score increase when immediately replaying a chart: {median_score_increase}%",
		f"Mean hit offset: {mean_string}",
		f"Average hours per day (last 6 months): {average_hours_str}",
		f"Number of sessions, last 7 days: {num_sessions}",
		f"Average wifescore last 6 months is {total_wifescore_str}",
	])

def gen_text_most_played_packs(xml, limit=15, months: Optional[int]=None):
	likings = generate_pack_likings(xml, months)
	
	sorted_packs = sorted(likings, key=likings.get, reverse=True)
	best_packs = sorted_packs[:limit]
	
	first_line = "Most played packs (" + (f"last {months} months" if months else "all time")
	if limit:
		first_line += ' - <a href="toggle" style="color: {util.link_color}">toggle</a>'
	first_line += ")"
	
	text = [first_line]
	for i, pack in enumerate(best_packs):
		if pack == "":
			pack_str = '<span style="color: #777777">[no name]</span>'
		else:
			pack_str = pack
		text.append(f"{i+1}) {pack_str} with {likings[pack]} plays")
	
	if limit is not None:
		text.append(f'<a href="#read_more" style="color: {util.link_color}">Show all</a>')
	
	return "<br>".join(text)

# Calculate the median score increase, when playing a chart twice
# in direct succession
def calc_median_score_increase(xml):
	from statistics import median
	
	score_increases = []
	
	for chart in xml.iter("ScoresAt"):
		# Chronologically sorted scores
		scores = sorted(iter_scores(chart), key=lambda s: s.findtext("DateTime"))
		
		for i in range(0, len(scores) - 1):
			datetime_1 = parsedate(scores[i].findtext("DateTime"))
			datetime_2 = parsedate(scores[i + 1].findtext("DateTime"))
			time_delta = datetime_2 - datetime_1
			play_time = float(scores[i].findtext("SurviveSeconds"))
			idle_time = time_delta.total_seconds() - play_time
			
			# If the same chart is played twice within 60 seconds
			if idle_time < 60:
				score_1 = float(scores[i].findtext("SSRNormPercent"))
				score_2 = float(scores[i + 1].findtext("SSRNormPercent"))
				score_increase = 100 * (score_2 - score_1)
				score_increases.append(score_increase)
	
	if len(score_increases) == 0:
		return 0
	else:
		return median(score_increases)
