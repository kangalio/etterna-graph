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
# ids_included: whether mapper returns list of identifiers for the scatter points
# type_: chart type: "scatter", "bar", or "stacked bar"
# colspan: how many columns the plot spans
# rowspan: how many rows the plot spans
# ids_included
def plot(frame, xml, mapper, color, title, alpha=0.4, mappertype="xml", mapper_args=[], log=False, time_xaxis=False, accuracy_yaxis=False, manip_yaxis=False, legend=None, click_callback=None, type_="scatter", colspan=1, rowspan=1):
	ids_included = click_callback != None
	ids = None
	if mappertype == "xml":
		data = (mapper)(xml, *mapper_args)
		if ids_included: (data, ids) = data
		if isinstance(data, dict): # If dict map key-value pairs to x-y
			x, y = list(data.keys()), list(data.values())
		else: # If list, map list to y and generate consecutive x values
			length = len(data[0]) if type_=="stacked bar" else len(data)
			x, y = range(length), data
		if time_xaxis: x = [value.timestamp() for value in x]
	elif mappertype == "score":
		x, y = [], []
		if ids_included: ids = []
		for score in xml.iter("Score"):
			result = (mapper)(score, *mapper_args)
			if result == None: continue
			y.append(result)
			
			timestamp = parsedate(score.findtext("DateTime")).timestamp()
			x.append(timestamp)
			
			if ids_included: ids.append(score)
	
	axisItems = {}
	if time_xaxis:
		axisItems["bottom"] = util.TimeAxisItem(orientation="bottom")
	if accuracy_yaxis:
		axisItems["left"] = util.DIYLogAxisItem(accuracy=True, decimal_places=3, orientation="left")
	if manip_yaxis:
		axisItems["left"] = util.DIYLogAxisItem(accuracy=False, decimal_places=1, orientation="left")
	
	plot = frame.addPlot(axisItems=axisItems, colspan=colspan, rowspan=rowspan)
	plot.setTitle(title)
	if log: plot.setLogMode(x=False, y=True)
	if legend != None: plot.addLegend()
	
	if type_ == "stacked bar":
		y = list(zip(*y))
		num_cols = len(y[0])
		bottom = [0] * num_cols
		for (row_i, row) in enumerate(y):
			#item = pg.BarGraphItem(x=x, y0=bottom, height=row, width=1, pen=(0,0,0,255), brush=color[row_i])
			item = pg.BarGraphItem(x=x, y0=bottom, height=row, width=0.82, pen=color[row_i], brush=color[row_i])
			bottom = [a+b for (a,b) in zip(bottom, row)] # We need out-of-place here
			if legend != None: plot.legend.addItem(item, legend[row_i])
			plot.addItem(item)
	else:
		color = pg.mkColor(color)
		color.setAlphaF(alpha)
		if type_ == "scatter":
			item = pg.ScatterPlotItem(x, y, pen=None, size=8, brush=color, data=ids)
			if click_callback != None:
				item.sigClicked.connect(click_callback)
		elif type_ == "bar":
			item = pg.BarGraphItem(x=x, height=y, width=0.8, pen="w", brush=color)
		plot.addItem(item)

def text_box(frame, text):
	plot = frame.addLabel(text, justify="left")

