from typing import *

import xml.etree.ElementTree as ET

import util, replays_analysis
import data_generators as g
from plot_frame import PlotFrame, Plot, TextBox


def score_info(plotter, score):
	datetime = score.findtext("DateTime")
	percent = float(score.findtext("SSRNormPercent")) * 100
	percent = round(percent * 100) / 100 # Round to 2 places
	chart = util.find_parent_chart(plotter.xml, score)
	pack, song = chart.get("Pack"), chart.get("Song")
	
	if len(score.findall("SkillsetSSRs")) == 1:
		msd = round(g.score_to_msd(score), 2)
		score_value = float(score.findtext(".//Overall"))
		return f'{datetime}    {percent}%    MSD: {msd}    Score: {score_value}    "{pack}" -> "{song}"'
	else:
		util.logger.warning("Selected scatter point doesn't have SkillsetSSRs data")
		return f'{datetime}    {percent}%    "{pack}" -> "{song}"'

def session_info(plotter, data):
	(prev_rating, then_rating, num_scores, length) = data
	prev_rating = round(prev_rating, 2)
	then_rating = round(then_rating, 2)
	length = round(length)
	
	return f'From {prev_rating} to {then_rating}    Total {length} minutes ({num_scores} scores)'

class PlotEntry:
	plot = None
	data_generator = None
	analysis_requirement = None # "no", "yes" or "optional"
	
	def __init__(self, plot, generator, analysis_requirement):
		self.plot = plot
		self.data_generator = generator
		self.analysis_requirement = analysis_requirement

