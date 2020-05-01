from typing import *

import sys
import xml.etree.ElementTree as ET

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

import data_generators as g
import replays_analysis


cmap = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
		'#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

def draw(textbox_container: QWidget, pg_layout, xml_path: str, replays_path: Optional[str]) -> None:
	try: # First try UTF-8
		xmltree = ET.parse(xml_path, ET.XMLParser(encoding='UTF-8'))
	except: # If that doesn't work, fall back to system encoding
		os_encoding = sys.getdefaultencoding()
		
		# if the OS says it uses UTF-8, just use a naive 8 bit encoding anyway.
		# we don't want to fail again
		if os_encoding.lower() == "utf-8": os_encoding = "ISO-8859-1"
		
		util.logger.exception(f"XML parsing with UTF-8 failed, falling back to {os_encoding}")
		xmltree = ET.parse(xml_path, ET.XMLParser(encoding=os_encoding))
	
	xml = xmltree.getroot()
	replays_path = None # REMEMBER
	if replays_path:
		analysis = replays_analysis.analyze(xml, replays_path)
	else:
		analysis = None
	
	sys_bgcolor = textbox_container.palette().color(textbox_container.backgroundRole())
	border_color = "white" if sys_bgcolor.lightness() < 128 else "black"
	
	textbox_grid = QGridLayout(textbox_container)
	def textbox(row: int, col: int, rowspan: int, colspan: int, text: str):
		label = QLabel(text)
		label.setWordWrap(True)
		label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
		label.setStyleSheet(f"border: 1px solid {border_color}; padding: 5px")
		textbox_grid.addWidget(label, row, col, rowspan, colspan)
	
	textbox(0, 0, 2, 2, g.gen_text_most_played_packs(xml))
	textbox(0, 2, 1, 2, g.gen_text_longest_sessions(xml))
	textbox(0, 4, 1, 2, g.gen_text_skillset_hours(xml))
	textbox(0, 6, 1, 2, g.gen_text_most_played_charts(xml))
	textbox(1, 2, 1, 3, g.gen_text_general_analysis_info(xml, analysis))
	textbox(1, 5, 1, 3, g.gen_text_general_info(xml, analysis))
	
	
