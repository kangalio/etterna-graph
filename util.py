import pyqtgraph as pg
from datetime import datetime
import time
import math

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
