import threading
import sys

# The purpose of this module is to provide simple logging capabilities
# and to redirect stderr to a file in order to record server exceptions
# while it is running nohup

# Logging level reference
# 0: Chat and join/leave messages only
# 1: PMs, name attempts, ignores
# 2: CC debugging info (userlist sends, size, connections, etc)
# 3: HTTP Requests, and all debugging info
# 4: EVERYTHING
logging = 3
logLock = threading.Lock()
def log(obj, msg, level=0):
	if(logging >= level):
		logLock.acquire()
		print "%s: %s" % (obj.__class__.__name__, msg)
		logLock.release()

class errorLogger:
	def __init__(self):
		self.errorLog = None
	
	def write(self, string):
		if(type(self.errorLog) != file):
			self.errorLog = file("CCErrorLog.log", 'w')
		self.errorLog.write(string)
		self.errorLog.flush()
errorOut = errorLogger()
sys.stderr = errorOut

