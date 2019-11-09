from lxml import etree
from multiprocessing import Process

from plot_frame import PlotFrame, Plot, TextBox
import data_generators as g
import util, replays_analysis

def score_info(plotter, score):
	datetime = score.findtext("DateTime")
	percent = float(score.findtext("WifeScore"))*100
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
	
	def __init__(self, plot, data_generator, analysis_requirement):
		self.plot = plot
		self.data_generator = data_generator
		self.analysis_requirement = analysis_requirement

class Plotter:
	def __init__(self, infobar):
		frame = PlotFrame(infobar)
		self.frame = frame
		
		cmap = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',	'#9467bd',
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
		
		_ = Plot(self, frame, 30, flags="time_xaxis", title="Wife score over time")
		_.set_args(cmap[0], click_callback=score_info)
		plots.append(PlotEntry(_, g.gen_wifescore, "no"))
		
		_ = Plot(self, frame, 30, flags="time_xaxis manip_yaxis", title="Manipulation over time (log scale)")
		_.set_args(cmap[3], click_callback=score_info)
		plots.append(PlotEntry(_, g.gen_manip, "yes"))
		self.frame.next_row()
		
		_ = Plot(self, frame, 30, flags="time_xaxis accuracy_yaxis", title="Accuracy over time (log scale)")
		_.set_args(cmap[1], click_callback=score_info)
		plots.append(PlotEntry(_, g.gen_accuracy, "no"))
		
		_ = Plot(self, frame, 30, flags="time_xaxis", title="Rating improvement per session (x=date, y=session length, bubble size=rating improvement)")
		_.set_args(cmap[2], type_="bubble", click_callback=session_info)
		plots.append(PlotEntry(_, g.gen_session_rating_improvement, "no"))
		self.frame.next_row()
		
		_ = Plot(self, frame, 30, flags="time_xaxis step", title="Skillsets over time")
		colors = ["ffffff", *util.skillset_colors] # Include overall
		legend = ["Overall", *util.skillsets] # Include overall
		_.set_args(colors, legend=legend, type_="stacked line")
		plots.append(PlotEntry(_, g.gen_skillset_development, "no"))
		
		# ~ _ = Plot(self, frame, 30, title="Distribution of hit offset")
		# ~ _.set_args(cmap[6], type_="bar")
		# ~ plots.append(PlotEntry(_, g.gen_hit_distribution, "yes"))
		# ~ self.frame.next_row()
		_ = Plot(self, frame, 30, title="Idle time between plays")
		_.set_args(cmap[6], type_="bar")
		plots.append(PlotEntry(_, g.gen_idle_time_buckets, "no"))
		self.frame.next_row()
		
		_ = Plot(self, frame, 30, title="Number of plays per hour of day")
		_.set_args(cmap[4], type_="bar")
		plots.append(PlotEntry(_, g.gen_plays_by_hour, "no"))
		
		_ = Plot(self, frame, 30, flags="time_xaxis", title="Number of play-hours each week")
		_.set_args(cmap[5], type_="bar", width=604800*0.8)
		plots.append(PlotEntry(_, g.gen_hours_per_week, "no"))
		self.frame.next_row()
		
		_ = Plot(self, frame, 60, title="Skillsets trained per week")
		_.set_args(util.skillset_colors, legend=util.skillsets, type_="stacked bar")
		plots.append(PlotEntry(_, g.gen_week_skillsets, "no"))
		self.frame.next_row()
		
		self.plots = plots
	
	def draw(self, xml_path, replays_path, qapp):
		print("Opening xml..")
		try: # First try UTF-8
			xmltree = etree.parse(xml_path, etree.XMLParser(encoding='UTF-8'))
		except: # If that doesn't work, fall back to ISO-8859-1
			util.logger.exception("XML parsing with UTF-8 failed")
			xmltree = etree.parse(xml_path, etree.XMLParser(encoding='ISO-8859-1'))
		xml = xmltree.getroot()
		self.xml = xml # This is required for the `score_info` callback
		
		# Let the window draw itself once before becoming unresponsive
		# for a while furing replays analysis
		qapp.processEvents()
		
		analysis = None
		if replays_path:
			print("Analyzing replays (this takes a while)..")
			analysis = replays_analysis.analyze(xml, replays_path)
			# Analysis might be None if the analysis failed
		
		for i, plot in enumerate(self.plots):
			print(f"Generating plot {i+1}")
			if plot.analysis_requirement == "no":
				data = (plot.data_generator)(xml)
			else:
				if analysis or plot.analysis_requirement == "optional":
					data = (plot.data_generator)(xml, analysis)
				else:
					data = "[please load replay data]"
				
			plot.plot.draw_with_given_args(data)
			qapp.processEvents()
		
		print("Done")