class PlotFrame(pg.GraphicsLayoutWidget):
	def __init__(self, xml_path, replays_path, infobar):
		super().__init__(border=(100,100,100))
		
		self.xml = etree.parse(xml_path).getroot()
		self.replays_path = replays_path
		self.infobar = infobar
	
	def scatter_info(self, points):
		if len(points) > 1:
			return f"{len(points)} points selected at once!"
		
		score = points[0].data()
		datetime = score.findtext("DateTime")
		chart = util.find_parent_chart(self.xml, score)
		pack, song = chart.get("Pack"), chart.get("Song")
		percent = float(score.findtext("WifeScore"))*100
		percent = round(percent * 100) / 100 # Round to 2 places
		
		return f'{datetime}    {percent}%    "{pack}" -> "{song}"'
	
	def session_info(self, points):
		if len(points) > 1:
			return f"{len(points)} points selected at once!"
		
		session = points[0].data()
		start = session[0][1]
		num_scores = len(session)
		
		
		return f'{start}    {num_scores} scores'

	def draw(self):
		diffset_colors = [
			"333399", "6666ff", "cc33ff", "ff99cc",
			"009933", "66ff66", "808080"
		]
		
		# These are the official (unsaturated) EO colors
		#diffset_colors = ["7d6b91", "8481db", "995fa3", "f2b5fa", "6c969d", "a5f8d3", "b0cec2"]
		
		cmap = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',	'#9467bd',
				'#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
		
		score_callback = lambda _, points: self.infobar.setText(self.scatter_info(points))
		session_callback = lambda _, points: self.infobar.setText(self.session_info(points))
		
		text_box(self, gen_textbox_text(self.xml))
		text_box(self, gen_textbox_text_2(self.xml))
		self.nextRow()
		text_box(self, gen_textbox_text_3(self.xml))
		text_box(self, gen_textbox_text_4(self.xml))
		self.nextRow()
		
		plot(self, self.xml, g.map_wifescore, cmap[0], "Wife score over time",
			time_xaxis=True, mappertype="score", click_callback=score_callback)
		
		plot(self, self.xml, g.map_manip, cmap[3], "Manipulation over time (log scale)",
			time_xaxis=True, mappertype="score", mapper_args=[self.replays_path],
			manip_yaxis=True, click_callback=score_callback)
		
		#plot(self, self.xml, g.gen_cb_probability, cmap[3], "",
		#	mapper_args=[self.replays_path], type_="bar")
		
		#g.gen_cb_probability(self.xml, self.replays_path)
		self.nextRow()
		
		plot(self, self.xml, g.map_accuracy, cmap[1], "Accuracy over time (log scale)",
			#log=True, # log doesn't work on scatter charts
			time_xaxis=True, accuracy_yaxis=True, mappertype="score",
			click_callback=score_callback)
		plot(self, self.xml, g.gen_session_length, cmap[2], "Session length over time (min)",
			time_xaxis=True, click_callback=session_callback)
		
		self.nextRow()
		
		plot(self, self.xml, g.gen_plays_by_hour, cmap[4], "Number of plays per hour of day",
			type_="bar")
		self.nextRow()
		
		plot(self, self.xml, g.gen_session_skillsets, diffset_colors, "Skillsets trained per week",
			legend=util.skillsets, type_="stacked bar", colspan=2)
		self.nextRow()

def gen_textbox_text(xml):
	text = ["Most played charts:"]
	charts = g.gen_most_played_charts(xml, num_charts=5)
	i = 1
	for (chart, num_plays) in charts:
		pack, song = chart.get("Pack"), chart.get("Song")
		text.append(f"{i}) \"{pack}\" -> \"{song}\" with {num_plays} scores")
		i += 1
	
	return "<br>".join(text)

def gen_textbox_text_2(xml):
	sessions = g.divide_into_sessions(xml)
	sessions = [(s, (s[-1][1]-s[0][1]).total_seconds()/60) for s in sessions]
	sessions.sort(key=lambda pair: pair[1], reverse=True) # Sort by length
	sessions = sessions[:5]
	
	text = ["Longest sessions:"]
	i = 1
	for (session, length) in sessions:
		num_plays = len(session)
		datetime = session[0][1]
		text.append(f"{i}) {datetime}, {round(length)} minutes long with {num_plays} scores")
		i += 1
	
	return "<br>".join(text)

def gen_textbox_text_3(xml):
	hours = g.gen_hours_per_skillset(xml)
	
	text = ["Hours spent training each skillset"]
	for i in range(7):
		skillset = util.skillsets[i]
		m_total = int(hours[i] * 60)
		h = int(m_total / 60)
		m = m_total - 60 * h
		text.append(f"- {skillset}: {h}h {m}min")
	
	return "<br>".join(text)

"""
You've been playing: {}
Number of scores: {}
You started playing {} ago
"""
def gen_textbox_text_4(xml):
	from dateutil.relativedelta import relativedelta
	
	scores = list(xml.iter("Score"))
	hours = sum(float(s.findtext("SurviveSeconds")) / 3600 for s in scores)
	first_play_date = min([parsedate(s.findtext("DateTime")) for s in scores])
	duration = relativedelta(datetime.now(), first_play_date)
	
	return "<br>".join([
		f"Total hours spent playing: {round(hours)} hours",
		f"Number of scores: {len(scores)}",
		f"You started playing {duration.years} years {duration.months} months ago"
	])
	
