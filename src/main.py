from typing import *

import os, json, socket, glob

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

import plotter
import util
import app as app


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
IGNORE_REPLAYS = False # Development purposes
if socket.gethostname() != "kangalioo-pc": IGNORE_REPLAYS = False

SETTINGS_FIELDS = {
	"etterna-xml": "etterna_xml",
	"replays-dir": "replays_dir",
	"enable-all-plots": "enable_all_plots",
	"latest-known-release": "latest_known_release",
}
class Settings:
	etterna_xml = None
	replays_dir = None
	enable_all_plots = False
	latest_known_release = VERSION_NUMBER
	
	def load(self):
		if not os.path.exists(SETTINGS_PATH):
			return
		
		try:
			self.from_dict(json.load(open(SETTINGS_PATH)))
		except Exception:
			util.logger.exception("Loading settings")
			QMessageBox.warning(None, "Warning",
					"Could not load settings. Deleting them")
			# Overwrite old (prbly corrupted) settings
			self.write()
	
	def write(self):
		try:
			json.dump(self.to_dict(), open(SETTINGS_PATH, "w"), indent=4)
		except Exception:
			util.logger.exception("Writing settings")
			QMessageBox.warning(None, "Warning",
					"Could not write settings")
	
	def to_dict(self):
		return {json_key: getattr(self, attr)
				for json_key, attr in SETTINGS_FIELDS.items()}
	
	def from_dict(self, d):
		for json_key, attr in SETTINGS_FIELDS.items():
			value = d.get(json_key)
			if value is not None:
				setattr(self, attr, value)
	
	# Returns a dict, but with only the properties that are different
	# in the `other` settings dict
	def difference(self, other_dict):
		a, b = self.to_dict(), other_dict
		return {key: value for key, value in a.items()
				if b.get(key) != value}

class SettingsDialog(QDialog):
	xml_input = None
	replays_input = None
	button_box = None
	
	def __init__(self):
		super().__init__()
		self.setWindowTitle("Settings")
		
		vbox = QVBoxLayout(self)
		layout_widget = QWidget(self)
		vbox.addWidget(layout_widget)
		layout = QGridLayout(layout_widget)
		
		buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
		self.button_box = buttons
		buttons.clicked.connect(self.handle_button_click)
		vbox.addWidget(buttons)
		
		row_i = 0
		def add_setting(label, control):
			nonlocal row_i
			layout.addWidget(QLabel(label), row_i, 0)
			layout.addWidget(control, row_i, 1)
			row_i += 1
		
		self.xml_input = QLineEdit()
		add_setting("Etterna XML path", self.xml_input)
		
		self.replays_input = QLineEdit()
		add_setting("ReplaysV2 directory path", self.replays_input)
		
		self.enable_all = QCheckBox()
		add_setting("Enable legacy plots (restart to apply)", self.enable_all)
	
	def apply(self):
		# Copy the settings from UI to settings object
		app.app.prefs.etterna_xml = self.xml_input.text()
		app.app.prefs.replays_dir = self.replays_input.text()
		app.app.prefs.enable_all_plots = self.enable_all.isChecked()
		
		# Save settings and refresh graphs
		app.app.prefs.write()
		app.app.refresh_graphs()
	
	def handle_button_click(self, button):
		button = self.button_box.standardButton(button)
		if button == QDialogButtonBox.Apply:
			self.apply()
		elif button == QDialogButtonBox.Cancel:
			self.close()
		elif button == QDialogButtonBox.Ok:
			self.apply()
			self.close()
	
	def run(self):
		# Set settings UI to matching values
		self.xml_input.insert(app.app.prefs.etterna_xml)
		self.replays_input.insert(app.app.prefs.replays_dir)
		self.enable_all.setChecked(app.app.prefs.enable_all_plots)
		
		# Run the dialog
		self.exec_()

# Handles UI
class UI:
	qapp = window = layout = None
	replays_button = None
	settings_dialog = None
	
	def __init__(self):
		# Construct app, root widget and layout
		qapp = QApplication(["Kangalioo's Etterna stats analyzer"])
		self.qapp = qapp
		qapp.setStyle("Fusion")
		
		self.settings_dialog = SettingsDialog()
		
		# Prepare area for the widgets
		window = QMainWindow()
		self.window = window
		root = QWidget()
		layout = QVBoxLayout(root)
		self.layout = layout

		# Put the widgets in
		self.setup_widgets(layout)
		
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
		self.window.show()
	
	def exec_(self):
		self.qapp.exec_()
	
	def open_settings(self):
		self.settings_dialog.run()
	
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
		
		# About button
		button = QPushButton("About this program")
		button_row.addWidget(button)
		button.clicked.connect(lambda: QMessageBox.about(None, "About", ABOUT_TEXT))
		
		button = QPushButton("Settings")
		button_row.addWidget(button)
		button.clicked.connect(self.open_settings)
		
		import pyqtgraph as pg
		self.box_container = QWidget()
		layout.addWidget(self.box_container)
		self.pg_layout = pg.GraphicsLayoutWidget()
		layout.addWidget(self.pg_layout)
	
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
	
	def alert_new_release(self, name, is_prerelease):
		QMessageBox.information(None,
			"New version was released",
			NEW_VERSION_MSG.format(name))
	
