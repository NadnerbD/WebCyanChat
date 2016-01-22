#!/usr/bin/python
import sys
import os

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
if(len(sys.argv) >= 2 and serverClasses.has_key(sys.argv[1])):
	serverName = serverClasses[sys.argv[1]]
	serverModule = __import__(serverName)
	serverClass = serverModule.__getattribute__(serverName)
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
			raise Exception("invalid option")
	Server.start()
except Exception:
	print "usage: python %s (%s) [--pref_name=VALUE ...]" % (sys.argv[0], '|'.join(serverClasses.keys()))
