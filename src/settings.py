from __future__ import annotations
from typing import *

import os, json
from enum import Enum
from dataclasses import dataclass

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

import util
import app


SETTINGS_PATH = "etterna-graph-settings.json"

REPLAYS_CHOOSER_INFO_MSG = """<p>
In the following dialog you need to select the ReplaysV2 directory in
your 'Save' directory and click OK. Important: don't try to select
individual files within and don't choose a different directory. This
program requires you to select the ReplaysV2 folder as a whole.
</p>"""

SONGS_ROOT_CHOOSER_INFO_MSG = """<p>
In the following dialog you need to select the Songs directory and click OK. Important: don't try to
select individual files within and don't choose a different directory. This
program requires you to select the Songs folder as a whole.
</p>"""

def try_select_xml() -> Optional[str]:
	result = QFileDialog.getOpenFileName(
			caption="Select your Etterna.xml",
			filter="Etterna XML files(Etterna.xml)")
	return result[0] if result else None

def try_choose_replays() -> Optional[str]:
	QMessageBox.information(None, "How to use", REPLAYS_CHOOSER_INFO_MSG)
	return QFileDialog.getExistingDirectory(
			caption="Select the ReplaysV2 directory")

def try_choose_songs_root() -> Optional[str]:
	QMessageBox.information(None, "How to use", SONGS_ROOT_CHOOSER_INFO_MSG)
	return QFileDialog.getExistingDirectory(
			caption="Select the root songs folder")

# when adding a new settings type, keep care to update the code at "# setting here"
SettingsType = Enum("SettingsType", ["File", "Folder", "Color", "Checkbox", "Spinbox"])

@dataclass(frozen=True)
class SettingsEntry:
	python_name: str
	json_name: str
	display_name: str
	default_value: Any
	# if the settings value doesn't differ from the default, should it be written to disk?
	is_necessary: bool # if not, the program won't complain when this setting isn't set
	settings_type: SettingsType
	write_if_default: bool = True
	tooltip: Optional[str] = None
	chooser_fn: Optional[Any] = None # only applies to file/folder settings types
	min_max_values: Optional[Tuple[int, int]] = None # only applies to spinbox

SETTINGS_ENTRIES = [
	SettingsEntry(
		python_name = "xml_path",
		json_name = "etterna-xml",
		display_name = "Etterna XML path",
		default_value = None,
		write_if_default = True,
		is_necessary = True,
		settings_type = SettingsType.File,
		chooser_fn = try_select_xml,
	),
	SettingsEntry(
		python_name = "replays_dir",
		json_name = "replays-dir",
		display_name = "ReplaysV2 directory path",
		default_value = None,
		write_if_default = True,
		is_necessary = True,
		settings_type = SettingsType.Folder,
		chooser_fn = try_choose_replays,
	),
	SettingsEntry(
		python_name = "songs_root",
		json_name = "songs-root",
		display_name = "Root songs directory",
		default_value = None,
		write_if_default = True,
		is_necessary = True,
		settings_type = SettingsType.File,
		chooser_fn = try_choose_songs_root,
	),
	SettingsEntry(
		python_name = "enable_all_plots",
		json_name = "enable-all-plots",
		display_name = "Enable old boring plots",
		default_value = False,
		write_if_default = True,
		is_necessary = False,
		settings_type = SettingsType.Checkbox,
	),
	SettingsEntry(
		python_name = "hide_invalidated",
		json_name = "hide-invalidated",
		display_name = "Hide invalidated scores",
		default_value = True,
		write_if_default = True,
		is_necessary = False,
		settings_type = SettingsType.Checkbox,
	),
	# only write color config value if they differ from the default. otherwise all users will
	# have the color config as of now hard-coded in their settings, and color config changes
	# in a future update won't be applied
	SettingsEntry(
		python_name = "bg_color",
		json_name = "bg-color",
		display_name = "Background color",
		default_value = "#222222",
		write_if_default = False,
		is_necessary = False,
		settings_type = SettingsType.Color,
	),
	SettingsEntry(
		python_name = "text_color",
		json_name = "text-color",
		display_name = "Text color",
		default_value = "#DDDDDD",
		write_if_default = False,
		is_necessary = False,
		settings_type = SettingsType.Color,
	),
	SettingsEntry(
		python_name = "border_color",
		json_name = "border-color",
		display_name = "Border color",
		default_value = "#777777",
		write_if_default = False,
		is_necessary = False,
		settings_type = SettingsType.Color,
	),
	SettingsEntry(
		python_name = "link_color",
		json_name = "link-color",
		display_name = "Link color",
		default_value = "#5193d4",
		write_if_default = False,
		is_necessary = False,
		settings_type = SettingsType.Color,
	),
	SettingsEntry(
		python_name = "legend_bg_color",
		json_name = "legend-bg-color",
		display_name = "Graph legend background color",
		default_value = "#2A2A2A",
		write_if_default = False,
		is_necessary = False,
		settings_type = SettingsType.Color,
	),
	SettingsEntry(
		python_name = "msgbox_num_scores_threshold",
		json_name = "msgbox-num-scores-threshold",
		display_name = "Min number of scores for the message box",
		default_value = 3,
		write_if_default = True,
		is_necessary = False,
		settings_type = SettingsType.Spinbox,
		min_max_values = (1, 99),
	),
]

