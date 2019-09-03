import pyqtgraph as pg
from lxml import etree
from datetime import datetime

import util
import data_generators as g

def parsedate(s): return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

def plot(frame, xml, mapper, color, alpha=0.4):
	axisItems = {"bottom": util.TimeAxisItem(orientation="bottom")}
	plot = frame.addPlot(axisItems=axisItems)
	data = score_map(xml, mapper)
	x, y = list(data.keys()), list(data.values())
	
	color = pg.mkColor(color)
	color.setAlphaF(alpha)
	item = pg.ScatterPlotItem(x, y, pen=None, brush=color)
	plot.addItem(item)

# Takes xml and score mapping function and maps every score of the xml
# via the score mapping function, plus a datetime. Returns a dict with
# timestamp-value pairs, where values are the mapping function results.
def score_map(xml, mapper_function):
	data = {}
	for score in xml.iter("Score"):
		datetime = parsedate(score.findtext("DateTime"))
		wife_score = (mapper_function)(score)
		data[int(datetime.timestamp())] = wife_score
	return data

class PlotFrame(pg.GraphicsLayoutWidget):
	def __init__(self, xml_path):
		super().__init__()
		
		if xml_path == None: return
		self.xml = etree.parse(xml_path).getroot()
	
	def draw(self):
		plot(self, self.xml, g.map_wifescore, "r")
		plot(self, self.xml, g.map_accuracy, "c")
	
