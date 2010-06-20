from cStringIO import *
import socket
import threading
import random
import struct
import time
import sys

try:
	import hashlib
except:
	import md5 as hashlib

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

def readTo(stream, delim, ignore):
	matches = 0
	output = StringIO()
	if(hasattr(stream, 'recv')):
		read = stream.recv
	else:
		read = stream.read
	while(matches < len(delim)):
		char = read(1)
		if(not char):
			return None
		elif(char == delim[matches]):
			matches += 1
		elif(not char in ignore):
			matches = 0
		output.write(char)
	return output.getvalue()

def parseToDict(string, eq, delim):
	output = dict()
	items = string.split(delim)
	for item in items:
		keyVal = item.split(eq, 1)
		if(len(keyVal) == 2):
			output[keyVal[0]] = keyVal[1]
	return output

class HTTP_Server:
	statusCodes = { \
		100: "Continue", \
		101: "Web Socket Protocol Handshake", \
		200: "OK", \
		201: "Created", \
		301: "Moved Permanently", \
		400: "Bad Request", \
		403: "Forbidden", \
		404: "Not Found", \
		501: "Not Implemented", \
	}
	defaultResponseData = { \
		403: """<html><head><title>403 Error</title></head>
			<body><h3>403 Forbidden</h3><br />
			You shouldn't be here</body></html>""", \
		404: """<html><head><title>404 Error</title></head>
			<body><h3>404 Not Found</h3><br />
			The requested client file is missing. 
			This is probably because it is being updated, 
			please wait a moment and try again.</body></html>""", \
		501: """<html><head><title>501 Error</title></head><body>
			<h3>501 Not Implemented</h3><br />I'm sorry, I'm only 
			a very simple server, and I can't fulfill that request.
			</body></html>""", \
	}
	mimeTypes = { \
		"html": "text/html", \
		"ico": "image/x-icon", \
		"js": "text/javascript", \
		"css": "text/css", \
		"jpg": "image/jpeg", \
		"jpeg": "image/jpeg", \
		"png": "image/png", \
		"gif": "image/gif", \
	}
	class sessionList:
		def __init__(self):
			self.accessLock = threading.Lock()
			self.sessions = list()
		
		def findBySID(self, sid):
			for session in self.sessions:
				if(session.sid == int(sid)):
					return session
			return None
		
		def newSession(self, sock, addr):
			self.accessLock.acquire()
			newSID = addr[1]
			newSession = HTTP_Server.HTTP_Session(newSID)
			self.sessions.append(newSession)
			pingThread = threading.Thread(None, self.pingLoop, "pingLoop", (newSession,))
			pingThread.setDaemon(1)
			pingThread.start()
			self.accessLock.release()
			log(self, "new http session: %s" % newSID, 3)
			return newSession
		
		def pingLoop(self, session):
			while 1:
				time.sleep(31)
				session.sendLock.acquire()
				lagTime = time.time() - session.lastResponseTime
				log(self, "pingloop running, %ss since last activity" % lagTime, 3)
				if(lagTime > 60):
					self.sessions.remove(session)
					session.timedOut = 1
					log(self, "removed timed out session: %s" % session.sid, 3)
					session.waitLock.set()
					session.sendLock.release()
					return
				elif(lagTime > 30):
					if(session.sendSock):
						try:
							HTTP_Server.writeHTTP(session.sendSock, 200, {}, "%s\r\n%s" % (session.sid, "PING"))
						except:
							log(self, "error pinging session: %s" % session.sid, 3)
						session.sendSock = None
					log(self, "pinged session: %s" % session.sid, 3)
				else:
					log(self, "not pinging", 3)
				session.sendLock.release()
		
	class HTTP_Session:
		def __init__(self, sid):
			self.sid = sid
			self.recvLock = threading.Lock()
			self.sendLock = threading.Lock()
			self.waitLock = threading.Event()
			self.sendBuffer = StringIO()
			self.recvBuffer = StringIO()
			self.sendSock = None
			self.lastResponseTime = time.time()
			self.timedOut = 0
		
		def flush(self):
			self.sendBuffer.seek(0)
			try:
				HTTP_Server.writeHTTP(self.sendSock, 200, {}, "%s\r\n%s" % (self.sid, self.sendBuffer.read()))
			except:
				log(self, "error flushing http send: %s" % self.sid)
			self.sendBuffer = StringIO()
			self.sendSock = None
			log(self, "sent data to: %s" % self.sid, 3)
		
		def send(self, data):
			self.sendLock.acquire()
			self.sendBuffer.write(data)
			if(self.sendSock):
				self.flush()
			else:
				log(self, "buffered send to: %s" % self.sid, 3)
			self.sendLock.release()
		
		def recv(self, count):
			while 1:
				log(self, "attempted recv from: %s" % self.sid, 4)
				self.recvLock.acquire()
				if(self.timedOut):
					self.recvLock.release()
					log(self, "timed out, return null: %s" % self.sid, 3)
					return ''
				self.recvBuffer.seek(0)
				output = self.recvBuffer.read(count)
				if(output):
					currentBuffer = self.recvBuffer.read()
					self.recvBuffer = StringIO()
					self.recvBuffer.write(currentBuffer)
					log(self, "sucessful recv from buffer %s: %s" % (self.sid, repr(output)), 4)
					self.recvLock.release()
					return output
				else:
					log(self, "no data, holding: %s" % self.sid, 4)
					self.recvLock.release()
					self.waitLock.wait()
					self.waitLock.clear()
		
		def close(self):
			pass
		
		def queueRecvData(self, data):
			self.recvLock.acquire()
			self.recvBuffer.write(data)
			log(self, "received data from %s" % self.sid, 3)
			#log(self, "buffered data: %s" % repr(data), 4)
			self.recvLock.release()
			self.waitLock.set()
		
		def setSendSock(self, sock):
			self.sendLock.acquire()
			self.sendSock = sock
			log(self, "got send sock for %s" % self.sid, 3)
			if(self.sendBuffer.tell()):
				self.flush()
			self.lastResponseTime = time.time()
			self.sendLock.release()
	
	class WebSocket:
		def __init__(self, sock):
			self.sock = sock
		
		def send(self, data):
			self.sock.send("\x00%s\xFF" % data)
		
		def recv(self, count):
			data = ''
			while(len(data) < count):
				chunk = self.sock.recv(count)
				if(not chunk):
					return ''
				data += chunk
				data = data.replace('\x00', '')
				data = data.replace('\xFF', '')
			log(self, "recieved data from WebSocket: %r" % data, 4)
			return data
		
		def close(self):
			self.sock.close()
	
	class acceptQueue:
		def __init__(self):
			self.accessLock = threading.Lock()
			self.waitLock = threading.Event()
			self.queue = list()
			
		def insert(self, session):
			self.accessLock.acquire()
			self.queue.insert(0, session)
			self.accessLock.release()
			self.waitLock.set()
		
		def acceptHTTPSession(self): #Called by external application to get incoming HTTP sessions
			# funky interlocking locks act to cause function to block until there is a session in the queue
			while 1:
				self.accessLock.acquire()
				if(len(self.queue)):
					sock = self.queue.pop()
					self.accessLock.release()
					return sock
				else:
					self.accessLock.release()
					self.waitLock.wait()
					self.waitLock.clear()
	
	def __init__(self):
		self.sessionList = self.sessionList()
		self.sessionAcceptQueue = self.acceptQueue()
		self.redirects = dict()
	
	def readHTTP(self, sock):
		data = readTo(sock, "\r\n\r\n", ['\t', ' '])
		if(not data):
			raise IOError
		(method, resource, protocol) = data.split(' ', 2)
		(protocol, data) = protocol.split("\r\n", 1)
		getOptions = dict()
		if('?' in resource):
			(resource, getOptions) = resource.split("?", 1)
			getOptions = parseToDict(getOptions, '=', '&')
		headers = parseToDict(data, ": ", "\r\n")
		body = str()
		if(headers.has_key("Expect") and headers["Expect"] == "100-continue"):
			sock.send("HTTP/1.1 100 Continue\r\n\r\n")
		if(headers.has_key("Content-Length")):
			while(len(body) < int(headers["Content-Length"])):
				body += sock.recv(int(headers["Content-Length"]) - len(body))
		if(headers.has_key("Content-Type") and headers["Content-Type"].startswith("multipart/form-data")):
			formHeaders = parseToDict(headers["Content-Type"], '=', "; ")
			log(self, "multipart/form-data boundary: %s" % formHeaders["boundary"], 3)
			if(body):
				log(self, "Nice client gave us a Content-Length: %s" % headers["Content-Length"], 3)
			else:# didn't send us a goddamn Content-Length
				body = readTo(sock, "--%s--" % formHeaders["boundary"], [])
				log(self, "No Content-Length, read multipart from sock using boundary, length: %d" % len(formData), 3)
			body = body.split("--%s" % formHeaders["boundary"])[1:-1]
			output = list()
			for data in body:
				(dataHeaders, data) = data.split("\r\n\r\n", 1)
				dataHeaders = parseToDict(dataHeaders, ": ", "\r\n")
				if(dataHeaders.has_key("Content-Disposition")):
					dataHeaders["Content-Disposition"] = parseToDict(dataHeaders["Content-Disposition"], '=', "; ")
				output.append({"headers": dataHeaders, "data": data})
			body = output
		return (method, resource, protocol, headers, body, getOptions)
		
	def writeHTTP(sock, code, headers={}, body=None, orderedHeaders=[]):
		if(not body and HTTP_Server.defaultResponseData.has_key(code)):
			body = HTTP_Server.defaultResponseData[code]
			headers["Content-Type"] = "text/html"
		if(body and not headers.has_key("Content-Type")):
			headers["Content-Type"] = "text/plain"
		if(body):
			headers["Content-Length"] = len(body)
		sock.send("HTTP/1.1 %d %s\r\n" % (code, HTTP_Server.statusCodes[code]))
		for header in orderedHeaders:
			sock.send("%s: %s\r\n" % header)
		for key in headers:
			sock.send("%s: %s\r\n" % (key, headers[key]))
		if(body):
			sock.send("\r\n%s" % body)
	writeHTTP = staticmethod(writeHTTP)

	def handleReq(self, sock, addr, method, resource, protocol, headers, body, getOptions):
		#lazy parsing of escape sequences :P
		resource = resource.replace("%20", ' ')
		if(self.redirects.has_key(resource)):
			self.writeHTTP(sock, 301, {"Location": self.redirects[resource]}, "301 Redirect")
			log(self, "redirected %s from %s to %s" % (addr, resource, self.redirects[resource]), 3)
			return
		#resExt = resource.rsplit('.', 1)
		resExt = resource.split('.')
		if(len(resExt) > 1):
			extension = resExt[-1].lower()
			if(self.mimeTypes.has_key(extension)):
				mimeType = self.mimeTypes[extension]
			else:
				log(self, "denied request for %s" % resource, 3)
				self.writeHTTP(sock, 403)
				return
		else:
			mimeType = "application/octet-stream"
		if(method == "GET" and resource == "/web-socket"):
			if(headers.has_key("WebSocket-Protocol")): # protocol draft 75
				responseHeaders = [ \
					("Upgrade", "WebSocket"), \
					("Connection", "Upgrade"), \
					("WebSocket-Origin", headers["Origin"]), \
					("WebSocket-Location", "ws://%s/web-socket" % headers["Host"]), \
					("WebSocket-Protocol", headers["WebSocket-Protocol"]), \
				]
				log(self, "got WebSocket from (%s, %s)" % addr, 3)
				self.writeHTTP(sock, 101, {}, None, responseHeaders)
				sock.send("\r\n")
				self.sessionAcceptQueue.insert((self.WebSocket(sock), addr))
				# now get out of the socket loop and let the cc server take over
				raise self.WebSocket(None)
			elif(headers.has_key("Sec-WebSocket-Protocol")): # protocol draft 76
				responseHeaders = [ \
					("Upgrade", "WebSocket"), \
					("Connection", "Upgrade"), \
					("Sec-WebSocket-Origin", headers["Origin"]), \
					("Sec-WebSocket-Location", "ws://%s/web-socket" % headers["Host"]), \
					("Sec-WebSocket-Protocol", headers["Sec-WebSocket-Protocol"]), \
				]
				# now we have to figure out the key
				Value1 = 0
				Spaces1 = 0
				for char in headers["Sec-WebSocket-Key1"]:
					if(char.isdigit()):
						Value1 *= 10
						Value1 += int(char)
					elif(char == ' '):
						Spaces1 += 1
				Value1 /= Spaces1
				Value2 = 0
				Spaces2 = 0
				for char in headers["Sec-WebSocket-Key2"]:
					if(char.isdigit()):
						Value2 *= 10
						Value2 += int(char)
					elif(char == ' '):
						Spaces2 += 1
				Value2 /= Spaces2
				Value3 = sock.recv(8)
				# finish the handshake
				log(self, "got Sec-WebSocket from (%s, %s)" % addr, 3)
				self.writeHTTP(sock, 101, {}, None, responseHeaders)
				sock.send("\r\n" + hashlib.md5(struct.pack(">I", Value1) + struct.pack(">I", Value2) + Value3).digest())
				self.sessionAcceptQueue.insert((self.WebSocket(sock), addr))
				# now get out of the socket loop and let the cc server take over
				raise self.WebSocket(None)
			else:
				self.writeHTTP(sock, 400) #Bad Request
				log(self, "bad websocket request from (%s, %s)" % addr, 3);
				return
		elif(method == "GET"):
			try:
				resourceFile = file(".%s" % resource, "rb")
				resourceData = resourceFile.read()
				resourceFile.close()
			except:
				self.writeHTTP(sock, 404)
				log(self, "couldn't find %s" % resource, 3)
				return
			self.writeHTTP(sock, 200, {"Content-Type": mimeType}, resourceData)
			log(self, "served %s" % resource, 3)
		elif(method == "POST" and resource == "/file-upload"):
			if(getOptions.has_key("authkey") and self.isAuthorized(getOptions["authkey"])):
				log(self, "authorized file upload from (%s, %s), looking for file" % addr, 3)
				for part in body:
					if(part["headers"]["Content-Disposition"].has_key("filename")):
						filename = part["headers"]["Content-Disposition"]["filename"]
						newFileURI = "images/%s" % filename[1:-1] # filename is quoted
						outputFile = file(newFileURI, "wb")
						outputFile.write(part["data"])
						outputFile.close()
						log(self, "sucessfully uploaded file: %s" % filename, 3)
						self.writeHTTP(sock, 201, {}, newFileURI)
						self.fileUploaded(newFileURI)
						return
			else:
				log(self, "unauthorized upload attempt from (%s, %s)" % addr, 3)
				self.writeHTTP(sock, 403)
		elif(method == "POST" and resource == "/chat-data"):
			if(getOptions.has_key("sid") and getOptions.has_key("action")):
				if(getOptions["sid"] == "0"):
					session = self.sessionList.newSession(sock, addr)
					self.sessionAcceptQueue.insert((session, addr))
				else:
					session = self.sessionList.findBySID(getOptions["sid"])
				if(session):
					if(getOptions["action"] == "send"):
						session.queueRecvData(body)
						self.writeHTTP(sock, 200, {}, str(session.sid))
					elif(getOptions["action"] == "recv"):
						session.setSendSock(sock)
				else:
					log(self, "session not found: %s" % getOptions["sid"], 3)
					self.writeHTTP(sock, 404, {}, "Couldn't find session")
			else:
				self.writeHTTP(sock, 400, {}, "SID not provided")
		else:
			self.writeHTTP(sock, 501)
			log(self, "couldn't handle %s request" % method, 3)
	
	def acceptLoop(self, port=80): #Threaded per-server
		listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			listener.bind(('', port))
		except:
			log(self, "failed to bind port %d" % port)
			return
		log(self, "listening on port %d" % port)
		while 1:
			listener.listen(1)
			(sock, addr) = listener.accept()
			sockThread = threading.Thread(None, self.sockLoop, "sockLoop", (sock, addr))
			sockThread.setDaemon(1)
			sockThread.start()

	def sockLoop(self, sock, addr): #Threaded per-socket
		while 1:
			try:
				(method, resource, protocol, headers, body, getOptions) = self.readHTTP(sock)
			except IOError:
				log(self, "socket closed (%s, %s)" % addr, 3)
				return
			log(self, "%s %s from (%s, %s)" % (method, resource, addr[0], addr[1]), 3)
			try:
				self.handleReq(sock, addr, method, resource, protocol, headers, body, getOptions)
			except self.WebSocket:
				log(self, "WebSocket passed as session", 3)
				return
	
	def fileUploaded(self, filename):
		# this is an event handler to be overloaded by subclasses who actually care if this happens
		pass

	def isAuthorized(self, authKey):
		# this is used to check for file upload authoriziation should be overloaded by subclasses
		return False

