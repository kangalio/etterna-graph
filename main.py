from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import os, json

from plotter import Plotter
import util

"""
This file mainly handles the UI and overall program state
"""

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

XML_CANCEL_MSG = "You need to provide an Etterna.xml file for this program to work"
SETTINGS_PATH = "etterna-graph-settings.json"
IGNORE_REPLAYS = True

# QScrollArea wrapper with scroll wheel scrolling disabled.
# I did this to prevent simultaneous scrolling and panning 
# when hovering a plot while scrolling, which was annoying af.
class ScrollArea(QScrollArea):
	def wheelEvent(self, event):
		pass

# Handles UI
class UI:
	state = None # Reference to the enclosing Application object
	app = window = layout = None
	replays_button = None
	
	def __init__(self, state):
		self.state = state
		
		# Construct app, root widget and layout 
		app = QApplication(["Kangalioo's Etterna stats analyzer"])
		self.app = app
		app.setStyle("Fusion")
		
		# Prepare area for the widgets
		window = QMainWindow()
		self.window = window
		root = QWidget()
		layout = QVBoxLayout(root)
		self.layout = layout
		scroll = ScrollArea(window)
		scroll.setWidget(root)
		scroll.setWidgetResizable(True)
		window.setCentralWidget(scroll)
		
		# Put the widgets in
		self.setup_widgets(layout)
		
		# Start
		w, h = 1600, 2500
		root.setMinimumSize(1000, h)
		window.resize(w, h)
	
	def exec_(self):
		self.window.show()
		self.app.exec_()
	
	def setup_widgets(self, layout):
		# Add infobox
		toolbar = QToolBar()
		infobar = QLabel("This is the infobox. Press on a scatter point to see information about the score")
		infobar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
		infobar.setAlignment(Qt.AlignCenter)
		self.infobar = infobar
		toolbar.addWidget(infobar)
		self.window.addToolBar(Qt.BottomToolBarArea, toolbar)
		
		# Button row. Next three sections are the three buttons
		button_row_widget = QWidget()
		button_row = QHBoxLayout(button_row_widget)
		layout.addWidget(button_row_widget)
		
		# Load Replays button
		button = QPushButton("Load Replays")
		self.replays_button = button
		button.setToolTip("Replay data is required for various statistics")
		self.button_load_replays = button
		button_row.addWidget(button)
		button.clicked.connect(self.state.try_choose_replays)
		
		# About button
		button = QPushButton("About this program")
		button_row.addWidget(button)
		button.clicked.connect(
			lambda: QMessageBox.about(None, "About", ABOUT_TEXT))
		
		# Add plot frame (that thing that contains all the plots)
		self.plotter = Plotter(infobar)
		layout.addWidget(self.plotter.frame)
	
	# Returns path to Etterna.xml
	def choose_etterna_xml(self):
		result = QFileDialog.getOpenFileName(filter="Etterna XML files(*.xml)")
		path = result[0] # getOpenFileName returns tuple of path and filetype
		
		if path == "": return None
		return path
	
	# Returns path to ReplaysV2 directory
	def choose_replays(self):
		path = QFileDialog.getExistingDirectory(None, "Select ReplaysV2 folder")
		
		if path == "": return None # User cancelled the chooser
		return path
	
# Handles general application state
class Application:
	etterna_xml = None
	replays_dir = None
	ui = None
	plotter = None
	
	def __init__(self):
		self.ui = UI(self) # Init UI
		self.plotter = self.ui.plotter
		self.load_settings() # Apply settings
		
		# If Etterna.xml isn't already defined, let the user choose it
		if self.etterna_xml is None:
			path = self.ui.choose_etterna_xml()
			if path is None: # Dialog was cancelled
				QMessageBox.critical(None, "Error", XML_CANCEL_MSG)
				return
			self.etterna_xml = path
		
		self.refresh_graphs()
		
		self.ui.exec_() # Run program
	
	def refresh_graphs(self):
		self.plotter.draw(self.etterna_xml, self.replays_dir)
	
	def try_choose_replays(self):
		path = self.ui.choose_replays()
		if not path is None:
			self.set_replays(path)
			self.refresh_graphs()
	
	def set_replays(self, path):
		self.replays_dir = path
		self.ui.replays_button.setEnabled(False)
	
	def load_settings(self):
		if not os.path.exists(SETTINGS_PATH):
			return
		
		try:
			settings = json.load(open(SETTINGS_PATH))
			self.etterna_xml = settings["etterna-xml"]
			if not IGNORE_REPLAYS:
				self.set_replays(settings["replays-dir"])
		except Exception as e:
			util.logger.exception("Loading settings")
			msgbox = QMessageBox.warning(None, "Warning",
				"Could not load settings. Deleting them")
			# Overwrite old (prbly corrupted) settings
			self.write_settings()
	
	def write_settings(self):
		try:
			settings = {
				"etterna-xml": self.etterna_xml,
				"replays-dir": self.replays_dir
			}
			json.dump(settings, open(SETTINGS_PATH, "w"))
		except Exception as e:
			util.logger.exception("Writing settings")
			msgbox = QMessageBox.warning(None, "Warning",
				"Could not write settings")

try:
	application = Application()
except Exception:
	# Maybe send an automated E-Mail to me on Exception in the future?
	util.logger.exception("Main")
