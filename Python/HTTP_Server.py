from Logger import *
from Utils import *

import socket
import struct
import base64
import time
try:
	import hashlib
except:
	import md5 as hashlib

class HTTP_Server:
	statusCodes = { \
		100: "Continue", \
		#101: "Web Socket Protocol Handshake", \
		101: "Switching Protocols", \
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
		self.sessionQueues = dict()
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
			redirect = self.redirects[resource]
			if(type(redirect) == type(str())):
				self.writeHTTP(sock, 301, {"Location": redirect}, "301 Redirect")
				log(self, "redirected %s from %s to %s" % (addr, resource, self.redirects[resource]), 3)
				return
			elif(headers.has_key(redirect["header"]) and headers[redirect["header"]].find(redirect["value"]) != -1):
				self.writeHTTP(sock, 301, {"Location": redirect["location"]}, "301 Redirect")
				log(self, "redirected request for %s to %s due to %s value containing %s" % ( \
					resource, \
					redirect["location"], \
					redirect["header"], \
					redirect["value"]), 3)
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
			if(headers.has_key("WebSocket-Protocol") and self.sessionQueues.has_key(headers["WebSocket-Protocol"])): # protocol draft 75
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
				self.sessionQueues[headers["WebSocket-Protocol"]].insert((self.WebSocket(sock), addr))
				# now get out of the socket loop and let the cc server take over
				return "WebSocket" 
			elif(headers.has_key("Sec-WebSocket-Protocol") and self.sessionQueues.has_key(headers["Sec-WebSocket-Protocol"]) and not headers.has_key("Sec-WebSocket-Version")): # protocol draft 76
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
				self.sessionQueues[headers["Sec-WebSocket-Protocol"]].insert((self.WebSocket(sock), addr))
				# now get out of the socket loop and let the cc server take over
				return "WebSocket"
			elif(headers.has_key("Sec-WebSocket-Version") and headers["Sec-WebSocket-Version"] == "8" and self.sessionQueues.has_key(headers["Sec-WebSocket-Protocol"])): # http://tools.ietf.org/html/draft-ietf-hybi-thewebsocketprotocol-08
				responseHeaders = [ \
					# HTTP/1.1 101 Switching Protocols
				        ("Upgrade", "websocket"), \
			        	("Connection", "Upgrade"), \
			        	("Sec-WebSocket-Accept", base64.b64encode(hashlib.sha1(headers["Sec-WebSocket-Key"] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())), \
			        	("Sec-WebSocket-Protocol", headers["Sec-WebSocket-Protocol"]), \
				]
				log(self, "got Sec-WebSocket Version 8 from (%s, %s)" % addr, 3)
				self.writeHTTP(sock, 101, {}, None, responseHeaders)
				self.sessionQueues[headers["Sec-WebSocket-Protocol"]].insert((self.WebSocket(sock), addr))
				return "WebSocket"
			else:
				self.writeHTTP(sock, 400) #Bad Request
				log(self, "bad websocket request from (%s, %s)" % addr, 3);
				return
		elif(method == "GET"):
			try:
				resourceFile = file("../HTML/%s" % resource, "rb")
				resourceData = resourceFile.read()
				resourceFile.close()
			except:
				self.writeHTTP(sock, 404)
				log(self, "couldn't find %s" % resource, 3)
				return
			self.writeHTTP(sock, 200, {"Content-Type": mimeType}, resourceData)
			log(self, "served %s" % resource, 3)
		elif(method == "POST" and resource == "/file-upload"):
			if(getOptions.has_key("authkey") and self.isAuthorized(getOptions["authkey"]) > 1):
				log(self, "authorized file upload from (%s, %s), looking for file" % addr, 3)
				for part in body:
					if(part["headers"]["Content-Disposition"].has_key("filename")):
						filename = part["headers"]["Content-Disposition"]["filename"][1:-1] # filename is quoted
						if(filename == ""):
							log(self, "empty filename", 3)
							self.writeHTTP(sock, 400, {}, "empty filename")
							return
						newFileURI = "images/%s" % filename
						outputFile = file("../HTML/%s" % newFileURI, "wb")
						outputFile.write(part["data"])
						outputFile.close()
						log(self, "sucessfully uploaded file: %s" % filename, 3)
						self.writeHTTP(sock, 201, {}, newFileURI)
						self.fileUploaded(newFileURI)
						return
				log(self, "no file found", 3)
				self.writeHTTP(sock, 400, {}, "no file in post")
			else:
				log(self, "unauthorized upload attempt from (%s, %s)" % addr, 3)
				self.writeHTTP(sock, 403)
		elif(method == "POST" and resource == "/chat-data"):
			if(getOptions.has_key("sid") and getOptions.has_key("action") and getOptions.has_key("protocol") and self.sessionQueues.has_key(getOptions["protocol"])):
				if(getOptions["sid"] == "0"):
					session = self.sessionList.newSession(sock, addr)
					self.sessionQueues[getOptions["protocol"]].insert((session, addr))
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
		listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
			if(self.handleReq(sock, addr, method, resource, protocol, headers, body, getOptions) == "WebSocket"):
				log(self, "WebSocket passed as session", 3)
				return

	def registerProtocol(self, protocol):
		if(not self.sessionQueues.has_key(protocol)):
			self.sessionQueues[protocol] = self.acceptQueue()
			return self.sessionQueues[protocol]
		else:
			raise Exception("Protocol '%s' already registered" % protocol)
	
	def fileUploaded(self, filename):
		# this is an event handler to be overloaded by subclasses who actually care if this happens
		pass

	def isAuthorized(self, authKey):
		# this is used to check for file upload authoriziation should be overloaded by subclasses
		return False