class CC_Server:
	class connectionList:
		def __init__(self, parent):
			self.broadcastLock = threading.Lock()
			self.accessLock = threading.Lock()
			self.connections = list()
			self.parent = parent
		
		def broadcast(self, message, toAll=0):
			self.broadcastLock.acquire()
			for connection in self.connections:
				if(toAll or connection.named):
					connection.send(message)
			self.broadcastLock.release()
		
		def sendUserList(self):
			log(self, "sending userlist", 2)
			message = "35"
			for connection in self.connections:
				if(connection.named):
					message += "|%s" % connection.msg()
			self.broadcast(message, 1)
		
		def findByName(self, name):
			for user in self.connections:
				if(user.name == name):
					return user
			return None
		
		def debugMsg(self, connection, message):
			if(self.parent.prefs["debug_mode"]):
				self.sendPM(CC_Server.chatServer(2), connection, message, 1)
		
		def debugOrKick(self, connection, message):
			if(self.parent.prefs["debug_mode"]):
				self.sendPM(CC_Server.chatServer(3), connection, message, 1)
			else:
				self.kick(connection)
		
		def sendChat(self, sender, msg, flag=1):
			if(len(msg.strip()) > 0):
				message = "31|%s|^%d%s" % (sender.msg(), flag, msg)
				self.broadcast(message)
		
		def sendPM(self, sender, target, msg, flag=0):
			if(len(msg.strip()) > 0):
				message = "21|%s|^%d%s" % (sender.msg(), flag, msg)
				target.send(message)
		
		def changeName(self, connection, name):
			self.accessLock.acquire()
			connectMessages = { \
				1: "<links in from Cyan Worlds Age>", \
				4: "<links in from Cyan Guest Age>", \
				0: "<links in from somewhere on the internet age>", \
			}
			if(len(name) < 20 and len(name) > 1 and self.findByName(connection.name[0] + name) == None):
				self.debugMsg(connection, "Setting name to '%s' - login - successful" % name)
				oldname = connection.name[1:]
				wasnamed = connection.named
				connection.name = connection.name[0] + name
				connection.named = 1
				connection.send("11")
				if(wasnamed and self.parent.prefs["enable_protocol_extensions"]):
					self.sendChat(connection, "<[%s] is now known as [%s]>" % (oldname, name), 2)
				elif(connectMessages.has_key(connection.level())):
					self.sendChat(connection, connectMessages[connection.level()], 2)
				else:
					self.sendChat(connection, "<links in from somewhere on the internet age>", 2)
				self.sendUserList()
				self.parent.totallogins += 1
				if(self.currentlogins() > self.parent.maxlogins):
					self.parent.maxlogins = self.currentlogins()
			else:
				log(self, "rejecting name: %s" % name, 2)
				connection.send("10")
			self.accessLock.release()
		
		def removeName(self, connection, cause=0):
			self.accessLock.acquire()
			if(connection.named):
				self.debugMsg(connection, "Removing name - logout - successful")
				if(cause > 0):
					connection.named = 0
				if(cause == 2 and self.parent.prefs["enable_protocol_extensions"]):
					self.sendChat(connection, "<was kicked by the server *ZZZZZWHAP*>", 3)
				elif(cause == 1):
					self.sendChat(connection, "<mistakenly used an unsafe linking book without a maintainer's suit *ZZZZZWHAP*>", 3)
				else:
					self.sendChat(connection, "<links safely back to their home Age>", 3)
				connection.named = 0
				connection.name = connection.name[0] + str(connection.addr[1])
				self.sendUserList()
			self.accessLock.release()
		
		def sendWelcome(self, target, message):
			for line in message:
				if(len(line) > 0):
					target.send("40|%d%s" % (target.version, line))
		
		def sendIgnore(self, sender, target):
			target.send("70|%s" % sender)
		
		def setLevel(self, connection, level):
			self.accessLock.acquire()
			connection.name = str(level) + connection.name[1:]
			self.sendUserList()
			self.accessLock.release()
		
		def kick(self, target):
			if(target.authLevel < 2):
				self.sendPM(CC_Server.chatServer(3), target, "An oscillating inharmonic interference error(OIIE) was detected. Please close and restart your browser.", 1)
				self.remove(target, 2)
				if(self.parent.prefs["enable_bans"]):
					self.parent.banlist.append(target.addr[0])
		
		def insert(self, connection):
			self.accessLock.acquire()
			self.connections.append(connection)
			if(len(self.connections) > self.parent.maxconnections):
				self.parent.maxconnections = len(self.connections)
			self.sendUserList()
			self.accessLock.release()
		
		def remove(self, connection, cause=1):
			connection.sock.close()
			connection.status = 0
			self.removeName(connection, cause)
			self.accessLock.acquire()
			if(connection in self.connections):
				self.connections.remove(connection)
			self.accessLock.release()
		
		def currentlogins(self):
			total = 0
			for connection in self.connections:
				if(connection.named):
					total += 1
			return total
	
	class CC_Connection:
		def __init__(self, sock, addr):
			self.comLock = threading.Lock()
			self.name = "0%s" % addr[1]
			self.addr = addr
			self.sock = sock
			self.ipHash = addr[0].replace('.', '')
			self.status = 1 # 0 disconnected, 1 connected, 2 banned
			self.named = 0
			self.version = 0 # client version
			self.authLevel = 0
			self.authKey = str()
		
		def __repr__(self):
			return "[%s] (%s, %s)" % (self.name, self.addr[0], self.addr[1])
		
		def msg(self):
			if(self.ipHash):
				return "%s,%s" % (self.name, self.ipHash)
			else:
				return self.name
		
		def level(self):
			return int(self.name[0])
		
		def send(self, message):
			self.comLock.acquire()
			try:
				log(self, "sending: %s to %s" % (repr(message), self), 2)
				self.sock.send(message + "\r\n")
			except:
				log(self, "send error to: %s" % self, 2)
			self.comLock.release()
	
	def __init__(self):
		self.starttime = time.strftime('%a %b %d %H:%M:%S %Z %Y')
		self.connections = self.connectionList(self)
		self.quit = threading.Event()
		self.maxconnections = 0
		self.maxlogins = 0
		self.totallogins = 0
		self.banlist = []
		self.authDict = dict()
		self.HTTPServ = HTTP_Server()
		self.HTTPServ.redirects['/'] = "/ChatClient.html"
		self.welcomeMessage = """
			Welcome to %(server_version)s
			Using protocol versions 0, 1 and 2
			Written by 'Nadnerb'
			There are only a few rules:
			    Don't send invalid commands. ;)
			    Language filter is currently %(censor_level)s
			    Bans are currently %(enable_bans)s
			Comments can be sent to Nadnerb@urulive.guildaxis.net
			Server commands now available, type !\? at the beginning of a line."""
		self.welcomeParams = { \
			"server_version": ["value"], \
			"censor_level": ["disabled", "replace", "warn", "kick"], \
			"enable_bans": ["disabled", "enabled"], \
		}
		self.prefs = { \
			"server_version": "CyanChat (Py CC Server 2.0)", \
			"enable_http": 1, \
			"enable_cc": 1, \
			"cc_port": 1812, \
			"http_port": 81, \
			"welcome_file": "CCWelcome.conf", \
			"word_file": "BadWords.conf", \
			"enable_bans": 0, \
			"censor_level": 1, \
			"debug_mode": 0, \
			"enable_admin_extensions": 1, \
			"enable_protocol_extensions": 1, \
			"auth_1": "huru", \
			"auth_2": "tia", \
		}
		# dict levels
		# 0 - still bad with * inserted and leaded and ended by letters ("fuck", "fluck", "pairofducks")
		# 1 - bad if standalone with no inserted chars, warnable if led or ended with letters ("shit" kills, but "shits" warns)
		# 2 - bad if standalone with no inserted chars (ie "cunt" but not "count")
		# 3 - warnable if standalone with no inserted chars (ie "hell" but not "hello")
		self.badWords = {\
			"fuck": 0, \
			"shit": 1, \
			"bitch": 0, \
			"cunt": 1, \
			"anus": 2, \
			"penis": 0, \
			"vagina": 0, \
			"tits": 0, \
			"asshole": 0, \
			"bastard": 0, \
			"hell": 3, \
			"slut": 0, \
			"whore": 0, \
			"nigger": 0, \
			"pussy": 0, \
			"dickhead": 1, \
		}
	
	
	def chatServer(level=2):
		server = CC_Server.CC_Connection(None, ('', ''))
		server.name = "%dChatServer" % level
		return server
	chatServer = staticmethod(chatServer)
	
	def readPrefs(self, filename="CCServer.conf"):
		global logging
		log(self, "reading %s" % filename)
		prefsFile = file(filename, 'r')
		prefsData = prefsFile.read()
		prefsFile.close()
		newPrefs = parseToDict(prefsData, ':', '\n')
		for pref in newPrefs:
			newPrefs[pref] = newPrefs[pref].strip()
			if(newPrefs[pref].isdigit()):
				newPrefs[pref] = int(newPrefs[pref])
			if(pref == "log_level"):
				logging = newPrefs.pop(pref)
		self.prefs.update(newPrefs)
		self.readWelcome()
		self.readWordList()
	
	def readWelcome(self, filename=None):
		if(not filename):
			filename = self.prefs["welcome_file"]
		welcomeFile = file(filename, 'r')
		self.welcomeMessage = readTo(welcomeFile, "\n\n", ['\r'])
		welcomeParams = welcomeFile.read()
		welcomeFile.close()
		welcomeParams = parseToDict(welcomeParams, ':', '\n')
		for param in welcomeParams:
			parts = welcomeParams[param].split(',')
			for part in range(len(parts)):
				parts[part] = parts[part].strip()
			welcomeParams[param] = parts
		self.welcomeParams = welcomeParams

	def readWordList(self, filename=None):
		if(not filename):
			filename = self.prefs["word_file"]
		wordFile = file(filename, 'r')
		wordData = wordFile.read()
		wordFile.close()
		newWords = parseToDict(wordData, ':', '\n')
		for word in newWords:
			newWords[word] = int(newWords[word])
		self.badWords.update(newWords)
	
	def parseAuth(self):
		authLevel = 1
		while(self.prefs.has_key("auth_%d" % authLevel)):
			self.authDict[str(self.prefs["auth_%d" % authLevel])] = authLevel
			log(self, "set auth password for level %d: %s" % (authLevel, self.prefs["auth_%d" % authLevel]), 3)
			authLevel += 1
	
	def parseWelcome(self):
		insertValues = dict()
		for paramKey in self.welcomeParams:
			if(self.prefs.has_key(paramKey)):
				if(len(self.welcomeParams[paramKey]) > 1):
					insertValues[paramKey] = self.welcomeParams[paramKey][self.prefs[paramKey]]
				else:
					insertValues[paramKey] = self.prefs[paramKey]
			else:
				insertValues[paramKey] = "<%s>" % paramKey
		welcomeList = (self.welcomeMessage.replace('\t', '') % insertValues).splitlines()
		welcomeList.reverse()
		return welcomeList
	
	def start(self):
		self.parseAuth()
		if(self.prefs["enable_cc"]):
			acceptThread = threading.Thread(None, self.acceptLoop, "acceptLoop", (self.prefs["cc_port"],))
			acceptThread.setDaemon(1)
			acceptThread.start()
		if(self.prefs["enable_http"]):
			acceptThread = threading.Thread(None, self.acceptHTTP, "acceptHttpLoop", (self.prefs["http_port"],))
			acceptThread.setDaemon(1)
			acceptThread.start()
		self.run()
	
	def run(self):
		self.quit.wait()
	
	def addConnection(self, sock, addr):
		newConnection = self.CC_Connection(sock, addr)
		if(addr[0] in self.banlist):
			newConnection.status = 2
			log(self, "banned connection attempt from: %s" % newConnection.addr[0], 2)
		else:
			self.connections.insert(newConnection)
			log(self, "added new connection %s" % newConnection, 2)
		sockThread = threading.Thread(None, self.sockLoop, "sockLoop", (newConnection,))
		sockThread.setDaemon(1)
		sockThread.start()
		cleanupThread = threading.Thread(None, self.cleanSock, "cleanSock", (newConnection, sockThread))
		cleanupThread.setDaemon(1)
		cleanupThread.start()
	
	def acceptLoop(self, port=1812): #Threaded per-server
		listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			listener.bind(('', port))
		except:
			log(self, "failed to bind port %d" % port)
			self.quit.set()
			return
		log(self, "listening on port %d" % port)
		while 1:
			listener.listen(1)
			(sock, addr) = listener.accept()
			self.addConnection(sock, addr)
	
	def watchHTTP(self):
		self.HTTPServThread.join()
		log(self, "HTTP server thread terminated")
		self.quit.set() #Terminate the server if the HTTP server dies

	def acceptHTTP(self, port=81): #Threaded per-server
		self.HTTPServThread = threading.Thread(None, self.HTTPServ.acceptLoop, "HTTPServThread", (port,))
		self.HTTPServThread.setDaemon(1)
		self.HTTPServThread.start()
		self.HTTPWatchdogThread = threading.Thread(None, self.watchHTTP, "HTTPWatchdogThread", ())
		self.HTTPWatchdogThread.setDaemon(1)
		self.HTTPWatchdogThread.start()
		while 1:
			(sock, addr) = self.HTTPServ.sessionAcceptQueue.acceptHTTPSession()
			self.addConnection(sock, addr)
	
	def cleanSock(self, connection, sockThread):
		sockThread.join()
		self.connections.remove(connection)
		log(self, "connection socket removed: (%s, %s)" % connection.addr, 2)
	
	def sockLoop(self, connection): #Threaded per-socket
		while 1:
			line = readTo(connection.sock, '\n', ['\r'])
			if(not line or connection.status == 0):
				log(self, "lost connection to %s" % connection, 2)
				return
			#line = line.rstrip("\r\n")
			line = line.strip()
			log(self, "received: %s from %s" % (line, connection), 2) 
			line = self.censor(line)
			if(type(line) == int):
				if(line == 1): # warn
					self.connections.sendPM(self.chatServer(2), connection, "I can't repeat that!", 1)
					continue
				elif(line == 2): # kick/ban
					self.connections.kick(connection)
			msg = line.split('|', 1)
			cmd = msg[0]
			if(len(msg) == 2):
				msg = msg[1]
			else:
				msg = ''
			if(not cmd.isdigit()):
				log(self, "invalid command: %s from %s" % (cmd, connection), 2)
				self.connections.debugOrKick(connection, "ERROR>Unknown command. Line sent=%s" % line)
				continue
			self.handleMsg(connection, int(cmd), msg)
	
	def handleMsg(self, connection, cmd, msg):
		log(self, "command: %s from %s" % (cmd, connection), 2)
		if(connection.status == 2 and cmd != 40):
			self.connections.sendPM(self.chatServer(3), connection, "Access denied.", 1)
		elif(cmd == 40): # announce
			connection.version = int(msg)
			if(connection.status == 2):
				banMsg = ["This ip address[/%s] is blocked from using CyanChat until tomorrow." % connection.addr[0]]
				self.connections.sendWelcome(connection, banMsg)
			else:
				self.connections.sendWelcome(connection, self.parseWelcome())
		elif(cmd == 10): # set name
			self.connections.changeName(connection, msg)
		elif(cmd == 15): # logout
			self.connections.removeName(connection)
		elif(cmd == 30): # chat
			if(msg[2:].startswith("!\\")):
				if(self.handleServCmd(connection, msg[4:])):
					return
			if(connection.named):
				self.connections.debugMsg(connection, "Send broadcast message - successful")
				self.connections.sendChat(connection, msg[2:])
			else:
				self.connections.kick(connection)
		elif(cmd == 20): # pm
			if(connection.named):
				(user, msg) = msg.split("|", 1)
				user = user.split(",", 1)
				target = self.connections.findByName(user[0])
				if(target):
					self.connections.debugMsg(connection, "Send private message - successful")
					self.connections.sendPM(connection, target, msg[2:])
			else:
				self.connections.kick(connection)
		elif(cmd == 70): # ignore
			target = self.connections.findByName(msg)
			if(target):
				self.connections.debugMsg(connection, "Ignore user successful.")
				self.connections.sendIgnore(connection, target)
		elif(self.prefs["enable_admin_extensions"]):
			self.handleExt(connection, cmd, msg)
	
	def handleExt(self, connection, cmd, msg):
		if(cmd == 12): # auth
			if(self.authDict.has_key(msg)):
				connection.authLevel = self.authDict[msg]
				connection.authKey = hex(random.randint(0, 0x7FFFFFFF))[2:]
				connection.send("13|%d|%s" % (connection.authLevel, connection.authKey))
			else:
				log(self, "invalid password %s attempted by %s" % (msg, connection), 2)
				self.connections.kick(connection)
		elif(cmd == 50): # change level
			if(connection.authLevel > 0):
				msg = msg.split("|")
				target = self.connections.findByName(msg[0])
				if(target):
					self.connections.setLevel(target, int(msg[1]))
		elif(cmd == 51): # kick/ban
			if(connection.authLevel > 0):
				target = self.connections.findByName(msg)
				if(target):
					self.connections.kick(target)
		elif(cmd == 52): # clear bans
			if(connection.authLevel > 0):
				self.banlist = list()
		elif(cmd == 53): # change self level
			if(connection.authLevel > 0):
				self.connections.setLevel(connection, int(msg))
		elif(cmd == 60): # ChatServer message
			if(connection.authLevel > 1):
				self.connections.sendChat(self.chatServer(2), msg)
		elif(cmd == 80): # remote shutdown
			if(connection.authLevel > 1):
				self.connections.sendChat(self.chatServer(2), "Warning: Server is now shutting down")
				self.quit.set()
		elif(cmd == 90): # reload config
			if(connection.authLevel > 1):
				self.readPrefs()
	
	def handleServCmd(self, connection, msg):
		if(msg == "?"):
			self.showHelp(connection)
		elif(msg == "time"):
			self.showTime(connection)
		elif(msg == "stats"):
			self.showStats(connection)
		elif(msg == "reload"):
			self.readPrefs()
		else:
			return 0
		return 1
	
	def showHelp(self, connection):
		commandsmessage = ['!\\time	 (displays server current time)', '!\\stats	(displays server stats)', 'Server commands:']
		for line in commandsmessage:
			self.connections.sendPM(self.chatServer(2), connection, line, 1)
		
	def showTime(self, connection):
		self.connections.sendPM(self.chatServer(2), connection, "Current local server time is %s" % time.strftime('%a %b %d %H:%M:%S %Z %Y'), 1)
		
	def showStats(self, connection):
		statsmessage = [ \
			"The highest number of logins at one time is %d and highest number of connections is %d." % (self.maxlogins, self.maxconnections), \
			"Currently, there are %d people logged in. And %d connections." % (self.connections.currentlogins(), len(self.connections.connections)), \
			"There have been %d logins since CyanChat was started on %s" % (self.totallogins, self.starttime), \
			self.prefs["server_version"], \
		]
		for line in statsmessage:
			self.connections.sendPM(self.chatServer(2), connection, line, 1)
	
	def censor(self, line):
		# dict levels
		# 0 - still bad with * inserted and leaded and ended by letters ("fuck", "fluck", "pairofducks")
		# 1 - bad if standalone with no inserted chars, warnable if led or ended with letters ("shit" kills, but "shits" warns)
		# 2 - bad if standalone with no inserted chars (ie "cunt" but not "count")
		# 3 - warnable if standalone with no inserted chars (ie "hell" but not "hello")
		matches = []
		for key in self.badWords:
			for startIndex in range(len(line)):
				nonMatchChars = 0
				matchChars = 0
				endIndex = startIndex
				while nonMatchChars < 2 and matchChars < len(key) and endIndex < len(line):
					if(line[endIndex].lower() == key[matchChars].lower()):
						matchChars += 1
					elif(startIndex == endIndex):
						break
					else:
						nonMatchChars += 1
					endIndex += 1
				if(matchChars == len(key)):
					# we have a match, find out if it has leading or trailing chars
					lead = ' '
					if(startIndex - 1 >= 0):
						lead = line[startIndex - 1]
					trail = ' '
					if(endIndex < len(line)):
						trail = line[endIndex]
					ltchars = False
					if(lead != ' ' or trail != ' '):
						ltchars = True
					# now we have all our data, let's determine what to do about it
					# matches format: [start, end, warn]
					if(self.badWords[key] == 0):
						matches.append([startIndex, endIndex, 0])
					elif(self.badWords[key] == 1):
						if(nonMatchChars == 0 and ltchars == False):
							matches.append([startIndex, endIndex, 0])
						elif(nonMatchChars == 0):
							matches.append([startIndex, endIndex, 1])
					elif(self.badWords[key] == 2):
						if(nonMatchChars == 0 and ltchars == False):
							matches.append([startIndex, endIndex, 0])
					elif(self.badWords[key] == 3):
						if(nonMatchChars == 0 and ltchars == False):
							matches.append([startIndex, endIndex, 1])
		# censor levels
		# 0 - no censor (unless in relay mode, then switch to 1)
		# 1 - replace occurances with ****
		# 2 - warn "I can't repeat that"
		# 3 - kick/ban (unless in relay mode, then switch to 2)
		if(self.prefs["censor_level"] == 1):
			for match in matches:
				fill = ''
				for i in range(match[1] - match[0]):
					fill += '*'
				line = line[0:match[0]] + fill + line[match[1]:]
		elif(self.prefs["censor_level"] == 2):
			if(len(matches) > 0):
				return 1
		elif(self.prefs["censor_level"] == 3):
			if(len(matches) > 0):
				for match in matches:
					if(match[2] == 0):
						return 2
				return 1
		return line

