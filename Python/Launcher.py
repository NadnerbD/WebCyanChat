#!/usr/bin/python
import sys
import os

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
if(len(sys.argv) == 2 and serverClasses.has_key(sys.argv[1])):
	serverName = serverClasses[sys.argv[1]]
	serverModule = __import__(serverName)
	serverClass = serverModule.__getattribute__(serverName)
if(serverClass):
	Server = serverClass()
	Server.readPrefs("etc/CCServer.conf")
	Server.prefs["http_port"] = int(os.environ["PORT"])
	Server.start()
else:
	print "usage: python %s [%s]" % (sys.argv[0], '|'.join(serverClasses.keys()))
