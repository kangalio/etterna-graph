from typing import *

import math
from datetime import datetime

import pyqtgraph as pg

import util
import app


"""
This file handles all graphics library interaction through the classes
PlotFrame, Plot and TextBox (and the internal utility classes
TimeAxisItem and DIYLogAxisItem)
"""

class TimeAxisItem(pg.AxisItem):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.setLabel(units=None)
		self.enableAutoSIPrefix(False)

	def tickStrings(self, values, scale, spacing):
		# Cap timestamp to 32 bit to prevent crash on Windows from
		# out-of-bounds dates
		capmin = 0
		capmax = (2 ** 31) - 1
		
		strings = []
		for value in values:
			value = min(capmax, max(capmin, value))
			strings.append(datetime.fromtimestamp(value).strftime("%Y-%m-%d"))
		return strings

class DIYLogAxisItem(pg.AxisItem):
	def __init__(self, accuracy, decimal_places, postfix="", *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.setLabel(units=None)
		self.enableAutoSIPrefix(False)
		
		self.accuracy = accuracy
		self.decimal_places = decimal_places
		self.postfix = postfix

	def tickStrings(self, values, scale, spacing):
		result = []
		for value in values:
			if self.accuracy:
				value = 100 - 10 ** -value
			else:
				value = 10 ** value
			value = round(value, self.decimal_places)
			result.append(str(value) + self.postfix)
		return result

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
def draw(frame, data,
		colspan=1, rowspan=1, flags="", title=None,
		color="white", alpha=0.4, legend=None,
		click_callback=None, type_="scatter", width=0.8):
	
	axisItems = {}
	if "time_xaxis" in flags:
		axisItems["bottom"] = TimeAxisItem(orientation="bottom")
	if "accuracy_yaxis" in flags:
		axisItems["left"] = DIYLogAxisItem(accuracy=True, decimal_places=3, postfix="%",
				orientation="left")
	elif "manip_yaxis" in flags:
		axisItems["left"] = DIYLogAxisItem(accuracy=False, decimal_places=1, postfix="%",
				orientation="left")
	elif "ma_yaxis" in flags:
		axisItems["left"] = DIYLogAxisItem(accuracy=False, decimal_places=1,
				orientation="left")
	
	plot = frame.addPlot(axisItems=axisItems, colspan=colspan, rowspan=rowspan)
	plot.setTitle(title)
	if "log" in flags: plot.setLogMode(x=False, y=True)
	
	def click_handler(_, points):
		if len(points) > 1:
			app.app.set_infobar(f"{len(points)} points selected at once!")
		else:
			try:
				(click_callback)(points[0].data())
			except Exception:
				util.logger.exception("Click handler")
				app.app.set_infobar("[Error while generating info text]")
	
	plot.clear()
	
	if isinstance(data, str):
		item = pg.TextItem(data, anchor=(0.5, 0.5))
		plot.addItem(item)
		return
	
	ids = None
	
	# We may have ids given which we need to separate
	if click_callback is not None: (data, ids) = data
	if type_ == "bubble": (x, y, sizes) = data
	else: (x, y) = data
	
	if "time_xaxis" in flags:
		x = [value.timestamp() for value in x]
	
	step_mode = ("step" in flags)
	if step_mode:
		x = [*x, x[-1]] # Duplicate last element to satisfy pyqtgraph with stepMode
		# Out-of-place to avoid modifying the passed-in list
	
	if legend is not None: plot.addLegend()
	
	if type_ == "stacked bar":
		num_cols = len(y)
		y = list(zip(*y))
		bottom = [0] * num_cols
		for (row_i, row) in enumerate(y):
			#item = pg.BarGraphItem(x=x, y0=bottom, height=row, width=1, pen=(0,0,0,255), brush=color[row_i])
			item = pg.BarGraphItem(x=x, y0=bottom, height=row, width=0.82, pen=color[row_i], brush=color[row_i])
			bottom = [a + b for (a, b) in zip(bottom, row)] # We need out-of-place here
			if legend is not None:
				plot.legend.addItem(item, legend[row_i])
			plot.addItem(item)
	elif type_ == "stacked line":
		num_cols = len(y)
		y = list(zip(*y))
		# Iterate in reverse so that overall comes last and draws
		# above the rest
		for (row_i, row) in reversed(list(enumerate(y))):
			# ~ item = pg.PlotCurveItem(x=x, y=list(row), pen=color[row_i], brush=color[row_i], stepMode=step_mode)
			width = 3 if row_i == 0 else 1
			pen = pg.mkPen(color[row_i], width=width)
			item = pg.PlotCurveItem(x=x, y=list(row), pen=pen, stepMode=step_mode)
			if legend is not None:
				plot.legend.addItem(item, legend[row_i])
			plot.addItem(item)
	else:
		color = pg.mkColor(color)
		color.setAlphaF(alpha)
		if type_ == "scatter":
			item = pg.ScatterPlotItem(x, y, pen=None, size=8, brush=color, data=ids)
		elif type_ == "bar":
			item = pg.BarGraphItem(x=x, height=y, width=width, pen=(200, 200, 200), brush=color)
		elif type_ == "bubble":
			item = pg.ScatterPlotItem(x, y, pen=None, size=sizes, brush=color, data=ids)
		elif type_ == "line":
			width = 3 if "thick_line" in flags else 1
			item = pg.PlotDataItem(x, y, pen=pg.mkPen(color, width=width), stepMode=step_mode)
		
		if click_callback is not None:
			item.sigClicked.connect(click_handler)
		plot.addItem(item)
	
	# Add horizontal score threshold lines
	if "accuracy_yaxis" in flags:
		print("adding lines")
		plot.addLine(y=-(math.log(100 - 60.00) / math.log(10)), pen="#c97bff")
		plot.addLine(y=-(math.log(100 - 70.00) / math.log(10)), pen="#5b78bb")
		plot.addLine(y=-(math.log(100 - 80.00) / math.log(10)), pen="#da5757")
		plot.addLine(y=-(math.log(100 - 93.00) / math.log(10)), pen="#66cc66")
		plot.addLine(y=-(math.log(100 - 99.75) / math.log(10)), pen="#eebb00")
		plot.addLine(y=-(math.log(100 - 99.97) / math.log(10)), pen="#66ccff")
		print("done adding lines")
	
	plot.autoBtnClicked()
	plot.showGrid(x=True, y=True, alpha=0.15)
	return plot
