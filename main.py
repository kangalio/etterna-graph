from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import os, json, socket, glob

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

REPLAYS_CHOOSER_INFO_MSG = """
In the following dialog you need to select the ReplaysV2 directory in
your 'Save' directory and click OK. Important: don't enter ReplaysV2
or try to select individual files within. This program requires you
to select the ReplaysV2 folder as a whole.
""".strip()

XML_CANCEL_MSG = "You need to provide an Etterna.xml file for this program to work"
SETTINGS_PATH = "etterna-graph-settings.json"
IGNORE_REPLAYS = True # Development purposes
if socket.gethostname() != "kangalioo-pc": IGNORE_REPLAYS = False

# QScrollArea wrapper with scroll wheel scrolling disabled.
# I did this to prevent simultaneous scrolling and panning 
# when hovering a plot while scrolling
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
		self.window.show()
	
	def exec_(self):
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
		QMessageBox.information(None, "How to use", REPLAYS_CHOOSER_INFO_MSG)
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
		
		# If Etterna.xml isn't already defined, search it
		if self.etterna_xml is None:
			self.detect_etterna()
			# If searching fails, ask user to choose Etterna.xml
			if self.etterna_xml is None:
				path = self.ui.choose_etterna_xml()
				if path is None: # Dialog was cancelled
					QMessageBox.critical(None, "Error", XML_CANCEL_MSG)
					return
				self.etterna_xml = path
		
		# Now, after the correct paths were established, save them
		self.write_settings()
		
		# Generate plots
		self.refresh_graphs()
		
		# Pass on control to Qt
		self.ui.exec_()
	
	# Detects an Etterna installation and sets etterna_xml and
	# replays_dir to the paths in it
	def detect_etterna(self):
		globs = [
			"C:\Games\Etterna*",
			os.path.expanduser("~") + "/.etterna*",
		]
		for glob_str in globs:
			for path in glob.iglob(glob_str):
				self.try_apply_paths(path)
	
	# Takes the path of an Etterna installation (e.g.
	# "/home/kangalioo/.etterna") and sets etterna_xml and replays_dir
	# correspondingly. If the path
	def try_apply_paths(self, path):
		etterna_xml = path + "/Save/LocalProfiles/00000000/Etterna.xml"
		if os.path.exists(etterna_xml):
			self.etterna_xml = etterna_xml
		
		replays_dir = path + "/Save/ReplaysV2"
		if os.path.exists(replays_dir):
			self.replays_dir = replays_dir
		
	
	def refresh_graphs(self):
		replays_dir = None if IGNORE_REPLAYS else self.replays_dir
		self.plotter.draw(self.etterna_xml, replays_dir, self.ui.app)
	
	def try_choose_replays(self):
		path = self.ui.choose_replays()
		if not path is None:
			self.set_replays(path)
			self.refresh_graphs()
	
	def set_replays(self, path):
		self.replays_dir = path
		self.write_settings()
	
	def load_settings(self):
		if not os.path.exists(SETTINGS_PATH):
			return
		
		try:
			settings = json.load(open(SETTINGS_PATH))
			self.etterna_xml = settings["etterna-xml"]
			if settings["replays-dir"]:
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
