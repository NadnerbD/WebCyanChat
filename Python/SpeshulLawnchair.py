from Cursive_Server import Cursive_Server
from Term_Server import Term_Server

from threading import Thread
import os, sys, re

import stacktracer
stacktracer.trace_start("/app/HTML/trace.html")

if(os.path.dirname(sys.argv[0])):
	os.chdir(os.path.dirname(sys.argv[0]))

# instantiate some servers
t = Term_Server()
t.readPrefs("etc/CCServer.conf")
c = Cursive_Server()
c.readPrefs("etc/CCServer.conf")

# take the CC server's HTTP server and link it to the Term server
t.server = c.HTTPServ
t.sessionQueue = t.server.registerProtocol("term", "/term-socket")
t.server.registerAuthorizer(re.compile("^/(term-socket|console\.html).*$"), t.authorize)

# use the supplied port
t.prefs["http_port"] = int(os.environ["PORT"])
c.prefs["http_port"] = int(os.environ["PORT"])

# to start both servers, we need threads
ct = Thread(None, c.start, "CCThread", ())
ct.start()
while True:
	# the term thread will die when the shell exits
	# so we'll restart it indefinitely
	tt = Thread(None, t.start, "TermThread", ())
	tt.setDaemon(1)
	tt.start()
	tt.join()

