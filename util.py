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

class AccuracyAxisItem(pg.AxisItem):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.setLabel(units=None)
		self.enableAutoSIPrefix(False)

	def tickStrings(self, values, scale, spacing):
		result = []
		for value in values:
			value = 100-math.pow(10, -value)
			value = round(value * 1000) / 1000
			result.append(str(value) + "%")
		return result
