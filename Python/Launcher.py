#!/usr/bin/python3
import sys
import os

profiling = False
if("--profile" in sys.argv):
	import yappi
	yappi.start()
	sys.argv.remove("--profile")
	profiling = True
	

if(os.path.dirname(sys.argv[0])):
	os.chdir(os.path.dirname(sys.argv[0]))

serverClasses = { \
	"cc": "CC_Server", \
	"tia": "TIA_Server", \
	"relay": "CC_Relay", \
	"skype": "CC_Skype_Relay", \
	"term": "Term_Server", \
	"cursive": "Cursive_Server", \
}
serverClass = None

def usage():
	print("usage: python %s (%s) [--pref_name=VALUE ...]" % (sys.argv[0], '|'.join(serverClasses.keys())))
	exit()

class InvalidOptionException(Exception):
	pass

if(len(sys.argv) >= 2 and sys.argv[1] in serverClasses):
	serverName = serverClasses[sys.argv[1]]
	serverModule = __import__(serverName)
	serverClass = serverModule.__getattribute__(serverName)
else:
	usage()
try:
	Server = serverClass()
	Server.readPrefs("etc/CCServer.conf")
	# prefs can be overridden with command line options
	for arg in sys.argv[2:]:
		(name, value) = arg.split("=", 1)
		if(name.startswith("--") and value):
			if(value.isdigit()):
				value = int(value)
			Server.prefs[name[2:]] = value
		else:
			raise InvalidOptionException
	Server.start()
except InvalidOptionException:
	usage()

if(profiling):
	yappi.get_func_stats().print_all()
	yappi.get_thread_stats().print_all()
