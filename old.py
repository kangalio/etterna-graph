#import xml.etree.ElementTree
from lxml import etree
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.widgets import TextBox
from datetime import datetime, timedelta
import numpy as np
import os
import glob
from enum import Enum

from mappers import *
#from etterna_helpers import parse_sm

def parsedate(s): return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

def analyze_session(scores):
	session_end_threshold = timedelta(minutes=20)
	
	datetimes = [parsedate(s.find("DateTime").text) for s in scores]
	datetimes = sorted(datetimes)
	
	s_start = datetimes[0]
	sessions = {}
	for i in range(1, len(datetimes)):
		if datetimes[i] - datetimes[i-1] > session_end_threshold:
			s_length = datetimes[i-1] - s_start
			s_minutes = s_length.total_seconds() / 60
			sessions[s_start] = s_minutes
			
			s_start = datetimes[i]
	
	return sessions

class Category:
	def __init__(self, name, mapper, mapper_input="singular"):
		self.name = name
		self.mapper = mapper
		self.mapper_input = mapper_input
	
	def create_data_dict(self, sm):
		if self.mapper_input == "singular":
			data = {}
			for score in sm.iter("Score"):
				datetime = parsedate(score.find("DateTime").text)
				value = (self.mapper)(score)
				if value != None: data[datetime] = value
			return data
		elif self.mapper_input == "raw":
			return (self.mapper)(sm.iter("Score"))
	
	def plot(self, sm, ax=None, **kwargs):
		data = self.create_data_dict(sm)
		
		(plt if ax==None else ax)\
			.scatter(data.keys(), data.values(), **kwargs)
		
		if ax==None:
			plt.xlabel("Date and time")
			plt.ylabel(self.name)
			plt.show()
		else:
			ax.set_xlabel("Date and time")
			ax.set_ylabel(self.name)

categories = [
	Category("Wife score", map_wifescore),
	Category("Manipulation (% of notes in wrong order)", map_manip),
	Category("Accuracy (%)", map_accuracy),
	Category("Session length (min)", analyze_session, mapper_input="raw")
]
xml = etree.parse("/home/kangalioo/.etterna/Save/LocalProfiles/00000000/Etterna.xml").getroot()

matplotlib.style.use("seaborn")

axes = []
ax = None
for i in range(len(categories)):
	ax = plt.subplot(2, 2, i+1, sharex=ax)
	axes.append(ax)
	
	print(categories[i].name + "...")
	color = plt.cm.get_cmap("Dark2")(i)
	categories[i].plot(xml, ax=ax, color=color, alpha=0.4)

plt.show()


"""while True:
	print("Select one of the following data categories to be plotted:")
	for (i, c) in enumerate(categories):
		print(f"{i+1}) {c.name}")
	
	category = None
	while category == None:
		print()
		selection = input("Make your selection by typing the number: ")
		try:
			category = categories[int(selection)-1]
		except IndexError: print("Number out of range")
		except ValueError: print("That's not a number")
	
	print(f"Plotting \"{category.name}\"...")
	print()
	print()
	
	category.plot(sm)"""
