#!/usr/bin/python

from CC_Server import CC_Server
from CC_Relay import CC_Relay
from TIA_Server import TIA_Server

import sys

serverClasses = { \
	"cc": CC_Server, \
	"tia": TIA_Server, \
	"relay": CC_Relay, \
}
serverClass = None
for arg in sys.argv:
	if(serverClasses.has_key(arg)):
		serverClass = serverClasses[arg]
if(serverClass):
	Server = serverClass()
	Server.readPrefs("etc/CCServer.conf")
	Server.start()
else:
	print "usage: python %s [%s]" % (sys.argv[0], '|'.join(serverClasses.keys()))
