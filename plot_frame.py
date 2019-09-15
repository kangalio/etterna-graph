import pyqtgraph as pg
from datetime import datetime
import numpy as np

import util
from util import parsedate
import data_generators as g

# This is a big function thata handles almost all graphics library
# interaction. Parameters:
# 
# frame: GraphicsLayoutWidget to insert the plot into
# xml: Etterna.xml root node
# mapper: function to generate data
# color, alpha: color/alpha of the points
# mappertype: "xml" if mapper is called with `xml` as parameter, "score"
#   if mapper is called with a single score object
# mapper_args: additional call parameters for the mapper
# log: whether to use log scale for x axis. Because of pyqtgraph
#   restrictions it only works for PlotDataItems (line charts)
# time_xaxis: whether the x axis is a datetime axis
# accuracy_yacis: whether the yaxis is an accuracy axis
# legend: color names
# click_callback: callback to call on scatter point click
# type_: chart type: "scatter", "bar", "bubble" or "stacked bar"
# colspan: how many columns the plot spans
# rowspan: how many rows the plot spans
# ids_included

class Tile:
	def __init__(self, frame, rowspan=1, colspan=1, flags="", title=None):
		global column
		
		self.flags = flags
		
		axisItems = {}
		if "time_xaxis" in flags:
			axisItems["bottom"] = util.TimeAxisItem(orientation="bottom")
		if "accuracy_yaxis" in flags:
			axisItems["left"] = util.DIYLogAxisItem(accuracy=True, decimal_places=3, orientation="left")
		elif "manip_yaxis" in flags:
			axisItems["left"] = util.DIYLogAxisItem(accuracy=False, decimal_places=1, orientation="left")
		
		plot = frame.addPlot(axisItems=axisItems, colspan=colspan, rowspan=rowspan)
		frame.maybe_advance_row()
		self.plot = plot
		plot.setTitle(title)
		if "log" in flags: plot.setLogMode(x=False, y=True)
	
	def draw(self, xml, mapper, color, alpha=0.4, mappertype="xml", mapper_args=[], legend=None, click_callback=None, type_="scatter", width=0.8):
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
			y = list(zip(*y))
			num_cols = len(y[0])
			bottom = [0] * num_cols
			for (row_i, row) in enumerate(y):
				#item = pg.BarGraphItem(x=x, y0=bottom, height=row, width=1, pen=(0,0,0,255), brush=color[row_i])
				item = pg.BarGraphItem(x=x, y0=bottom, height=row, width=0.82, pen=color[row_i], brush=color[row_i])
				bottom = [a+b for (a,b) in zip(bottom, row)] # We need out-of-place here
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
