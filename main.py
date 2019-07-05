#import xml.etree.ElementTree
from lxml import etree
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.widgets import TextBox, Button
import numpy as np
import os
import glob
from enum import Enum

from mappers import *
#from etterna_helpers import parse_sm

PLOT_ROWS = 2
PLOT_COLS = 2
INPUT_HEIGHT = 0.05

class Category:
	def __init__(self, name, mapper, mapper_input="score"):
		self.name = name.lower()
		self.mapper = mapper
		self.mapper_input = mapper_input

def calculate_ax(pos):
	global PLOT_ROWS, PLOT_COLS
	
	left = 0.05
	right = 0.01
	bottom = 0.05
	top = 0.01
	
	main_height = 1-INPUT_HEIGHT
	
	row = PLOT_ROWS-1 - pos//PLOT_COLS
	col = pos%PLOT_COLS
	
	x = 1/PLOT_COLS * col + left
	y = main_height/PLOT_ROWS * row + INPUT_HEIGHT + bottom
	width = 1/PLOT_COLS - left - right
	height = main_height/PLOT_ROWS - bottom - top
	plot_ax = plt.axes([x, y, width, height])
	
	# Stub: add delete button
	
	return plot_ax#, btn_ax

category_cache = {}

def find_category(name):
	name = name.lower()
	for c in categories:
		if name == c.name: return c

# Uses cache
def retrieve_category_data(c):
	if c in category_cache: return category_cache[c]
	
	data = [(c.mapper)(score) for score in xml.iter("Score")]
	category_cache[c] = data
	return data

free_spaces = list(range(0, PLOT_ROWS*PLOT_COLS))
def add_plot(expression):
	[ycategory, xcategory] = expression.split(" over ")
	
	x = retrieve_category_data(find_category(xcategory))
	y = retrieve_category_data(find_category(ycategory))
	if len(x) != len(y): raise Exception("Non-matching x and y data")
	
	pos = free_spaces.pop(0)
	color = plt.cm.get_cmap("Dark2")(pos)
	ax = calculate_ax(pos)
	ax.scatter(x, y, color=color)


categories = [
	Category("overall", map_wifescore),
	Category("time", map_datetime),
	Category("manipulation", map_manip),
	Category("accuracy", map_accuracy),
]

xml = etree.parse("/home/kangalioo/.etterna/Save/LocalProfiles/00000000/Etterna.xml").getroot()
matplotlib.style.use("seaborn")
plt.tight_layout()

add_plot("overall over time")
add_plot("accuracy over manipulation")

tbox = TextBox(plt.axes([0, 0, 0.95, INPUT_HEIGHT]), "")
tbox.on_submit(lambda _: None)
btn = Button(plt.axes([0.95, 0, 0.05, INPUT_HEIGHT]), "Add")
def on_btn_click(ev):
	add_plot(tbox.text)
	tbox.set_val("")
btn.on_clicked(on_btn_click)


plt.show()
