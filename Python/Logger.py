import threading
import sys, os

try:
	import ctypes
	handle = ctypes.windll.kernel32.GetStdHandle(-11) # STD_OUTPUT_HANDLE
except:
	handle = False

def getAttrs(handle):
	import struct
	buf = ctypes.create_string_buffer(22)
	assert ctypes.windll.kernel32.GetConsoleScreenBufferInfo(handle, buf)
	return struct.unpack("hhhhHhhhhhh", buf.raw)[4]

def setAttrs(handle, attrs):
	ctypes.windll.kernel32.SetConsoleTextAttribute(handle, attrs)

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
	def __init__(self, stderr):
		self.errorLog = None
		self.stderr = stderr
	
	def write(self, string):
		if(type(self.errorLog) != file):
			self.errorLog = file("CCErrorLog.log", 'w')
		self.errorLog.write(string)
		self.errorLog.flush()
		# we should also pass the error through to the console
		# writes errors in red on Windows Console and ANSI terminal
		logLock.acquire()
		if(os.isatty(self.stderr.fileno())):
			if(handle):
				reset = getAttrs(handle)
				setAttrs(handle, 0x000c) # 4 (red) | 8 (intense)
				self.stderr.write(string)
				setAttrs(handle, reset)
			else:
				self.stderr.write("\x1b[31;1m" + string + "\x1b[0m") # 31 (red); 1 (intense)
		else:
			self.stderr.write(string)
		logLock.release()
sys.stderr = errorLogger(sys.stderr)