class CC_Relay(CC_Server):
	class connectionList(CC_Server.connectionList):
		def insert(self, connection):
			CC_Server.connectionList.insert(self, connection)
			connection.relaySock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			try:
				connection.relaySock.connect((self.parent.prefs["relay_addr"], self.parent.prefs["relay_port"]))
				connection.connectEvent.set()
				relayRecvThread = threading.Thread(None, self.parent.relayRecvLoop, "relayRecvLoop", (connection,))
				relayRecvThread.setDaemon(1)
				relayRecvThread.start()
			except: #except Exception as error:
				#print error
				log(self, "error connecting to relay target %s" % self.parent.prefs["relay_addr"], 2)
				self.sendPM(CC_Server.chatServer(3), connection, "Error connecting to relay target", 1)
				connection.connectEvent.set() #allow the loop to run, but it will throw errors on every forward
		
		def sendUserList(self):
			pass
		
		def removeName(self, connection, cause=1):
			pass
		
		def findBySubName(self, name):
			for user in self.connections:
				if(user.name[1:] == name):
					return user
			return None
		
		def remove(self, connection, cause=1):
			CC_Server.connectionList.remove(self, connection, cause=1)
			connection.relaySock.close()
	
	class CC_Connection(CC_Server.CC_Connection):
		def __init__(self, sock, address):
			CC_Server.CC_Connection.__init__(self, sock, address)
			self.relaySock = socket.socket()
			self.relayComLock = threading.Lock()
			self.connectEvent = threading.Event()
		
		def forward(self, message):
			self.connectEvent.wait()
			self.relayComLock.acquire()
			try:
				log(self, "forwarding: %s from %s" % (repr(message), self), 2)
				self.relaySock.send(message + "\r\n")
			except:
				log(self, "forward error from: %s" % self, 2)
			self.relayComLock.release()
	
	def __init__(self):
		CC_Server.__init__(self)
		relayPrefs = { \
			"relay_port": 1813, \
			"relay_addr": "cho.cyan.com", \
			"shadow_users": 0, \
		}
		self.prefs.update(relayPrefs)
		self.shadowUserList = list()
		self.shadowListLock = threading.Lock()
	
	def relayRecvLoop(self, connection): #Threaded per-relay-socket
		while 1:
			try:
				line = readTo(connection.relaySock, '\n', ['\r'])
			except:
				log(self, "removed relay connection to server for: %s" % connection, 2)
				return
			if(not line):
				log(self, "lost connection to server on: %s" % connection, 2)
				return
			#line = line.rstrip("\r\n")
			line = line.strip()
			log(self, "received: %s for %s" % (line, connection), 2)
			msg = line.split('|', 1)
			cmd = msg[0]
			if(len(msg) == 2):
				msg = msg[1]
			else:
				msg = ''
			if(not cmd.isdigit()):
				log(self, "invalid command from server: %s not relaying to %s" % (cmd, connection), 2)
				continue
			self.handleServMsg(connection, int(cmd), msg)
	
	def sendShadowUserList(self):
		if(self.prefs["shadow_users"]):
			self.shadowListLock.acquire()
			self.shadowUserList = self.replaceUsers(self.shadowUserList)
			msg = '|'.join(self.shadowUserList)
			self.connections.broadcast("%d|%s" % (35, msg))
			self.shadowListLock.release()
	
	def replaceUsers(self, users):
		for user in range(len(users)):
			relayUser = self.connections.findBySubName(users[user].split(',')[0][1:])
			if(relayUser):
				users[user] = relayUser.msg()
		return users
	
	def handleServMsg(self, connection, cmd, msg):
		if(cmd == 11):
			connection.name = connection.name[0] + connection.lastAttemptedName
			connection.named = 1
		if(self.prefs["shadow_users"]):
			if(cmd == 35):
				self.shadowListLock.acquire()
				self.shadowUserList = self.replaceUsers(msg.split('|'))
				msg = '|'.join(self.shadowUserList)
				self.shadowListLock.release()
			elif(cmd in [21, 31]):
				msg = msg.split('|', 1)
				msg = '|'.join([self.replaceUsers([msg[0]])[0], msg[1]])
		log(self, "relaying to %s" % connection, 2)
		connection.send("%d|%s" % (cmd, msg))
	
	def handleMsg(self, connection, cmd, msg):
		if(connection.status == 2 and cmd != 40):
			self.connections.sendPM(CC_Server.chatServer(3), connection, "Access denied.", 1)
		elif(cmd == 40): # announce
			connection.version = int(msg)
			if(connection.status == 2):
				banMsg = ["This ip address[/%s] is blocked from using CyanChat until tomorrow." % connection.addr[0]]
				self.connections.sendWelcome(connection, banMsg)
				return
		elif(cmd == 10): # set name
			connection.lastAttemptedName = msg
		elif(self.prefs["enable_admin_extensions"]):
			self.handleExt(connection, cmd, msg)
		if(cmd in [50, 51, 53]):
			self.sendShadowUserList()
		elif(cmd in [10, 40] or (cmd in [15, 20, 30, 70] and connection.named)):
			log(self, "forwarding %s to server" % "%d|%s" % (cmd, msg), 2)
			connection.forward("%d|%s" % (cmd, msg))
		if(cmd == 15): # logout (must be done after forward, or the above will block it)
			connection.named = 0

