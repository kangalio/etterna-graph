import pyqtgraph as pg
from datetime import datetime

import util
import data_generators as g

"""
This file handles all graphics library interaction through the classes
PlotFrame, Plot and TextBox (and the internal utility classes
TimeAxisItem and DIYLogAxisItem)
"""

class Plot:
	class TimeAxisItem(pg.AxisItem):
		def __init__(self, *args, **kwargs):
			super().__init__(*args, **kwargs)
			self.setLabel(units=None)
			self.enableAutoSIPrefix(False)

		def tickStrings(self, values, scale, spacing):
			return [datetime.fromtimestamp(value).strftime("%Y-%m-%d") for value in values]

	class DIYLogAxisItem(pg.AxisItem):
		def __init__(self, accuracy, decimal_places, *args, **kwargs):
			super().__init__(*args, **kwargs)
			self.setLabel(units=None)
			self.enableAutoSIPrefix(False)
			
			self.accuracy = accuracy
			self.decimal_places = decimal_places

		def tickStrings(self, values, scale, spacing):
			result = []
			for value in values:
				if self.accuracy:
					value = 100 - 10 ** -value
				else:
					value = 10 ** value
				value = round(value, self.decimal_places)
				result.append(str(value) + "%")
			return result
	
	def __init__(self, frame, rowspan=1, colspan=1, flags="", title=None):
		global column
		
		self.flags = flags
		self.title = title
		
		axisItems = {}
		if "time_xaxis" in flags:
			axisItems["bottom"] = self.TimeAxisItem(orientation="bottom")
		if "accuracy_yaxis" in flags:
			axisItems["left"] = self.DIYLogAxisItem(accuracy=True, decimal_places=3, orientation="left")
		elif "manip_yaxis" in flags:
			axisItems["left"] = self.DIYLogAxisItem(accuracy=False, decimal_places=1, orientation="left")
		
		plot = frame.addPlot(axisItems=axisItems, colspan=colspan, rowspan=rowspan)
		for _ in range(colspan): frame.maybe_advance_row()
		self.plot = plot
		plot.setTitle(title)
		if "log" in flags: plot.setLogMode(x=False, y=True)
	
	# mapper: function that turns xml into data points
	# color: chart color (duh)
	# alpha: transparency of scatter points
	# mapper_args: extra parameters passed to `mapper`
	# legend: list of strings as the legend, for the stacked bar chart.
	# click_callback: callback for when a scatter point is clicked. The
	#  callback is called with the point data as parameter
	# type_: either "scatter", "bubble", "bar", "stacked bar" or
	#  "stacked line"
	# width: (only for bar charts) width of the bars
	def draw(self, xml, mapper, color, alpha=0.4, mapper_args=[], legend=None, click_callback=None, type_="scatter", width=0.8):
		def click_handler(self, callback, _, points):
			if len(points) > 1:
				text = f"{len(points)} points selected at once!"
			else:
				text = (callback)(points[0].data())
			self.frame.infobar.setText(text)
		
		self.plot.clear()
		
		ids = None
		
		data = (mapper)(xml, *mapper_args)
		# We may have ids given which we need to separate
		if click_callback != None: (data, ids) = data
		if type_ == "bubble": (x, y, sizes) = data
		else: (x, y) = data
		
		if "time_xaxis" in self.flags:
			x = [value.timestamp() for value in x]
		
		if legend != None: self.plot.addLegend()
		
		if type_ == "stacked bar":
			num_cols = len(y)
			y = list(zip(*y))
			bottom = [0] * num_cols
			for (row_i, row) in enumerate(y):
				#item = pg.BarGraphItem(x=x, y0=bottom, height=row, width=1, pen=(0,0,0,255), brush=color[row_i])
				item = pg.BarGraphItem(x=x, y0=bottom, height=row, width=0.82, pen=color[row_i], brush=color[row_i])
				bottom = [a+b for (a,b) in zip(bottom, row)] # We need out-of-place here
				if legend != None: self.plot.legend.addItem(item, legend[row_i])
				self.plot.addItem(item)
		elif type_ == "stacked line":
			num_cols = len(y)
			y = list(zip(*y))
			for (row_i, row) in enumerate(y):
				item = pg.PlotCurveItem(x=x, y=list(row), pen=color[row_i], brush=color[row_i])
				if legend != None: self.plot.legend.addItem(item, legend[row_i])
				self.plot.addItem(item)
		else:
			color = pg.mkColor(color)
			color.setAlphaF(alpha)
			if type_ == "scatter":
				item = pg.ScatterPlotItem(x, y, pen=None, size=8, brush=color, data=ids)
			elif type_ == "bar":
				item = pg.BarGraphItem(x=x, height=y, width=width, pen=(200,200,200), brush=color)
			elif type_ == "bubble":
				item = pg.ScatterPlotItem(x, y, pen=None, size=sizes, brush=color, data=ids)
			
			if click_callback != None:
				lowlevel_callback = lambda *args: click_handler(click_callback, *args)
				item.sigClicked.connect(lowlevel_callback)
			self.plot.addItem(item)

class TextBox:
	def __init__(self, frame):
		self.label = frame.addLabel(justify="left")
		frame.maybe_advance_row()
	def draw(self, text): self.label.setText(text)

class PlotFrame(pg.GraphicsLayoutWidget):
	def __init__(self, infobar):
		super().__init__(border=(100,100,100))
		
		self.infobar = infobar
		self.column_counter = 0
	
	def maybe_advance_row(self):
		self.column_counter += 1
		if self.column_counter == 2:
			self.column_counter = 0
			self.nextRow()
