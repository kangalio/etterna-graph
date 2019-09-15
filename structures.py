import multiprocessing

def parse_replay(path):
	try: replays_file = open(path)
	except: return None
	
	replay = []
	for line in replays_file.readlines():
		if line.startswith("H"): continue
		replay.append(tuple(float(x) for x in line.split(" ")))
	
	return replay

class Replays:
	def __init__(self, xml, replays_path):
		pool = multiprocessing.Pool(multiprocessing.cpu_count())
		
		keys = [score.get("Key") for score in xml.iter("Score")]
		paths = (replays_path+"/"+key for key in keys)
		replays = pool.map(parse_replay, paths, chunksize=20)
		replays = dict(zip(keys, replays))
		self.replays = replays
	
	# Returns replay as list of tuples where each tuple corresponds to
	# one line of the replay file
	def get(self, scorekey):
		return self.replays[scorekey]
