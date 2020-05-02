from typing import *

import sys
import xml.etree.ElementTree as ET

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

import data_generators as g
import replays_analysis, util, plot_frame, app


def show_scrollable_msgbox(text, title=None, word_wrap=False):
	label = QLabel(text)
	label.setWordWrap(word_wrap)
	
	scroll = QScrollArea()
	scroll.setMinimumWidth(label.sizeHint().width() + 45)
	scroll.setStyleSheet("padding: 1px");
	scroll.setWidget(label)
	scroll.setMaximumHeight(400)
	scroll.setWidgetResizable(True) # I dunno?
	
	msgbox = QDialog()
	# ~ msgbox.setModal(True) # don't block rest of the app
	if title: msgbox.setWindowTitle(title)
	msgbox_dummy_layout = QHBoxLayout(msgbox)
	msgbox_dummy_layout.addWidget(scroll)
	
	# I wish I could make this modal to not block the rest of the app, but the msgbox won#t show up
	# for some reason if I do that
	msgbox.exec_()

def show_score_info(xml, score) -> None:
	datetime = score.findtext("DateTime")
	wifescore = float(score.findtext("SSRNormPercent"))
	chart = util.find_parent_chart(xml, score)
	pack, song = chart.get("Pack"), chart.get("Song")
	
	text = f"{datetime}    {100*wifescore:.2f}%    "
	if len(score.findall("SkillsetSSRs")) == 1:
		msd = round(g.score_to_msd(score), 2)
		score_value = float(score.findtext(".//Overall"))
		text += f"Approx. MSD: {msd}    Score: {score_value}    "
	else:
		util.logger.warning("Selected scatter point doesn't have SkillsetSSRs data")
	text += f'"{pack}" -> "{song}"'
	text += '    <a href="read-more">Show more</a>'
	
	def show_all():
		lines = [
			f"<b>{song}</b> ({pack})",
			f"- <b>{100*wifescore:.2f}%</b> ({util.wifescore_to_grade_string(wifescore)})",
			f"- Max combo: <b>{score.findtext('MaxCombo')}x</b>",
			f"- Modifiers: <b>\"{score.findtext('Modifiers')}\"</b>",
		]
		
		tap_note_scores = score.find("TapNoteScores")
		names = ["W1", "W2", "W3", "W4", "W5", "Miss"]
		lines.append("- <b>" + " / ".join(tap_note_scores.findtext(name) for name in names) + "</b>")
		
		hit_mine = int(tap_note_scores.findtext("HitMine"))
		avoid_mine = int(tap_note_scores.findtext("AvoidMine"))
		try:
			mine_avoided_ratio = avoid_mine / (hit_mine + avoid_mine)
		except ZeroDivisionError:
			mine_avoided_ratio = 1 # when there's no mines at all, just say the player has hit 100%
		lines.append(f"- Avoided <b>{avoid_mine}/{hit_mine + avoid_mine}</b> mines (<b>{mine_avoided_ratio*100:.2f}%</b>)")
		
		hold_note_scores = score.find("HoldNoteScores")
		let_go = int(hold_note_scores.findtext("LetGo"))
		held = int(hold_note_scores.findtext("Held"))
		missed_hold = int(hold_note_scores.findtext("MissedHold"))
		total_holds = let_go + held + missed_hold
		try:
			held_ratio = held / total_holds
		except ZeroDivisionError:
			held_ratio = 1
		lines.append(f"- Held <b>{held}/{total_holds}</b> holds (<b>{held_ratio*100:.2f}%</b>)")
		
		skillset_ssrs = score.find("SkillsetSSRs")
		if skillset_ssrs:
			lines.append(f"- Overall score rating: <b>{skillset_ssrs.findtext('Overall')}</b>")
			for skillset_elem in skillset_ssrs:
				if skillset_elem.tag == "Overall": continue # we already showed that
				lines.append(f"=> {skillset_elem.tag}: <b>{skillset_elem.text}</b>")
		
		show_scrollable_msgbox("<br/>".join(lines), "Score info", word_wrap=True)
	
	# REMEMBER
	show_all()
	return
	
	app.app.set_infobar(text, lambda link_name: show_all())

def show_session_info(data) -> None:
	(prev_rating, then_rating, num_scores, length) = data
	prev_rating = round(prev_rating, 2)
	then_rating = round(then_rating, 2)
	length = round(length)
	
	text = f'From {prev_rating} to {then_rating}    Total {length} minutes ({num_scores} scores)'
	text += '    <a href="read-more">Show more</a>'
	
	def show_all():
		show_scrollable_msgbox(text, "Session info", word_wrap=True)
	
	app.app.set_infobar(text, lambda link_name: show_all())

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
	
	return # REMEMBER
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
