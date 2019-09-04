import pyqtgraph as pg
from lxml import etree
from datetime import datetime
import numpy as np

import util
import data_generators as g

def parsedate(s): return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

# frame: GraphicsLayoutWidget to insert the plot into
# xml: Etterna.xml root node
# mapper: function to generate data
# color, alpha: color/alpha of the points
# mappertype: "xml" if mapper is called with `xml` as parameter, "score"
#  if mapper is called with a single score object
# time_xaxis: whether the x axis is a datetime axis
# type_: chart type: "scatter", "bar", or "stacked bar"
# colspan: how many columns the plot spans
# rowspan: how many rows the plot spans
def plot(frame, xml, mapper, color, alpha=0.4, mappertype="xml", mapper_args=[], time_xaxis=True, type_="scatter", colspan=1, rowspan=1):
	if mappertype == "xml":
		data = (mapper)(xml)
		if isinstance(data, dict): # If dict map key-value pairs to x-y
			x, y = list(data.keys()), list(data.values())
		else: # If list, map list to y and generate consecutive x values
			length = len(data[0]) if type_=="stacked bar" else len(data)
			x, y = range(length), data
		if time_xaxis: x = [value.timestamp() for value in x]
	elif mappertype == "score":
		x, y = [], []
		for score in xml.iter("Score"):
			result = (mapper)(score, *mapper_args)
			if result == None: continue
			y.append(result)
			
			timestamp = parsedate(score.findtext("DateTime")).timestamp()
			x.append(timestamp)
	
	if time_xaxis:
		axisItems = {"bottom": util.TimeAxisItem(orientation="bottom")}
	else:
		axisItems = {}
	
	plot = frame.addPlot(axisItems=axisItems, colspan=colspan, rowspan=rowspan)
	if type_ == "stacked bar":
		num_cols = len(y[0])
		bottom = [0] * num_cols
		for (row_i, row) in enumerate(y):
			item = pg.BarGraphItem(x=x, y0=list(bottom), height=row, width=0.8, pen=color[row_i], brush=color[row_i])
			bottom = [a+b for (a,b) in zip(bottom, row)] # We need out-of-place here
			plot.addItem(item)
	else:
		color = pg.mkColor(color)
		color.setAlphaF(alpha)
		if type_ == "scatter":
			item = pg.ScatterPlotItem(x, y, pen=None, brush=color)
		elif type_ == "bar":
			item = pg.BarGraphItem(x=x, height=y, width=0.8, pen=None, brush=color)
		plot.addItem(item)

class PlotFrame(pg.GraphicsLayoutWidget):
	def __init__(self, xml_path, replays_path):
		super().__init__()
		
		if xml_path == None: return
		self.xml = etree.parse(xml_path).getroot()
		self.replays_path = replays_path
	
	def draw(self):
		plot(self, self.xml, g.map_wifescore, "r", mappertype="score")
		plot(self, self.xml, g.map_accuracy, "c", mappertype="score")
		self.nextRow()
		plot(self, self.xml, g.gen_session_length, "m", time_xaxis=True)
		plot(self, self.xml, g.map_manip, "m", mappertype="score", mapper_args=[self.replays_path])
		self.nextRow()
		plot(self, self.xml, g.gen_plays_by_hour, "m", time_xaxis=False, type_="bar")
		plot(self, self.xml, g.gen_session_plays, "m", time_xaxis=False, type_="bar")
		self.nextRow()
		plot(self, self.xml, g.gen_session_skillsets, range(7), time_xaxis=False, type_="stacked bar", colspan=2)
		self.nextRow()
		plot(self, self.xml, g.gen_chart_play_distr, "m", time_xaxis=False, type_="bar")
	
