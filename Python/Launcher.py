#!/usr/bin/python

from CC_Server import CC_Server
from CC_Relay import CC_Relay
from TIA_Server import TIA_Server
from CC_Skype_Relay import CC_Skype_Relay
from Term_Server import Term_Server

import sys

serverClasses = { \
	"cc": CC_Server, \
	"tia": TIA_Server, \
	"relay": CC_Relay, \
	"skype": CC_Skype_Relay, \
	"term": Term_Server, \
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
