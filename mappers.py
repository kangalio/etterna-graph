from datetime import datetime, timedelta

def map_wifescore(score):
	try:
		overall = float(next(score.iter("Overall")).text)
		percentage = float(next(score.iter("WifeScore")).text)
		score = overall * percentage / 0.93
		return score
	except: return None

def map_manip(score):
	replaydir = f"/home/kangalioo/.etterna/Save/ReplaysV2"
	try: replayfile = open(replaydir+"/"+score.attrib['Key'])
	except: return None

	times = []
	for line in replayfile.readlines():
		time_str = line.split(" ")[0]
		try: times.append(float(time_str))
		except ValueError: pass

	manipulations = 0
	i = 1
	for t in times[1:]:
		if times[i] < times[i-1]:
			manipulations += 1
		i += 1

	percent_manipulated = manipulations/len(times)*100
	return percent_manipulated

def map_accuracy(score):
	return float(score.find("WifeScore").text)*100

def map_datetime(score):
	string = score.find("DateTime").text
	return datetime.strptime(string, "%Y-%m-%d %H:%M:%S")

"""sessions = None # Functions as a cache
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
	
	return sessions"""
