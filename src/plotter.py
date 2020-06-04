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
	label.setTextInteractionFlags(label.textInteractionFlags() | Qt.TextSelectableByMouse);
	
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
		score_value = float(score.findtext(".//Overall"))
		text += f"Score rating: {score_value}    "
	else:
		util.logger.warning("Selected scatter point doesn't have SkillsetSSRs data")
	text += f'"{pack}" -> "{song}"'
	text += f'    <a href="read-more" style="color: {util.link_color()}">Show more</a>'
	
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
		
		lines.append("Scorekey: " + score.get("Key"))
		
		show_scrollable_msgbox("<br/>".join(lines), "Score info", word_wrap=True)
	
	app.app.set_infobar(text, lambda _link_name: show_all())

def show_session_info(data) -> None:
	(prev_rating, then_rating, num_scores, length) = data
	prev_rating = round(prev_rating, 2)
	then_rating = round(then_rating, 2)
	length = round(length)
	
	text = f'From {prev_rating} to {then_rating}    Total {length} minutes ({num_scores} scores)'
	text += '    <a href="read-more">Show more</a>'
	
	app.app.set_infobar(text)

cmap = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
		'#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

# returns a list of all the pyqtgraph widgets on which scrolling should be ignored
def draw(qapp, textbox_container: QWidget, plot_container: QWidget, prefs) -> List[QWidget]:
	try: # First try UTF-8
		xmltree = ET.parse(prefs.xml_path, ET.XMLParser(encoding='UTF-8'))
	except: # If that doesn't work, fall back to system encoding
		os_encoding = sys.getdefaultencoding()
		
		# if the OS says it uses UTF-8, just use a naive 8 bit encoding anyway.
		# we don't want to fail again
		if os_encoding.lower() == "utf-8":
			os_encoding = "ISO-8859-1"
		
		util.logger.exception(f"XML parsing with UTF-8 failed, falling back to {os_encoding}")
		xmltree = ET.parse(prefs.xml_path, ET.XMLParser(encoding=os_encoding))
	xml = xmltree.getroot()
	
	analysis = replays_analysis.analyze(xml, prefs.replays_dir)
	
	textbox_grid = QGridLayout(textbox_container)
	def textbox(row: int, col: int, rowspan: int, colspan: int, fn, *args,
			read_more_title=None, link_handler=lambda link: None, **kwargs):
		
		text = (fn)(*args, **kwargs)
		label = QLabel(text)
		label.setWordWrap(True)
		label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
		label.setTextInteractionFlags(label.textInteractionFlags() | Qt.TextSelectableByMouse);
		label.setStyleSheet(f"""
			border: 1px solid {util.border_color()};
			padding: 5px;
			font-size: 13px;
		""")
		
		existing_item = textbox_grid.itemAtPosition(row, col)
		if existing_item:
			textbox_grid.removeItem(existing_item)
		textbox_grid.addWidget(label, row, col, rowspan, colspan)
		
		def link_callback(link):
			if link == "#read_more" and read_more_title:
				show_scrollable_msgbox((fn)(*args, **kwargs, limit=None), read_more_title)
			else:
				(link_handler)(link)
		
		label.setOpenExternalLinks(False)
		label.linkActivated.connect(link_callback)
	
	textbox(0, 0, 4, 5, g.gen_text_most_played_charts, xml, read_more_title="Most played charts")
	def most_played_packs_textbox(all_time=False): # spaghetti
		read_more_title = "Most played packs (" + ("all time)" if all_time else "last 6 months)")
		textbox(4, 0, 8, 3, g.gen_text_most_played_packs, xml, months=None if all_time else 6,
				read_more_title=read_more_title,
				link_handler=lambda link: most_played_packs_textbox(all_time=not all_time))
	most_played_packs_textbox(all_time=False)
	textbox(0, 5, 4, 2, g.gen_text_skillset_hours, xml)
	textbox(0, 7, 4, 5, g.gen_text_longest_sessions, xml, read_more_title="Longest sessions")
	textbox(4, 3, 8, 5, g.gen_text_general_analysis_info, xml, analysis)
	textbox(4, 8, 8, 4, g.gen_text_general_info, xml, analysis)
	
	all_plots = [] # this will be filled in plotbox() and returned at the end
	
	plotbox_grid = QGridLayout(plot_container)
	plotbox_grid.setVerticalSpacing(10)
	plotbox_grid.setHorizontalSpacing(10)
	cur_row = 0
	cur_col = 0
	def plotbox(plot, title: str, colspan: int=1):
		nonlocal cur_row, cur_col
		
		all_plots.append(plot)
		
		container_widget = QWidget()
		container_widget.setStyleSheet(f"border: 1px solid {util.border_color()}")
		plotbox_grid.addWidget(container_widget, cur_row, cur_col, 1, colspan)
		container = QVBoxLayout(container_widget)
		container.setSpacing(0)
		
		# we set transparent borders here to prevent cascading the border setting from the container
		# widget. this css is in the label style sheet too, see below
		plot.setStyleSheet("border: 0px solid transparent")
		
		label = QLabel(title)
		label.setStyleSheet("font-size: 18px; font-weight: bold; border: 0px solid transparent")
		label.setWordWrap(True)
		label.setAlignment(Qt.AlignHCenter)
		util.keep(label)
		
		container.addWidget(label)
		container.addWidget(plot)
		cur_col += colspan
		if cur_col >= 2:
			cur_row += 1
			cur_col = 0
	
	score_info_callback = lambda score: show_score_info(xml, score)
	
	qapp.processEvents()
	plot = plot_frame.draw(
		flags="time_xaxis",
		color=cmap[0],
		click_callback=score_info_callback,
		data=g.gen_wifescore(xml),
	)
	plotbox(plot, "Score rating over time")
	
	qapp.processEvents()
	plot = plot_frame.draw(
		flags="time_xaxis manip_yaxis",
		log_axis_max_shown_value=99,
		color=cmap[3],
		click_callback=score_info_callback,
		data=g.gen_manip(xml, analysis),
	)
	plotbox(plot, "Manipulation over time (log scale)")
	
	qapp.processEvents()
	accuracy_data, brushes = g.gen_accuracy(xml, cmap[1])
	plot = plot_frame.draw(
		flags="time_xaxis accuracy_yaxis",
		log_axis_min_shown_value=-99,
		color=brushes,
		click_callback=score_info_callback,
		data=accuracy_data,
	)
	plotbox(plot, "Accuracy over time (log scale)")
	
	qapp.processEvents()
	plot = plot_frame.draw(
		flags="time_xaxis ma_yaxis",
		log_axis_max_shown_value=99,
		color=cmap[6],
		click_callback=score_info_callback,
		data=g.gen_ma(xml),
	)
	plotbox(plot, "MA over time (marvelouses÷perfects) (log scale)")
	
	qapp.processEvents()
	plot = plot_frame.draw(
		type_="bar",
		color=cmap[4],
		data=g.gen_plays_by_hour(xml),
	)
	plotbox(plot, "Number of plays per hour of day")
	
	qapp.processEvents()
	plot = plot_frame.draw(
		type_="bubble",
		flags="time_xaxis",
		color=cmap[2],
		click_callback=show_session_info,
		data=g.gen_session_rating_improvement(xml),
	)
	plotbox(plot, "Rating improvement per session (x=date, y=session length, bubble size=rating improvement)")
	
	qapp.processEvents()
	plot = plot_frame.draw(
		type_="line",
		flags="time_xaxis step thick_line",
		color=cmap[1],
		data=g.gen_cmod_over_time(xml),
	)
	plotbox(plot, "Effective CMod over time")
	
	qapp.processEvents()
	plot = plot_frame.draw(
		type_="bar",
		flags="time_xaxis",
		color=cmap[5],
		width=604800*0.8,
		data=g.gen_hours_per_week(xml),
	)
	plotbox(plot, "Number of play-hours each week")
	
	qapp.processEvents()
	plot = plot_frame.draw(
		type_="bar",
		color=cmap[6],
		flags="align_to_whole",
		data=g.gen_wifescore_frequencies(xml),
	)
	plotbox(plot, "Number of scores per wifescore percent")
	
	if prefs.enable_all_plots:
		qapp.processEvents()
		plot = plot_frame.draw(
			type_="scatter",
			flags="diagonal_line",
			color=cmap[0],
			data=((analysis.current_wifescores, analysis.new_wifescores), analysis.wifescore_scores),
			# data=(analysis.current_wifescores, analysis.new_wifescores),
			click_callback=score_info_callback,
		)
		plotbox(plot, "My rescoring impl (for developer purposes)")
		
		qapp.processEvents()
		plot = plot_frame.draw(
			type_="bar",
			color=cmap[3],
			data=g.gen_hit_distribution_sub_93(xml, analysis),
		)
		plotbox(plot, "Hit distribution (only sub 93% scores)")
		
		qapp.processEvents()
		plot = plot_frame.draw(
			type_="bar",
			color=cmap[6],
			data=g.gen_idle_time_buckets(xml),
		)
		plotbox(plot, "Idle time between plays (a bit broken)")
		
		# The following two were implemented based on an idea of snover. Unfortunately they didn't
		# provide much insight, so yeah, now they're here.
		
		qapp.processEvents()
		plot = plot_frame.draw(
			type_="bar",
			color=cmap[6],
			data=g.gen_avg_score_per_hour(xml),
		)
		plotbox(plot, "Average score rating per hour of day")
		
		qapp.processEvents()
		plot = plot_frame.draw(
			type_="scatter",
			color=cmap[6],
			click_callback=score_info_callback,
			data=g.gen_scores_per_hour(xml),
		)
		plotbox(plot, "Score ratings per hour of day")
		
		qapp.processEvents()
		plot = plot_frame.draw(
			type_="bar",
			color=cmap[6],
			data=g.gen_session_plays(xml),
		)
		plotbox(plot, "Number of sessions with specific score amount")
		
		qapp.processEvents()
		plot = plot_frame.draw(
			flags="time_xaxis",
			color=cmap[6],
			data=g.gen_session_length(xml),
		)
		plotbox(plot, "Session length over time")
		
		qapp.processEvents()
		plot = plot_frame.draw(
			type_="bar",
			flags="time_xaxis",
			color=cmap[6],
			width=604800*0.8,
			data=g.gen_plays_per_week(xml),
		)
		plotbox(plot, "Number of scores each week")
	
	qapp.processEvents()
	plot = plot_frame.draw(
		type_="stacked line",
		flags="time_xaxis step",
		color=["ffffff", *util.skillset_colors], # Include overall
		legend=["Overall", *util.skillsets], # Include overall
		data=g.gen_skillset_development(xml),
	)
	plotbox(plot, "Skillsets over time", colspan=2)

	qapp.processEvents()
	plot = plot_frame.draw(
		type_="stacked bar",
		color=util.skillset_colors,
		legend=util.skillsets,
		data=g.gen_week_skillsets(xml),
	)
	plotbox(plot, "Skillsets trained per week", colspan=2)
	
	return all_plots
