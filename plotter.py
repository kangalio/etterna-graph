from lxml import etree

from plot_frame import PlotFrame, Plot, TextBox
import data_generators as g
import util
import structures

def score_info(self, score):
	datetime = score.findtext("DateTime")
	chart = util.find_parent_chart(self.xml, score)
	pack, song = chart.get("Pack"), chart.get("Song")
	percent = float(score.findtext("WifeScore"))*100
	percent = round(percent * 100) / 100 # Round to 2 places
	
	return f'{datetime}    {percent}%    "{pack}" -> "{song}"'

def session_info(self, data):
	(prev_rating, then_rating, num_scores, length) = data
	prev_rating = round(prev_rating, 2)
	then_rating = round(then_rating, 2)
	length = round(length)
	
	return f'From {prev_rating} to {then_rating}    Total {length} minutes ({num_scores} scores)'

class Plotter:
	def __init__(self, infobar):
		frame = PlotFrame(infobar)
		self.frame = frame
		
		self.plots = [
			TextBox(frame), TextBox(frame), TextBox(frame), TextBox(frame),
			Plot(frame, flags="time_xaxis", title="Wife score over time"),
			Plot(frame, flags="time_xaxis manip_yaxis", title="Manipulation over time (log scale)"),
			Plot(frame, flags="time_xaxis accuracy_yaxis", title="Accuracy over time (log scale)"),
			Plot(frame, flags="time_xaxis", title="Rating improvement per session (x=date, y=session length, bubble size=rating improvement)"),
			Plot(frame, title="Number of plays per hour of day"),
			Plot(frame, flags="time_xaxis", title="Number of plays each week"),
			Plot(frame, colspan=2, title="Skillsets trained per week"),
		]
	
	def draw(self, xml_path, replays_path):
		print("Opening xml..")
		xml = etree.parse(xml_path).getroot()
		print("Parsing replays..")
		if replays_path: replays = structures.Replays(xml, replays_path)
		else: replays = None
		
		cmap = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',	'#9467bd',
				'#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
		
		print("Generating textboxes..")
		self.plots[0].draw(g.gen_textbox_text(xml))
		self.plots[1].draw(g.gen_textbox_text_2(xml))
		self.plots[2].draw(g.gen_textbox_text_3(xml))
		self.plots[3].draw(g.gen_textbox_text_4(xml))
		print("Generating wifescore plot..")
		self.plots[4].draw(xml, g.gen_wifescore, cmap[0], click_callback=score_info)
		print("Generating manip plot..")
		if replays:
			self.plots[5].draw(xml, g.gen_manip, cmap[3], mapper_args=[replays], click_callback=score_info)
		print("Generating accuracy plot..")
		self.plots[6].draw(xml, g.gen_accuracy, cmap[1], click_callback=score_info)
		print("Generating session bubble plot..")
		self.plots[7].draw(xml, g.gen_session_rating_improvement, cmap[2], type_="bubble", click_callback=session_info)
		print("Generating plays per hour of day..")
		self.plots[8].draw(xml, g.gen_plays_by_hour, cmap[4], type_="bar")
		print("Generating plays for each week..")
		self.plots[9].draw(xml, g.gen_plays_per_week, cmap[5], type_="bar", width=604800*0.8)
		print("Generating session skillsets..")
		self.plots[10].draw(xml, g.gen_session_skillsets, util.skillset_colors, legend=util.skillsets, type_="stacked bar")
		print("Done")