class TIA_Server(CC_Server):
	# The TIA server is a big, nasty, hack/hunk of server extensions
	# I should really rewrite it once I get a clearer idea of what it's supposed to do. <_<
	class connectionList(CC_Server.connectionList):
		def changeName(self, connection, name):
			CC_Server.connectionList.changeName(self, connection, name)
			if(connection.named):
				# what this is actually doing is chainging the setGrid command with the tileImgList command
				# you don't see the setGrid command because it's actually in the tileGrid list .... OMGHAX
				message = "tileImgList|%d|%s|%s" % (len(self.parent.imageList), '|'.join(self.parent.imageList), '|'.join(self.parent.tileGrid))
				self.sendPM(self.parent.chatServer(2), connection, message, 1)
				self.sendPlayerPosList()
		
		def removeName(self, connection, cause=0):
			CC_Server.connectionList.removeName(self, connection, cause)
			self.sendPlayerPosList()
		
		def setLevel(self, connection, level):
			CC_Server.connectionList.setLevel(self, connection, level)
			self.sendPlayerPosList()
		
		def sendPlayerPosList(self):
			self.accessLock.acquire()
			out = []
			for connection in self.connections:
				if(connection.named):
					out.append("%s|%s|%s|%s" % (connection.name, connection.playerImg, connection.playerPos, connection.playerLight))
			self.sendChat(self.parent.chatServer(2), "players|%d|%s" % (len(out), '|'.join(out)))
			self.accessLock.release()
		
		def updatePlayer(self, player, pos, light):
			self.accessLock.acquire()
			player.playerPos = pos
			player.playerLight = light
			log(self, "updated %s pos: %s" % (player, player.playerPos), 2)
			self.accessLock.release()
	
	class CC_Connection(CC_Server.CC_Connection):
		def __init__(self, sock, addr):
			CC_Server.CC_Connection.__init__(self, sock, addr)
			self.playerPos = "0|0|0"
			self.playerLight = "0"
			self.playerImg = str(int(addr[1]) % 6) #HAAAAX!!!!
	
	def __init__(self):
		CC_Server.__init__(self)
		self.tileGrid = list()
		self.imageList = list()
		self.HTTPServ.redirects['/'] = "TIAClient.html"
		self.HTTPServ.isAuthorized = self.checkAuthKey
		self.HTTPServ.fileUploaded = self.addNewTile
		tiaPrefs = { \
			"grid_filename": "tileGrid.dat", \
			"tile_filename": "tileImages.dat", \
			"pos_filename": "/dev/null", \
		}
		self.prefs.update(tiaPrefs)
	
	def start(self):
		self.readTileData()
		CC_Server.start(self)
	
	def handleMsg(self, connection, cmd, msg):
		CC_Server.handleMsg(self, connection, cmd, msg)
		if(cmd == 30):
			msg = msg[2:]
			if(connection.level() > 0):
				# save the results if it's a grid changing message
				if(msg.startswith("setGrid")):
					self.tileGrid = msg.split('|')
					self.updateGridFile()
				elif(msg.startswith("setTile")):
					args = msg.split('|')
					index = int(args[1]) + int(args[2]) * int(self.tileGrid[2]) + int(args[3]) * int(self.tileGrid[2]) * int(self.tileGrid[3])
					self.tileGrid[index + 11] = args[4]
					self.updateGridFile()
			if(msg.startswith("playerMove")):
				# name, <pos>, light
				args = msg.split('|')
				player = self.connections.findByName(args[1])
				# permissions: you can only edit your own pos unless you're admin or guested
				if(player and (player == connection or connection.level() > 0)):
					self.connections.updatePlayer(player, '|'.join(args[2:5]), args[5])
				else:
					self.connections.sendPlayerPosList()
	
	def readTileData(self):
		try:
			imgsIn = file(self.prefs["tile_filename"], 'r')
		except:
			imgsOut = file(self.prefs["tile_filename"], 'w')
			imgsOut.close()
		else:
			self.imageList = imgsIn.read().splitlines()
			imgsIn.close()
		# also need to read grid data
		try:
			gridIn = file(self.prefs["grid_filename"], 'r')
		except:
			pass
		else:
			self.tileGrid = gridIn.read().split('|')
			gridIn.close()

	def addNewTile(self, filename):
		self.imageList.append(filename)
		imgsOut = file(self.prefs["tile_filename"], 'w')
		imgsOut.write('\n'.join(self.imageList))
		imgsOut.close()
		self.connections.sendChat(self.chatServer(2), "tileImgList|%d|%s" % (len(self.imageList), '|'.join(self.imageList)))

	def checkAuthKey(self, authKey):
		log(self, "checking authkey: %s" % authKey, 3)
		for connection in self.connections.connections:
			if(connection.authKey != "" and connection.authKey == authKey):
				return True
		return False	
		
	def updateGridFile(self):
		gridOut = file(self.prefs["grid_filename"], 'w')
		gridOut.write('|'.join(self.tileGrid))
		gridOut.close()

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
	Server.readPrefs()
	Server.start()
else:
	print "usage: python %s [%s]" % (sys.argv[0], '|'.join(serverClasses.keys()))
