from __future__ import annotations
from typing import *

import json
from dataclasses import dataclass

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

import plotter
import util
import app


"""
This file mainly handles the UI and overall program state
"""

VERSION_NUMBER = "v0.4"

ABOUT_TEXT = """
This was coded using PyQt5 and PyQtGraph in Python, by kangalioo.

The manipulation percentage is calculated by counting the number of
notes that were hit out of order. This is not optimal, but I think it
works well enough.

For session time calculation a session is defined to end when one play
is more than 20 minutes apart from the next play. Therefore a 15min
pause between playing would still count as one session, a 25 min pause
however would not.

Also, if you have any more plot ideas - scatter plot, bar chart,
whatever - I would be thrilled if you sent them to me, over
Discord/Reddit
""".strip() # strip() to remove leading and trailing newlines

REPLAYS_CHOOSER_INFO_MSG = """
In the following dialog you need to select the ReplaysV2 directory in
your 'Save' directory and click OK. Important: don't try to select
individual files within and don't choose another directory. This
program requires you to select the ReplaysV2 folder as a whole.
""".strip()

NEW_VERSION_MSG = f"""
Version {{0}} is available on the GitHub releases page.
This is version {VERSION_NUMBER}
""".strip()

XML_CANCEL_MSG = "You need to provide an Etterna.xml file for this program to work"
SETTINGS_PATH = "etterna-graph-settings.json"

_keep_storage = []
def keep(*args) -> None:
	_keep_storage.extend(args)

@dataclass
class Settings:
	xml_path: str
	replays_dir: str
	enable_all_plots: bool
	
	@staticmethod
	def load_from_json(path: str) -> Settings:
		with open(path) as f:
			j = json.load(f)
		
		return Settings(j["etterna-xml"], j["replays-dir"], j["enable-all-plots"])
	
	def save_to_json(self, path: str) -> None:
		json_data = {
			"etterna-xml": self.xml_path,
			"replays-dir": self.replays_dir,
			"enable-all-plots": self.enable_all_plots,
		}
		with open(path, "w") as f:
			json.dump(json_data, f)

class UI:
	def __init__(self):
		# Construct app, root widget and layout
		self.qapp = QApplication(["Kangalioo's Etterna stats analyzer"])
		self.qapp.setStyle("Fusion")
		
		# Prepare area for the widgets
		window = QMainWindow()
		root = QWidget()
		layout = QVBoxLayout(root)

		# Put the widgets in
		self.setup_widgets(layout, window)
		
		# QScrollArea wrapper with scroll wheel scrolling disabled on plots. I did this to prevent
		# simultaneous scrolling and panning when hovering a plot while scrolling
		class ScrollArea(QScrollArea):
			def eventFilter(self, obj, event) -> bool:
				if event.type() == QEvent.Wheel and self.ui_object.pg_layout.underMouse():
					return True
				return False
		scroll = ScrollArea(window)
		scroll.ui_object = self
		scroll.setWidget(root)
		scroll.setWidgetResizable(True)
		window.setCentralWidget(scroll)
		
		# Start
		w, h = 1600, 2500
		if app.app.prefs.enable_all_plots: h = 3800 # More plots -> more room
		root.setMinimumSize(1000, h)
		window.resize(w, h)
		window.show()
		keep(window)
	
	def run(self):
		self.qapp.exec_()
	
	def setup_widgets(self, layout, window):
		# Add infobox
		toolbar = QToolBar()
		infobar = QLabel("This is the infobox. Press on a scatter point to see information about the score")
		infobar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
		infobar.setAlignment(Qt.AlignCenter)
		self.infobar = infobar
		toolbar.addWidget(infobar)
		window.addToolBar(Qt.BottomToolBarArea, toolbar)
		
		import pyqtgraph as pg
		self.box_container = QWidget()
		layout.addWidget(self.box_container)
		self.pg_layout = pg.GraphicsLayoutWidget(border=pg.mkPen(255, 255, 255))
		layout.addWidget(self.pg_layout)
	
	def get_box_container_and_pg_layout(self):
		return self.box_container, self.pg_layout
	
	def get_qapp(self):
		return self.qapp

# Handles general application state
class Application:
	def run(self):
		self._prefs = Settings.load_from_json(SETTINGS_PATH)
		ui = UI()
		
		box_container, pg_container = ui.get_box_container_and_pg_layout()
		plotter.draw(ui.get_qapp(), box_container, pg_container, self._prefs)
		
		ui.run()
	
	@property
	def prefs(self):
		return self._prefs

if __name__ == "__main__":
	try:
		app.app = Application()
		app.app.run()
	except Exception:
		# Maybe send an automated e-mail to me on Exception in the future?
		util.logger.exception("Main")
		input("Press enter to quit")
