from typing import *

import os, logging, json, math
from datetime import datetime, timedelta
from urllib.request import urlopen

import app


skillsets = ["Stream", "Jumpstream", "Handstream", "Stamina",
		"Jacks", "Chordjacks", "Technical"]

logger = logging.getLogger()

# Official EO colors
#skillset_colors = ["7d6b91", "8481db", "995fa3", "f2b5fa", "6c969d", "a5f8d3", "b0cec2"]
# Modified (saturated) EO colors
skillset_colors = ["333399", "6666ff", "cc33ff", "ff99cc", "009933", "66ff66", "808080"]

grade_names = "D C B A AA AAA AAAA AAAAA".split(" ")
grade_thresholds = [-math.inf, 0.6, 0.7, 0.8, 0.93, 0.997, 0.99955, 0.99996]
D_THRESHOLD = grade_thresholds[0]
C_THRESHOLD = grade_thresholds[1]
B_THRESHOLD = grade_thresholds[2]
A_THRESHOLD = grade_thresholds[3]
AA_THRESHOLD = grade_thresholds[4]
AAA_THRESHOLD = grade_thresholds[5]
AAAA_THRESHOLD = grade_thresholds[6]
AAAAA_THRESHOLD = grade_thresholds[7]


def bg_color(): return app.app.prefs.bg_color
def text_color(): return app.app.prefs.text_color
def border_color(): return app.app.prefs.border_color
def link_color(): return app.app.prefs.link_color

_keep_storage = []
def keep(*args): # an escape hatch of Python's GC
	_keep_storage.extend(args)

def wifescore_to_grade_string(wifescore: float) -> str:
	for grade_name, grade_threshold in zip(grade_names, grade_thresholds):
		if wifescore >= grade_threshold:
			return grade_name
	return "huh?"
	logger.exception("this shouldn't happen")

# Parses date in Etterna.xml format
def parsedate(s):
	try:
		return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
	except ValueError:
		# in this case this datetime is on midnight, in which case Etterna omits the time part
		# of the datetime. Weird behavior, but true. Found by snover
		return datetime.strptime(s, "%Y-%m-%d")

def score_within_n_months(score, months: Optional[int]) -> bool:
	if months is None: return True
	
	time_delta = datetime.now() - parsedate(score.findtext("DateTime"))
	return time_delta <= timedelta(365 / 12 * months)

def is_score_valid(score):
	skillset_ssrs = score.find("SkillsetSSRs")
	if skillset_ssrs is not None:
		overall_ssr = float(skillset_ssrs.findtext("Overall"))
		if overall_ssr > 40:
			return False
	
	if score.findtext("EtternaValid") == "0" and app.app.prefs.hide_invalidated: return False
	
	return True

def iter_scores(xml_element):
	return filter(is_score_valid, xml_element.iter("Score"))

def get_latest_release():
	with urlopen("https://api.github.com/repos/kangalioo/etterna-graph/releases") as response:
		return json.loads(response.read())[0]
		

# Rarameters: replays = ReplaysV2 directory path  ;  key = Chart key
# Returns list of the files' lines
def read_replay(replays, key):
	path = os.path.join(replays, key)
	if os.path.exists(path):
		with open(path) as f: return f.readlines()
	else:
		return None

# Convert a float of hours to a string, e.g. "5h 35min"
def timespan_str(hours):
	minutes_total = round(hours * 60)
	hours = int(minutes_total / 60)
	minutes = minutes_total - 60 * hours
	return f"{hours}h {minutes}min"

cache_data = {}
def cache(key, data=None):
	global cache_data
	
	if data is not None: # If data was given, update cache
		cache_data[key] = data
	return cache_data.get(key) # Return cached data

def clear_cache():
	global cache_data
	
	cache_data = {}

def find_parent_chart(xml, score):
	score_key = score.get("Key")
	return xml.find(f".//Score[@Key=\"{score_key}\"]/../..")

# Abbreviates a number, e.g. (with default `min_precision`):
#  1367897 -> 1367k
#  47289361 -> 47M
# The min_precision parameter controls how many digits must be visible minimum
def abbreviate(n, min_precision=2):
	num_digits = len(str(n))
	postfix_index = int((num_digits - min_precision) / 3)
	postfix = ["", "k", "M", "B", "T", "Q"][postfix_index]
	return str(round(n / 1000**postfix_index)) + postfix

def gen_padding_from(text):
	return f'<span style="color:{bg_color}">{text}</span>'
