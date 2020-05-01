from typing import *

import sys
import xml.etree.ElementTree as ET

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

import data_generators as g
import replays_analysis, util, plot_frame


def show_scrollable_msgbox(text, title=None):
	scroll = QScrollArea()
	scroll.setWidget(QLabel(text))
	scroll.setFixedHeight(400)
	scroll.setWidgetResizable(True) # I dunno?
	
	msgbox = QDialog()
	# ~ msgbox.setModal(True) # don't block rest of the app
	if title: msgbox.setWindowTitle(title)
	msgbox_dummy_layout = QHBoxLayout(msgbox)
	msgbox_dummy_layout.addWidget(scroll)
	
	# I wish I could make this modal to not block the rest of the app, but the msgbox won#t show up
	# for some reason if I do that
	msgbox.exec_()

def show_score_info(xml, score):
	datetime = score.findtext("DateTime")
	percent = float(score.findtext("SSRNormPercent")) * 100
	percent = round(percent, 2)
	chart = util.find_parent_chart(xml, score)
	pack, song = chart.get("Pack"), chart.get("Song")
	
	if len(score.findall("SkillsetSSRs")) == 1:
		msd = round(g.score_to_msd(score), 2)
		score_value = float(score.findtext(".//Overall"))
		return f'{datetime}    {percent}%    MSD: {msd}    Score: {score_value}    "{pack}" -> "{song}"'
	else:
		util.logger.warning("Selected scatter point doesn't have SkillsetSSRs data")
		return f'{datetime}    {percent}%    "{pack}" -> "{song}"'

def show_session_info(data):
	(prev_rating, then_rating, num_scores, length) = data
	prev_rating = round(prev_rating, 2)
	then_rating = round(then_rating, 2)
	length = round(length)
	
	return f'From {prev_rating} to {then_rating}    Total {length} minutes ({num_scores} scores)'

cmap = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
		'#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

def draw(qapp, textbox_container: QWidget, pg_layout,
		xml_path: str, replays_path: Optional[str]) -> None:
	try: # First try UTF-8
		xmltree = ET.parse(xml_path, ET.XMLParser(encoding='UTF-8'))
	except: # If that doesn't work, fall back to system encoding
		os_encoding = sys.getdefaultencoding()
		
		# if the OS says it uses UTF-8, just use a naive 8 bit encoding anyway.
		# we don't want to fail again
		if os_encoding.lower() == "utf-8":
			os_encoding = "ISO-8859-1"
		
		util.logger.exception(f"XML parsing with UTF-8 failed, falling back to {os_encoding}")
		xmltree = ET.parse(xml_path, ET.XMLParser(encoding=os_encoding))
	
	xml = xmltree.getroot()
	# ~ replays_path = None # REMEMBER
	if replays_path:
		analysis = replays_analysis.analyze(xml, replays_path)
	else:
		analysis = None
	
	# both dark and light system theme compatibility :)
	sys_bgcolor = textbox_container.palette().color(textbox_container.backgroundRole())
	border_color = "white" if sys_bgcolor.lightness() < 128 else "black"
	
	textbox_grid = QGridLayout(textbox_container)
	def textbox(row: int, col: int, rowspan: int, colspan: int, fn, *args, read_more_title=None):
		text = (fn)(*args)
		label = QLabel(text)
		label.setWordWrap(True)
		label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
		label.setStyleSheet(f"border: 1px solid {border_color}; padding: 5px")
		textbox_grid.addWidget(label, row, col, rowspan, colspan)
		
		label.setOpenExternalLinks(False)
		label.linkActivated.connect(lambda _: show_scrollable_msgbox((fn)(*args, limit=None), read_more_title))
	
	textbox(0, 0, 2, 2, g.gen_text_most_played_packs, xml, read_more_title="Most played packs")
	textbox(0, 2, 1, 2, g.gen_text_longest_sessions, xml, read_more_title="Longest sessions")
	textbox(0, 4, 1, 2, g.gen_text_skillset_hours, xml)
	textbox(0, 6, 1, 2, g.gen_text_most_played_charts, xml, read_more_title="Most played charts")
	textbox(1, 2, 1, 3, g.gen_text_general_analysis_info, xml, analysis)
	textbox(1, 5, 1, 3, g.gen_text_general_info, xml, analysis)
	
	score_info_callback = lambda score: show_score_info(xml, score)
	
	qapp.processEvents()
	plot_frame.draw(pg_layout,
		flags="time_xaxis",
		title="Score rating over time",
		color=cmap[0],
		click_callback=score_info_callback,
		data=g.gen_wifescore(xml),
	)
	
	qapp.processEvents()
	plot_frame.draw(pg_layout,
		flags="time_xaxis manip_yaxis",
		title="Manipulation over time (log scale)",
		color=cmap[3],
		click_callback=score_info_callback,
		data=g.gen_manip(xml, analysis),
	)
	
	pg_layout.nextRow()
	
	qapp.processEvents()
	plot_frame.draw(pg_layout,
		flags="time_xaxis accuracy_yaxis",
		title="Accuracy over time (log scale)",
		color=cmap[1],
		click_callback=score_info_callback,
		data=g.gen_accuracy(xml),
	)
	
	qapp.processEvents()
	plot_frame.draw(pg_layout,
		flags="time_xaxis ma_yaxis",
		title="MA over time (marvelouses÷perfects) (log scale)",
		color=cmap[6],
		click_callback=score_info_callback,
		data=g.gen_ma(xml),
	)
	
	pg_layout.nextRow()
	
	qapp.processEvents()
	plot_frame.draw(pg_layout,
		type_="stacked line",
		flags="time_xaxis step",
		title="Skillsets over time",
		color=["ffffff", *util.skillset_colors], # Include overall
		legend=["Overall", *util.skillsets], # Include overall
		data=g.gen_skillset_development(xml),
	)
	
	qapp.processEvents()
	plot_frame.draw(pg_layout,
		type_="bubble",
		flags="time_xaxis",
		title="Rating improvement per session (x=date, y=session length, bubble size=rating improvement)",
		color=cmap[2],
		click_callback=show_session_info,
		data=g.gen_session_rating_improvement(xml),
	)
	
	pg_layout.nextRow()
	
	qapp.processEvents()
	plot_frame.draw(pg_layout,
		type_="bar",
		title="Number of plays per hour of day",
		color=cmap[4],
		data=g.gen_plays_by_hour(xml),
	)

	qapp.processEvents()
	plot_frame.draw(pg_layout,
		type_="bar",
		flags="time_xaxis",
		title="Number of play-hours each week",
		color=cmap[5],
		width=604800*0.8,
		data=g.gen_hours_per_week(xml),
	)

	pg_layout.nextRow()

	qapp.processEvents()
	plot_frame.draw(pg_layout,
		colspan=2,
		type_="stacked bar",
		title="Skillsets trained per week",
		color=util.skillset_colors,
		legend=util.skillsets,
		data=g.gen_week_skillsets(xml),
	)
