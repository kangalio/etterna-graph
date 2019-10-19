from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import os, json

from plotter import Plotter
import util

"""
This file mainly handles the UI and overall program state
"""

SETTINGS_PATH = "etterna-graph-settings.json"

infobox_text = """
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

# Like QScrollArea, but without scroll wheel scrolling :p
# I did this to prevent simultaneous scrolling and panning when hovering
# a plot while scrolling, which was annoying af.
class ScrollArea(QScrollArea):
	def wheelEvent(self, event):
		pass

class Application():
	etterna_xml = None
	replays_dir = None
	plotter = None
	
	def __init__(self):
		# Construct app, root widget and layout 
		app = QApplication(["Kangalioo's Etterna stats analyzer"])
		self.app = app
		app.setStyle("Fusion")
		
		window = QMainWindow()
		self.window = window
		root = QWidget()
		layout = QVBoxLayout(root)
		self.layout = layout
		scroll = ScrollArea(window)
		scroll.setWidget(root)
		scroll.setWidgetResizable(True)
		window.setCentralWidget(scroll)
		
		self.setup_ui(layout)
		
		# Start
		w, h = 1600, 2500
		root.setMinimumSize(1000, h)
		window.resize(w, h)
		window.show()
		app.exec_()
		
		self.update_settings()
	
	def setup_ui(self, layout):
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
		
		button = QPushButton("Reload Etterna.xml")
		self.button_load_xml = button
		button_row.addWidget(button)
		button.clicked.connect(self.try_choose_etterna_xml)
		
		button = QPushButton("Load Replays")
		button.setToolTip("Replay data is required for the manipulation chart")
		self.button_load_replays = button
		button_row.addWidget(button)
		button.clicked.connect(self.try_choose_replays)
		
		button = QPushButton("About this program")
		button_row.addWidget(button)
		button.clicked.connect(self.display_info_box)
		
		self.try_load_settings()
		
		self.try_choose_etterna_xml()
		
		# Add plot frame
		self.plotter = Plotter(infobar)
		layout.addWidget(self.plotter.frame)
		
		self.refresh_graphs()
		
		self.update_settings()
	
	def try_load_settings(self):
		try:
			if os.path.exists(SETTINGS_PATH):
				settings = json.load(open(SETTINGS_PATH))
				self.etterna_xml = settings["etterna-xml"]
				self.replays_dir = settings["replays-dir"]
		except Exception as e:
			msgbox = QMessageBox()
			msgbox.setText("Could not load settings")
			msgbox.exec_()
			self.update_settings()
	
	def update_settings(self):
		settings = {
			"etterna-xml": self.etterna_xml,
			"replays-dir": self.replays_dir
		}
		json.dump(settings, open(SETTINGS_PATH, "w"))
	
	def refresh_graphs(self):
		if not self.plotter is None:
			self.plotter.draw(self.etterna_xml, self.replays_dir)
	
	def display_info_box(self):
		msgbox = QMessageBox()
		msgbox.setText(infobox_text)
		msgbox.exec_()
	
	def mark_currently_loaded(self, button):
		current_text = button.text()
		if not current_text.endswith(" [currently loaded]"):
			button.setText(current_text + " [currently loaded]")
	
	def try_choose_etterna_xml(self):
		if self.etterna_xml is None:
			result = QFileDialog.getOpenFileName(filter="Etterna XML files(*.xml)")
			path = result[0] # getOpenFileName returns tuple of path and filetype
			
			if path == "": return # User cancelled the file chooser
			
			print(f"[UI] User selected Etterna.xml: {path}")
			self.mark_currently_loaded(self.button_load_xml)
			self.etterna_xml = path
		
		self.update_settings()
		util.clear_cache()
		self.refresh_graphs()
	
	def try_choose_replays(self):
		if self.replays_dir is None:
			path = QFileDialog.getExistingDirectory(None, "Select ReplaysV2 folder")
			
			if path == "": return # User cancelled the chooser
			
			print(f"[UI] User selected ReplaysV2: {path}")
			self.mark_currently_loaded(self.button_load_replays)
			self.replays_dir = path
		
		self.update_settings()
		util.clear_cache()
		self.refresh_graphs()

application = Application()
