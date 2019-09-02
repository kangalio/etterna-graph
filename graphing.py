from lxml import etree
import math
import numpy as np
import matplotlib.pyplot as plt

import data_generators as g


		

# Accepts canvas, Etterna.xml path and optionally ReplaysV2, and draws
# all the stuff on the canvas. For the scatter plots data generators
# from data_generators.py are used.
def draw_plots_old(canvas, xml_path, replays_dir=None):
	if xml_path == None: return
	
	data_functions = [g.gen_wife_score, g.gen_manipulation, g.gen_accuracy,
			g.gen_session_length]
	data_names = ["Wife score", "Manipulation (% of notes out of order)",
			"Accuracy (%)", "Session length (min)"]
	#data_scale = ["linear", "log", "log", "linear"]
	data_scale = ["linear", "linear", "linear", "linear"]
	
	xml = etree.parse(xml_path).getroot()

	plt.style.use("seaborn")
	previous_ax = None
	chart_amount = len(data_functions)
	num_cols = 2
	num_rows = math.ceil(chart_amount / num_cols)
	num_rows = 3 # REMEMBER
	for i in range(chart_amount):
		ax = canvas.add_subplot(num_rows, num_cols, i+1, sharex=previous_ax)
		#previous_ax = ax
		
		print(f"Generating scatter point set {i}...")
		data = (data_functions[i])(xml, replays_dir=replays_dir)
		if len(data) == 0: continue
		
		color = plt.get_cmap("Dark2")(i)
		x, y = data.keys(), data.values()
		ax.scatter(x, y, color=color, alpha=0.4)
		#ax.set_yscale(data_scale[i])
		#ax.set_ylim([min([a for a in y if a>0]), max(y)])
		ax.set_title(f"{data_names[i]} over time")
	
	ax = canvas.add_subplot(num_rows, num_cols, 5)
	diffsets = g.gen_session_diffsets(xml)
	diffsets = [[diffset[i] for diffset in diffsets] for i in range(7)]
	bottom = [0]*len(diffsets[0])
	for i in range(len(diffsets)):
		ax.bar(np.arange(len(diffsets[i])), diffsets[i], 1, bottom=bottom)
		for x in diffsets[i]: bottom[i] += x
	
	canvas.tight_layout()

def draw_plots(canvas, xml_path, replays_dir=None):
	if xml_path == None: return
	xml = etree.parse(xml_path).getroot()
	
	plt.style.use("seaborn")
	charts = [
		g.ScoreScatterChart(xml, "Wife score", g.map_wifescore),
		g.ScoreScatterChart(xml, "Manipulation", g.map_manip),
		g.ScoreScatterChart(xml, "Accuracy", g.map_accuracy),
		g.XMLScatterChart(xml, "Session length", g.gen_session_length),
		g.XMLBarChart(xml, "Plays by hour of day", g.gen_plays_by_hour),
		g.XMLStackedBarChart(xml, "Skillsets per seession", g.gen_session_skillsets),
		g.XMLBarChart(xml, "Number of sessions with x plays", g.gen_session_plays),
		g.XMLBarChart(xml, "Number of charts with x plays", g.gen_chart_play_distr),
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