# Handles general application state
class Application:
	prefs = None
	ui = None
	plotter = None
	
	def run(self):
		self.prefs = Settings()
		self.prefs.load() # Load settings
		self.ui = UI() # Init UI
		
		self.check_new_release()
		
		# If Etterna.xml isn't already defined, search it
		if self.prefs.etterna_xml is None:
			self.detect_etterna()
			# If searching fails, ask user to choose Etterna.xml
			if self.prefs.etterna_xml is None:
				path = self.ui.choose_etterna_xml()
				if path is None: # Dialog was cancelled
					QMessageBox.critical(None, "Error", XML_CANCEL_MSG)
					return
				self.prefs.etterna_xml = path
		
		# Generate plots
		plotter.draw(self.ui.qapp, self.ui.box_container, self.ui.pg_layout, self.prefs.etterna_xml, self.prefs.replays_dir)
		
		# Now, after the correct paths were established, save them
		self.prefs.write()
		
		# Pass on control to Qt
		self.ui.exec_()
	
	# Detects an Etterna installation and sets etterna_xml and
	# replays_dir to the paths in it
	def detect_etterna(self):
		globs = [
			"C:\\Games\\Etterna*", # Windows
			"C:\\Users\\*\\AppData\\*\\etterna*", # Windows
			os.path.expanduser("~") + "/.etterna*", # Linux
			os.path.expanduser("~") + "/.stepmania*", # Linux
			"/opt/etterna*", # Linux
			"Z:\\home\\kangalioo\\.etterna*", # My Wine on Linux (for testing)
			os.path.expanduser("~") + "/Library/Preferences/Etterna*", # Mac
		]
		# Assemble all possible save game locations. path_pairs is a
		# list of tuples `(xml_path, replays_dir_path)`
		path_pairs = []
		for glob_str in globs:
			for path in glob.iglob(glob_str):
				replays_dir = path + "/Save/ReplaysV2"
				possible_xml_paths = glob.iglob(path + "/Save/LocalProfiles/*/Etterna.xml")
				for xml_path in possible_xml_paths:
					path_pairs.append((xml_path, replays_dir))
		
		if len(path_pairs) == 0:
			return # No installation could be found
		elif len(path_pairs) == 1:
			# Only one was found, but maybe this is the wrong one and
			# the correct xml was not detected at all. Better ask
			mibs = os.path.getsize(path_pairs[0][0]) / 1024**2 # MiB's
			text = f"Detected an Etterna.xml ({mibs:.2f} MiB) at {path_pairs[0][0]}. Should the program use that?"
			reply = QMessageBox.question(None, "Which Etterna.xml?", text,
					QMessageBox.Yes, QMessageBox.No)
			if reply == QMessageBox.No: return
			path_pair = path_pairs[0]
		else: # With multiple possible installations, it's tricky
			# Select the savegame pair with the largest XML, ask user if that one is right
			path_pair = max(path_pairs, key=lambda pair: os.path.getsize(pair[0]))
			mibs = os.path.getsize(path_pair[0]) / 1024**2 # MiB's
			text = f"Found {len(path_pairs)} Etterna.xml's. The largest one \n({path_pair[0]})\nis {mibs:.2f} MiB; should the program use that?"
			reply = QMessageBox.question(None, "Which Etterna.xml?", text,
					QMessageBox.Yes, QMessageBox.No)
			if reply == QMessageBox.No: return
		
		# Apply the paths. Also, do a check if files exist. I mean, they
		# _should_ exist at this point, but you can never be too sure
		etterna_xml, replays_dir = path_pair
		if os.path.exists(etterna_xml):
			self.prefs.etterna_xml = etterna_xml
		if os.path.exists(replays_dir):
			self.prefs.replays_dir = replays_dir
	
	def try_choose_replays(self):
		path = self.ui.choose_replays()
		if path is not None:
			self.set_replays(path)
			self.refresh_graphs()
	
	def check_new_release(self):
		release = util.get_latest_release()
		tag_name = release["tag_name"]
		is_prerelease = release["prerelease"]
		if tag_name != self.prefs.latest_known_release:
			self.prefs.latest_known_release = tag_name
			self.prefs.write()
			self.ui.alert_new_release(tag_name, is_prerelease)

if __name__ == "__main__":
	try:
		app.app = Application()
		app.app.run()
	except Exception:
		# Maybe send an automated e-mail to me on Exception in the future?
		util.logger.exception("Main")
		input("Press enter to quit")
