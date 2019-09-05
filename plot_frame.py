import pyqtgraph as pg
from lxml import etree
from datetime import datetime
import numpy as np

import util
from util import parsedate
import data_generators as g

# This is a big function thata handles almost all graphics library
# interaction. Parameters:
# 
# frame: GraphicsLayoutWidget to insert the plot into
# xml: Etterna.xml root node
# mapper: function to generate data
# color, alpha: color/alpha of the points
# mappertype: "xml" if mapper is called with `xml` as parameter, "score"
#   if mapper is called with a single score object
# mapper_args: additional call parameters for the mapper
# log: whether to use log scale for x axis. Because of pyqtgraph
#   restrictions it only works for PlotDataItems (line charts)
# time_xaxis: whether the x axis is a datetime axis
# accuracy_yacis: whether the yaxis is an accuracy axis
# legend: color names
# type_: chart type: "scatter", "bar", or "stacked bar"
# colspan: how many columns the plot spans
# rowspan: how many rows the plot spans
def plot(frame, xml, mapper, color, title, alpha=0.4, mappertype="xml", mapper_args=[], log=False, time_xaxis=False, accuracy_yaxis=False, legend=None, type_="scatter", colspan=1, rowspan=1):
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
	
	axisItems = {}
	if time_xaxis:
		axisItems["bottom"] = util.TimeAxisItem(orientation="bottom")
	if accuracy_yaxis:
		axisItems["left"] = util.AccuracyAxisItem(orientation="left")
	
	plot = frame.addPlot(axisItems=axisItems, colspan=colspan, rowspan=rowspan)
	plot.setTitle(title)
	if log: plot.setLogMode(x=False, y=True)
	if legend != None: plot.addLegend()
	
	if type_ == "stacked bar":
		num_cols = len(y[0])
		bottom = [0] * num_cols
		for (row_i, row) in enumerate(y):
			item = pg.BarGraphItem(x=x, y0=bottom, height=row, width=1, pen=color[row_i], brush=color[row_i])
			bottom = [a+b for (a,b) in zip(bottom, row)] # We need out-of-place here
			if legend != None: plot.legend.addItem(item, legend[row_i])
			plot.addItem(item)
	else:
		color = pg.mkColor(color)
		color.setAlphaF(alpha)
		if type_ == "scatter":
			item = pg.ScatterPlotItem(x, y, pen=None, brush=color)
		elif type_ == "bar":
			item = pg.BarGraphItem(x=x, height=y, width=0.8, pen="w", brush=color)
		plot.addItem(item)
	
	#if log: plot.setLogMode(True, False)

class PlotFrame(pg.GraphicsLayoutWidget):
	def __init__(self, xml_path, replays_path):
		super().__init__(border=(100,100,100))
		
		if xml_path == None: return
		self.xml = etree.parse(xml_path).getroot()
		self.replays_path = replays_path
	
	def draw(self):
		diffsets = [
			("333399", "Stream"),
			("6666ff", "Jumpstream"),
			("cc33ff", "Handstream"),
			("ff99cc", "Stamina"),
			("009933", "Jackspeed"),
			("66ff66", "Chordjack"),
			("808080", "Technical")
		]
		diffset_colors, diffset_names = zip(*diffsets) # Unzip
		
		plot(self, self.xml, g.map_wifescore, "r", "Wife score over time",
			time_xaxis=True, mappertype="score")
		plot(self, self.xml, g.map_accuracy, "c", "Accuracy over time",
			#log=True, # log doesn't work on scatter charts
			time_xaxis=True, accuracy_yaxis=True, mappertype="score")
		self.nextRow()
		
		plot(self, self.xml, g.gen_session_length, "m", "Session length over time",
			time_xaxis=True)
		plot(self, self.xml, g.map_manip, "m", "Manipulation over time",
			time_xaxis=True, mappertype="score", mapper_args=[self.replays_path])
		self.nextRow()
		
		plot(self, self.xml, g.gen_plays_by_hour, "m", "Number of plays per hour of day",
			type_="bar")
		plot(self, self.xml, g.gen_session_plays, "m", "Number of sessions with x plays",
			type_="bar")
		self.nextRow()
		
		plot(self, self.xml, g.gen_session_skillsets, diffset_colors, "Skillsets trained during sessions (only those with >5 scores)",
			legend=diffset_names, type_="stacked bar", colspan=2)
		self.nextRow()
		
		plot(self, self.xml, g.gen_chart_play_distr, "m", "Number of charts with x plays",
			type_="bar")
	