# validate settings entries format
for entry in SETTINGS_ENTRIES:
	is_file_selector = entry.settings_type in (SettingsType.File, SettingsType.Folder)
	if is_file_selector and entry.chooser_fn is None:
		raise Exception(f"Setting {entry.python_name} has no chooser_fn!")
	elif not is_file_selector and entry.chooser_fn is not None:
		raise Exception(f"Setting {entry.python_name} has an unexpected chooser_fn!")

# When adding a new setting, keep care to update all placed marked with "# setting here"
class Settings:
	@staticmethod
	def load_from_json() -> Settings:
		settings = Settings()

		# Initialize defaults
		for entry in SETTINGS_ENTRIES:
			setattr(settings, entry.python_name, entry.default_value)
		
		# Load the values from the json
		if os.path.exists(SETTINGS_PATH):
			with open(SETTINGS_PATH) as f:
				for key, value in json.load(f).items(): # setting here
					# find the settings entry corresponding to this json key-value pair
					for entry in SETTINGS_ENTRIES:
						if entry.json_name == key:
							break
					else:
						print(f"unknown settings key-value pair: {key}, {value}")
						continue
					
					setattr(settings, entry.python_name, value)
		
		return settings
	
	def save_to_json(self) -> None:
		json_data = {}

		for entry in SETTINGS_ENTRIES:
			current_value = getattr(self, entry.python_name)
			if entry.write_if_default:
				json_data[entry.json_name] = current_value
			else:
				# check equality case-insensitively
				if current_value.casefold() != entry.default_value.casefold():
					json_data[entry.json_name] = current_value
				else:
					# this entry should only be written to disk if it differs from the default -
					# we don't differ from the default here, so we omit it from the json
					pass

		with open(SETTINGS_PATH, "w") as f:
			json.dump(json_data, f, indent="\t")
	
	def is_incomplete(self) -> bool:
		for entry in SETTINGS_ENTRIES:
			if entry.is_necessary and getattr(self, entry.python_name) is None:
				return True
		return False

class ColorPickerButton(QPushButton):
	def __init__(self, initial_color):
		super().__init__()
		self._qcolordialog = QColorDialog()
		
		self._initial_color = initial_color
		self.set_color(initial_color)
		self._qcolordialog.currentColorChanged.connect(self._update_self_color)
		self.pressed.connect(lambda: self._qcolordialog.open())
	
	def _update_self_color(self):
		self.setStyleSheet(f"background-color: {self._qcolordialog.currentColor().name()}")
	
	def get_qcolor(self) -> QColor:
		return self._qcolordialog.currentColor()
	
	def set_color(self, color) -> None:
		self._qcolordialog.setCurrentColor(QColor(color))
		self._update_self_color()
	
	# reset to initial color (note: initial color = the color that was set when entering the
	# settings, NOT the overall program default)
	def reset(self) -> None:
		self.set_color(self._initial_color)

