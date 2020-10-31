from datetime import datetime, timedelta
import math, os
from numba import jit
import numpy as np
import logging

skillsets = ["Stream", "Jumpstream", "Handstream", "Stamina",
		"Jacks", "Chordjacks", "Technical"]

logger = logging.getLogger()
"""logger.addHandler(logging.handlers.SMTPHandler(
		mailhost=("smtp.example.com", 25),
		fromaddr="from@example.com", 
		toaddrs="to@example.com",
		subject=u"AppName error!")"""

# Official EO colors
#skillset_colors = ["7d6b91", "8481db", "995fa3", "f2b5fa", "6c969d", "a5f8d3", "b0cec2"]
# Modified (saturated) EO colors
skillset_colors = ["333399", "6666ff", "cc33ff", "ff99cc", "009933", "66ff66", "808080"]


# Parses date in Etterna.xml format
def parsedate(s): return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

# Used for `is_relevant(score)`
SCORE_DATE_THRESHOLD = datetime.now() - timedelta(days=183)
# Returns True or False depending on whether the score is relevant
# If it't not relevant, it won't be included in some statistics
def is_relevant(score):
	return parsedate(score.findtext("DateTime")) > SCORE_DATE_THRESHOLD
def get_relevance_string(): return "last 6 months"

def is_score_valid(score):
	skillset_ssrs = score.find("SkillsetSSRs")
	if not skillset_ssrs is None:
		overall_ssr = float(skillset_ssrs.findtext("Overall"))
		if overall_ssr > 40: return False
	
	if score.findtext("EtternaValid") == "0": return False
	
	return True

def iter_scores(xml_element):
	return filter(is_score_valid, xml_element.iter("Score"))

# Rarameters: replays = ReplaysV2 directory path  ;  key = Chart key
# Returns list of the files' lines
def read_replay(replays, key):
	path = replays + "/" + key
	if os.path.exists(path):
		return open(path).readlines()
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
	
	if not data is None: # If data was given, update cache
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
# The min_precision parameter controls how many digits must be visible
def abbreviate(n, min_precision=2):
	num_digits = len(str(n))
	postfix_index = int((num_digits - min_precision) / 3)
	postfix = ["", "k", "M", "B"][postfix_index]
	return str(round(n / 1000**postfix_index)) + postfix

# Takes a potential rating, and a list of skillset ratings (one for each
# score). Returns a boolean, whether the given potential rating is
# 'okay', as I call it.
# 'values' must be given as numpy array (for numba compatibility)
@jit(nopython=True)
def is_rating_okay(rating, values):
	max_power_sum = 2 ** (0.1 * rating)
	power_sum = 0
	for value in values:
		power_sum += max(0, 2 / math.erfc(0.1 * (value - rating)) - 2)
	return power_sum < max_power_sum


"""
The idea is the following: we try out potential skillset rating values
until we've found the lowest rating that still fits (I've called that
property 'okay'-ness in the code).
How do we know whether a potential skillset rating fits? We give each
score a "power level", which is larger when the skillset rating of the
specific score is high. Therefore, the user's best scores get the 
highest power levels.
Now, we sum the power levels of each score and check whether that sum
is below a certain limit. If it is still under the limit, the rating
fits (is 'okay'), and we can try a higher rating. If the sum is above
the limit, the rating doesn't fit, and we need to try out a lower
rating.
"""
def find_skillset_rating(values):
	rating = 0
	resolution = 10.24
	
	# Repeatedly approximate the final rating, with better resolution
	# each time
	while resolution > 0.01:
		# Find lowest 'okay' rating with certain resolution
		while not is_rating_okay(rating + resolution, values):
			rating += resolution
		
		# Now, repeat with smaller resolution for better approximation
		resolution /= 2
	
	# Round to accommodate floating point errors
	return round(rating * 1.04, 2)


# `skillsets_values` should be a list with 7 sublists, one for each
# skillset containing all values from that skillset.
# Returns list with 8 elements: first is the Overall rating, following
# are the skillset ratings.
def find_ratings(skillsets_values):
	ratings = [find_skillset_rating(np.array(values)) for values in skillsets_values]
	overall = sum(ratings) / 7
	ratings.insert(0, overall)
	return ratings
