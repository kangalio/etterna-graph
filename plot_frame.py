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
# click_callback: callback to call on scatter point click
# type_: chart type: "scatter", "bar", "bubble" or "stacked bar"
# colspan: how many columns the plot spans
# rowspan: how many rows the plot spans
# ids_included

class Tile:
	def __init__(self, frame, rowspan=1, colspan=1, flags="", title=None):
		global column
		
		self.flags = flags
		
		axisItems = {}
		if "time_xaxis" in flags:
			axisItems["bottom"] = util.TimeAxisItem(orientation="bottom")
		if "accuracy_yaxis" in flags:
			axisItems["left"] = util.DIYLogAxisItem(accuracy=True, decimal_places=3, orientation="left")
		elif "manip_yaxis" in flags:
			axisItems["left"] = util.DIYLogAxisItem(accuracy=False, decimal_places=1, orientation="left")
		
		plot = frame.addPlot(axisItems=axisItems, colspan=colspan, rowspan=rowspan)
		frame.maybe_advance_row()
		self.plot = plot
		plot.setTitle(title)
		if "log" in flags: plot.setLogMode(x=False, y=True)
	
	def draw(self, xml, mapper, color, alpha=0.4, mappertype="xml", mapper_args=[], legend=None, click_callback=None, type_="scatter", width=0.8):
		self.plot.clear()
		
		ids = None
		
		data = (mapper)(xml, *mapper_args)
		# We may have ids given which we need to separate
		if click_callback != None: (data, ids) = data
		if type_ == "bubble": (x, y, sizes) = data
		else: (x, y) = data
		
		if "time_xaxis" in self.flags:
			x = [value.timestamp() for value in x]
		
		if legend != None: self.plot.addLegend()
		
		if type_ == "stacked bar":
			y = list(zip(*y))
			num_cols = len(y[0])
			bottom = [0] * num_cols
			for (row_i, row) in enumerate(y):
				#item = pg.BarGraphItem(x=x, y0=bottom, height=row, width=1, pen=(0,0,0,255), brush=color[row_i])
				item = pg.BarGraphItem(x=x, y0=bottom, height=row, width=0.82, pen=color[row_i], brush=color[row_i])
				bottom = [a+b for (a,b) in zip(bottom, row)] # We need out-of-place here
				if legend != None: self.plot.legend.addItem(item, legend[row_i])
				self.plot.addItem(item)
		else:
			color = pg.mkColor(color)
			color.setAlphaF(alpha)
			if type_ == "scatter":
				item = pg.ScatterPlotItem(x, y, pen=None, size=8, brush=color, data=ids)
			elif type_ == "bar":
				item = pg.BarGraphItem(x=x, height=y, width=width, pen=(200,200,200), brush=color)
			elif type_ == "bubble":
				item = pg.ScatterPlotItem(x, y, pen=None, size=sizes, brush=color, data=ids)
			
			if click_callback != None:
				item.sigClicked.connect(click_callback)
			self.plot.addItem(item)

class TextBox:
	def __init__(self, frame):
		self.label = frame.addLabel(justify="left")
		frame.maybe_advance_row()
	def draw(self, text): self.label.setText(text)

class PlotFrame(pg.GraphicsLayoutWidget):
	def __init__(self, xml_path, infobar):
		super().__init__(border=(100,100,100))
		
		self.xml = etree.parse(xml_path).getroot()
		self.infobar = infobar
		self.column_counter = 0
		
		self.plots = [
			TextBox(self), TextBox(self), TextBox(self), TextBox(self),
			Tile(self, flags="time_xaxis", title="Wife score over time"),
			Tile(self, flags="time_xaxis manip_yaxis", title="Manipulation over time (log scale)"),
			Tile(self, flags="time_xaxis accuracy_yaxis", title="Accuracy over time (log scale)"),
			Tile(self, flags="time_xaxis", title="Rating improvement per session (x=date, y=session length, bubble size=rating improvement)"),
			Tile(self, title="Number of plays per hour of day"),
			Tile(self, flags="time_xaxis", title="Number of plays each week"),
			Tile(self, colspan=2, title="Skillsets trained per week"),
		]
	
	def maybe_advance_row(self):
		self.column_counter += 1
		if self.column_counter == 2:
			self.column_counter = 0
			self.nextRow()
	
	def scatter_info(self, score):
		datetime = score.findtext("DateTime")
		chart = util.find_parent_chart(self.xml, score)
		pack, song = chart.get("Pack"), chart.get("Song")
		percent = float(score.findtext("WifeScore"))*100
		percent = round(percent * 100) / 100 # Round to 2 places
		
		return f'{datetime}    {percent}%    "{pack}" -> "{song}"'
	
	def session_info(self, session):
		start = session[0][1]
		num_scores = len(session)
		
		return f'{start}    {num_scores} scores'
	
	def session_info2(self, data):
		(prev_rating, then_rating, num_scores, length) = data
		prev_rating = round(prev_rating, 2)
		then_rating = round(then_rating, 2)
		length = round(length)
		
		return f'From {prev_rating} to {then_rating}    Total {length} minutes ({num_scores} scores)'
	
	def click_handler(self, callback, points, _):
		if len(points) > 1:
			text = f"{len(points)} points selected at once!"
		else:
			text = (callback)(points[0].data())
		self.infobar.setText(text)
			
	def draw(self, replays_path):
		cmap = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',	'#9467bd',
				'#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
		
		score_callback = lambda *args: self.click_handler(self.score_info, *args)
		session_callback = lambda *args: self.click_handler(self.session_info, *args)
		sess_improvement_callback = lambda *args: self.click_handler(self.session_info2, *args)
		
		print("Generating textboxes..")
		self.plots[0].draw(gen_textbox_text(self.xml))
		self.plots[1].draw(gen_textbox_text_2(self.xml))
		self.plots[2].draw(gen_textbox_text_3(self.xml))
		self.plots[3].draw(gen_textbox_text_4(self.xml))
		print("Generating wifescore plot..")
		self.plots[4].draw(self.xml, g.gen_wifescore, cmap[0], click_callback=score_callback)
		print("Generating manip plot..")
		self.plots[5].draw(self.xml, g.gen_manip, cmap[3], mapper_args=[replays_path], click_callback=score_callback)
		print("Generating accuracy plot..")
		self.plots[6].draw(self.xml, g.gen_accuracy, cmap[1], click_callback=score_callback)
		print("Generating session bubble plot..")
		self.plots[7].draw(self.xml, g.gen_session_rating_improvement, cmap[2], type_="bubble", click_callback=sess_improvement_callback)
		print("Generating plays per hour of day..")
		self.plots[8].draw(self.xml, g.gen_plays_by_hour, cmap[4], type_="bar")
		print("Generating plays for each week..")
		self.plots[9].draw(self.xml, g.gen_plays_per_week, cmap[5], type_="bar", width=604800*0.8)
		print("Generating session skillsets..")
		self.plots[10].draw(self.xml, g.gen_session_skillsets, util.skillset_colors, legend=util.skillsets, type_="stacked bar")
		print("Done")

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

def gen_textbox_text_4(xml):
	from dateutil.relativedelta import relativedelta
	
	scores = list(xml.iter("Score"))
	hours = sum(float(s.findtext("SurviveSeconds")) / 3600 for s in scores)
	first_play_date = min([parsedate(s.findtext("DateTime")) for s in scores])
	duration = relativedelta(datetime.now(), first_play_date)
	
	return "<br>".join([
		f"You started playing {duration.years} years {duration.months} months ago",
		f"Total hours spent playing: {round(hours)} hours",
		f"Number of scores: {len(scores)}",
	])
	
