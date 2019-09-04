import pyqtgraph as pg
from datetime import datetime
import time

# Parses date in Etterna.xml format
def parsedate(s): return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

class TimeAxisItem(pg.AxisItem):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.setLabel(text='Time', units=None)
		self.enableAutoSIPrefix(False)

	def tickStrings(self, values, scale, spacing):
		return [datetime.fromtimestamp(value).strftime("%Y-%m-%d") for value in values]

class AccuracyAxisItem(pg.AxisItem):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.setLabel(text='Accuracy', units=None)
		self.enableAutoSIPrefix(False)

	def tickStrings(self, values, scale, spacing):
		return [str(100-value)+"%" for value in values]
