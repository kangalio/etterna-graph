import pyqtgraph as pg
from datetime import datetime
import time
import math
from numba import jit
import numpy as np

# Parses date in Etterna.xml format
def parsedate(s): return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

class TimeAxisItem(pg.AxisItem):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.setLabel(units=None)
		self.enableAutoSIPrefix(False)

	def tickStrings(self, values, scale, spacing):
		return [datetime.fromtimestamp(value).strftime("%Y-%m-%d") for value in values]

class DIYLogAxisItem(pg.AxisItem):
	def __init__(self, accuracy, decimal_places, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.setLabel(units=None)
		self.enableAutoSIPrefix(False)
		
		self.accuracy = accuracy
		self.decimal_places = decimal_places

	def tickStrings(self, values, scale, spacing):
		result = []
		for value in values:
			if self.accuracy:
				value = 100-math.pow(10, -value)
			else:
				value = math.pow(10, value)
			value = round(value, self.decimal_places)
			result.append(str(value) + "%")
		return result

def find_parent_chart(xml, score):
	score_key = score.get("Key")
	return xml.find(f".//Score[@Key=\"{score_key}\"]/../..")

skillsets = ["Stream", "Jumpstream", "Handstream",
		"Stamina", "Jacks", "Chordjacks", "Technical"]

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
	overall = (sum(ratings) - min(ratings)) / 6
	ratings.insert(0, overall)
	return ratings