class Plotter:
	xml = analysis = None
	
	def __init__(self, infobar, prefs):
		frame = PlotFrame(infobar)
		self.frame = frame
		self.prefs = {} # The prefs that were last used. Empty in the beginning
		
		cmap = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
				'#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
		
		plots = []
		
		_ = TextBox(self, frame, 20, rowspan=2)
		plots.append(PlotEntry(_, g.gen_text_most_played_packs, "no"))
		_ = TextBox(self, frame, 10)
		plots.append(PlotEntry(_, g.gen_text_longest_sessions, "no"))
		_ = TextBox(self, frame, 19)
		plots.append(PlotEntry(_, g.gen_text_skillset_hours, "no"))
		_ = TextBox(self, frame, 11)
		plots.append(PlotEntry(_, g.gen_text_most_played_charts, "no"))
		self.frame.next_row()
		
		_ = TextBox(self, frame, 17)
		plots.append(PlotEntry(_, g.gen_text_general_analysis_info, "optional"))
		_ = TextBox(self, frame, 23)
		plots.append(PlotEntry(_, g.gen_text_general_info, "optional"))
		self.frame.next_row()
		
		plots.append(PlotEntry(Plot(self, frame,
			colspan=30,
			flags="time_xaxis",
			title="Score rating over time",
			color=cmap[0],
			click_callback=score_info),
			
			generator=g.gen_wifescore,
			analysis_requirement="no"))
		
		plots.append(PlotEntry(Plot(self, frame,
			colspan=30,
			flags="time_xaxis manip_yaxis",
			title="Manipulation over time (log scale)",
			color=cmap[3],
			click_callback=score_info),
			
			generator=g.gen_manip,
			analysis_requirement="yes"))
		self.frame.next_row()
		
		plots.append(PlotEntry(Plot(self, frame,
			colspan=30,
			flags="time_xaxis accuracy_yaxis",
			title="Accuracy over time (log scale)",
			color=cmap[1],
			click_callback=score_info),
			
			generator=g.gen_accuracy,
			analysis_requirement="no"))
		
		plots.append(PlotEntry(Plot(self, frame,
			colspan=30,
			flags="time_xaxis ma_yaxis",
			title="MA over time (marvelouses÷perfects) (log scale)",
			color=cmap[6],
			click_callback=score_info),
			
			generator=g.gen_ma,
			analysis_requirement="no"))
		self.frame.next_row()
		
		plots.append(PlotEntry(Plot(self, frame,
			colspan=30,
			type_="stacked line",
			flags="time_xaxis step",
			title="Skillsets over time",
			color=["ffffff", *util.skillset_colors], # Include overall
			legend=["Overall", *util.skillsets]), # Include overall
			
			generator=g.gen_skillset_development,
			analysis_requirement="no"))
		
		plots.append(PlotEntry(Plot(self, frame,
			colspan=30,
			type_="bubble",
			flags="time_xaxis",
			title="Rating improvement per session (x=date, y=session length, bubble size=rating improvement)",
			color=cmap[2],
			click_callback=session_info),
			
			generator=g.gen_session_rating_improvement,
			analysis_requirement="no"))
		self.frame.next_row()
		
		if prefs.enable_all_plots:
			plots.append(PlotEntry(Plot(self, frame,
				colspan=30,
				type_="bar",
				title="Distribution of hit offset",
				color=cmap[6]),
				
				generator=g.gen_hit_distribution,
				analysis_requirement="yes"))
			
			plots.append(PlotEntry(Plot(self, frame,
				colspan=30,
				type_="bar",
				title="Idle time between plays (a bit broken)",
				color=cmap[6]),
				
				generator=g.gen_idle_time_buckets,
				analysis_requirement="no"))
			self.frame.next_row()
			
			"""_ = Plot(self, frame, 30, title="CB probability based on combo length")
			_.set_draw_args(cmap[6], type_="bar")
			plots.append(PlotEntry(_, g.gen_cb_probability, "yes"))"""
			
			plots.append(PlotEntry(Plot(self, frame,
				colspan=30,
				type_="bar",
				title="Number of sessions with specific score amount",
				color=cmap[6]),
				
				generator=g.gen_session_plays,
				analysis_requirement="no"))
			self.frame.next_row()
			
			plots.append(PlotEntry(Plot(self, frame,
				colspan=30,
				flags="time_xaxis",
				title="Session length over time",
				color=cmap[6]),
				
				generator=g.gen_session_length,
				analysis_requirement="no"))
			
			plots.append(PlotEntry(Plot(self, frame,
				colspan=30,
				type_="bar",
				flags="time_xaxis",
				title="Number of scores each week",
				color=cmap[6],
				width=604800*0.8),
				
				generator=g.gen_plays_per_week,
				analysis_requirement="no"))
			self.frame.next_row()
		
		plots.append(PlotEntry(Plot(self, frame,
			colspan=30,
			type_="bar",
			title="Number of plays per hour of day",
			color=cmap[4]),
			
			generator=g.gen_plays_by_hour,
			analysis_requirement="no"))
		
		plots.append(PlotEntry(Plot(self, frame,
			colspan=30,
			type_="bar",
			flags="time_xaxis",
			title="Number of play-hours each week",
			color=cmap[5],
			width=604800*0.8),
			
			generator=g.gen_hours_per_week,
			analysis_requirement="no"))
		
		self.frame.next_row()
		
		plots.append(PlotEntry(Plot(self, frame,
			colspan=60,
			type_="stacked bar",
			title="Skillsets trained per week",
			color=util.skillset_colors,
			legend=util.skillsets),
			
			generator=g.gen_week_skillsets,
			analysis_requirement="no"))
		self.frame.next_row()
		
		self.plots = plots
	
	def draw(self, new_prefs, qapp):
		# Find what changed from the last draw
		changes = new_prefs.difference(self.prefs)
		self.prefs = new_prefs.to_dict()
		
		# Let the window draw itself once before the block loading and
		# analysis stuff
		qapp.processEvents()
		
		# Load XML if it changed
		xml_path = changes.get("etterna-xml")
		if xml_path:
			print("Opening xml..")
			try: # First try UTF-8
				xmltree = ET.parse(xml_path, ET.XMLParser(encoding='UTF-8'))
			except: # If that doesn't work, fall back to ISO-8859-1
				util.logger.exception("XML parsing with UTF-8 failed")
				xmltree = ET.parse(xml_path, ET.XMLParser(encoding='ISO-8859-1'))
			self.xml = xmltree.getroot()
		
		# Analyze replays if they changed
		replays_dir = changes.get("replays-dir")
		if replays_dir:
			print("Analyzing replays (this takes a while)..")
			self.analysis = replays_analysis.analyze(self.xml, replays_dir)
			# Analysis might be None if the analysis failed
		
		if xml_path: print("XML changed")
		if replays_dir: print("Replays changed")
		
		for i, plot in enumerate(self.plots):
			# If nothing relevant changed
			if not any([
				xml_path,
				replays_dir and plot.analysis_requirement != "no",
			]): continue
			
			print(f"Generating plot {i+1}")
			if plot.analysis_requirement == "no":
				data = (plot.data_generator)(self.xml)
			else:
				if self.analysis or plot.analysis_requirement == "optional":
					data = (plot.data_generator)(self.xml, self.analysis)
				else:
					data = "[please load replay data]"
				
			plot.plot.draw(data)
			qapp.processEvents()
		
		print("Done")
