import os

class Replays:
	def __init__(self, xml, replays_path):
		#pool = multiprocessing.Pool(multiprocessing.cpu_count())
		def open_file(key):
			path = replays_path+"/"+key
			return open(path).readlines() if os.path.exists(path) else None
		
		keys = [score.get("Key") for score in xml.iter("Score")]
		replays = {key: open_file(key) for key in keys}
		self.replays = replays
	
	# Returns iterator of rows (as strings)
	def get(self, scorekey):
		return self.replays[scorekey]
