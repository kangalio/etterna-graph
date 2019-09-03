from lxml import etree
import math
import numpy as np
import matplotlib.pyplot as plt

import data_generators as g


# Implements a scatter chart with datetime over x-axis. Y values are
# different per instance via the given chart_mapper function.
class ScoreScatterChart:
	def __init__(self, xml, name, score_mapper):
		self.name = name
		self.xml = xml
		self.score_mapper = score_mapper
	
	def calculate(self, **kwargs):
		self.data = {}
		for score in self.xml.iter("Score"):
			datetime = parsedate(score.find("DateTime").text)
			value = (self.score_mapper)(score, **kwargs)
			self.data[datetime] = value
	
	def draw(self, ax, index):
		color = plt.get_cmap("Dark2")(index)
		x, y = self.data.keys(), self.data.values()
		ax.scatter(x, y, color=color, alpha=0.4)
		ax.set_title(self.name)

class XMLScatterChart(ScoreScatterChart):
	def calculate(self, **kwargs):
		self.data = (self.score_mapper)(self.xml)

class XMLBarChart(XMLScatterChart):
	def draw(self, ax, index):
		color = plt.get_cmap("Dark2")(index)
		x, y = self.data.keys(), self.data.values()
		ax.bar(x, y, color=color)
		ax.set_title(self.name)

class XMLStackedBarChart(XMLScatterChart):
	def draw(self, ax, index):
		ax.set_title(self.name)
		
		self.data = self.data[-30:]
		num_sessions = len(self.data)
		bottom = [0] * num_sessions
		for j in range(7):
			color = plt.get_cmap("Dark2_r")(j) # TODO use official color palette
			amounts = [self.data[i][j] for i in range(num_sessions)]
			x = np.arange(num_sessions)
			ax.bar(x, amounts, width=0.9, bottom=bottom, color=color)
			for i in range(num_sessions): bottom[i] += amounts[i]

# Accepts canvas, Etterna.xml path and optionally ReplaysV2, and draws
# all the stuff on the canvas. For the scatter plots data generators
# from data_generators.py are used.
def draw_plots(canvas, xml_path, replays_dir=None):
	if xml_path == None: return
	xml = etree.parse(xml_path).getroot()
	
	plt.style.use("seaborn")
	charts = [
		ScoreScatterChart(xml, "Wife score", g.map_wifescore),
		ScoreScatterChart(xml, "Manipulation", g.map_manip),
		ScoreScatterChart(xml, "Accuracy", g.map_accuracy),
		XMLScatterChart(xml, "Session length", g.gen_session_length),
		XMLBarChart(xml, "Plays by hour of day", g.gen_plays_by_hour),
		XMLStackedBarChart(xml, "Skillsets per seession", g.gen_session_skillsets),
		XMLBarChart(xml, "Number of sessions with x plays", g.gen_session_plays),
		XMLBarChart(xml, "Number of charts with x plays", g.gen_chart_play_distr),
	]
	for chart in charts:
		if chart.name == "Manipulation":
			chart.calculate(replays_dir=replays_dir)
		else:
			chart.calculate()
			
	for i, chart in enumerate(charts):
		ax = canvas.add_subplot(4, 2, i+1)
		chart.draw(ax, i)
	
	canvas.tight_layout()