class SettingsDialog(QDialog):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("Settings")

		# maps the SettingsEntry.python_name to the QWidget in the settings dialog
		self.input_widgets: Dict[str, QWidget] = {}
		
		vbox = QVBoxLayout(self)
		
		layout_widget = QWidget(self)
		vbox.addWidget(layout_widget)
		layout = QGridLayout(layout_widget)
		
		buttons = QDialogButtonBox()
		save_btn = buttons.addButton("Save", QDialogButtonBox.ButtonRole.AcceptRole)
		save_btn.pressed.connect(self.try_save)
		cancel_btn = buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
		cancel_btn.pressed.connect(self.reject)
		vbox.addWidget(buttons)
		
		restart_info = QLabel("<i>Restart for changes to take place</i>")
		restart_info.setAlignment(Qt.AlignCenter | Qt.AlignRight)
		vbox.addWidget(restart_info)

		row = 0

		for entry in SETTINGS_ENTRIES:
			current_value = getattr(app.app.prefs, entry.python_name)

			input_widget = None
			btn = None

			# setting here
			if entry.settings_type in (SettingsType.File, SettingsType.Folder):
				is_file = entry.settings_type == SettingsType.File

				theme_icon_name = "document-open" if is_file else "folder-open"
				standard_icon = QStyle.SP_FileIcon if is_file else QStyle.SP_DirIcon

				input_widget = QLineEdit(current_value)
				def chooser_handler():
					result = (entry.chooser_fn)()
					if result: self.input_widget.setText(result)
				
				btn = QPushButton()
				btn.setIcon(QIcon.fromTheme(theme_icon_name,
						QApplication.style().standardIcon(standard_icon))) # fallback icon
				btn.pressed.connect(chooser_handler)
			elif entry.settings_type == SettingsType.Color:
				color_picker_button = ColorPickerButton(current_value)
				color_picker_button.setToolTip("Press this button to select a color")

				def reset_color(color_picker_button=color_picker_button,
						default_value=entry.default_value):
					color_picker_button.set_color(default_value)

				reset_button = QPushButton()
				reset_button.setIcon(QIcon.fromTheme("view-refresh",
						QApplication.style().standardIcon(QStyle.SP_BrowserReload))) # fallback icon
				reset_button.pressed.connect(reset_color)
				reset_button.setToolTip("Reset color to default")
				
				input_widget = color_picker_button
				btn = reset_button
			elif entry.settings_type == SettingsType.Checkbox:
				input_widget = QCheckBox()
				input_widget.setChecked(current_value)
			elif entry.settings_type == SettingsType.Spinbox:
				input_widget = QSpinBox()
				input_widget.setMinimum(entry.min_max_values[0])
				input_widget.setMaximum(entry.min_max_values[1])
				input_widget.setValue(current_value)
			else:
				raise Exception(f"Unexpected settings type {entry.settings_type}")

			self.input_widgets[entry.python_name] = input_widget
			layout.addWidget(QLabel(entry.display_name), row, 0)
			if btn is None:
				# when there's no button, use the free space on column 2 to make the input widget
				# span across two columns
				layout.addWidget(input_widget, row, 1, 1, 2)
			else:
				layout.addWidget(input_widget, row, 1)
				layout.addWidget(btn, row, 2)
			
			row += 1
		
		self.setMinimumWidth(600)
	
	def try_save(self):
		# setting here
		missing_inputs = []
		for entry in SETTINGS_ENTRIES:
			if entry.is_necessary:
				if not entry.settings_type in (SettingsType.File, SettingsType.Folder):
					print("WARNING: uh oh, unimplemented")
					continue

				selected_path = self.input_widgets[entry.python_name].text()
				if not os.path.exists(selected_path): # includes blank input
					missing_inputs.append(entry.display_name)
		
		if len(missing_inputs) >= 1:
			QMessageBox.information(None, "Missing or invalid fields",
					"Please fill in valid values for: " + ", ".join(missing_inputs))
			return
		
		# setting here
		for entry in SETTINGS_ENTRIES:
			input_widget = self.input_widgets[entry.python_name]

			selected_value = None
			if isinstance(input_widget, QLineEdit):
				selected_value = input_widget.text()
			elif isinstance(input_widget, QCheckBox):
				selected_value = input_widget.isChecked()
			elif isinstance(input_widget, ColorPickerButton):
				selected_value = input_widget.get_qcolor().name()
			elif isinstance(input_widget, QSpinBox):
				selected_value = input_widget.value()
			else:
				print(f"WARNING: unexpected input widget type {type(input_widget)}")
				continue
			
			setattr(app.app.prefs, entry.python_name, selected_value)
		
		print("Saving prefs to json...")
		app.app.prefs.save_to_json()
		
		self.accept()