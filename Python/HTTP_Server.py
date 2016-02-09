from Logger import *
from Utils import *

import socket
import struct
import base64
import urllib
import time
import ssl
try:
	import hashlib
	md5 = hashlib.md5
	sha1 = hashlib.sha1
except:
	import md5
	import sha
	md5 = md5.md5
	sha1 = sha.sha

def recvall(sock, size):
	data = ''
	while(len(data) < size):
		data += sock.recv(size - len(data))
	return data

def lowerKeys(in_dict):
	out_dict = {}
	for i in in_dict:
		out_dict[i.lower()] = in_dict[i]
	return out_dict

class HTTP_Server:
	statusCodes = { \
		100: "Continue", \
		#101: "Web Socket Protocol Handshake", \
		101: "Switching Protocols", \
		200: "OK", \
		201: "Created", \
		#301: "Moved Permanently", \
		302: "Found", \
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
					session.close()
					log(self, "removed timed out session: %s" % session.sid, 3)
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
			self.frameBuffer = list()
			self.recvBuffer = list()
			self.sendSock = None
			self.lastResponseTime = time.time()
			self.closed = False
		
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

		def recvFrame(self):
			self.recvLock.acquire()
			log(self, "attempting recvFrame from: %s" % self.sid, 4)
			while(len(self.frameBuffer) < 1):
				log(self, "no data, holding: %s" % self.sid, 4)
				self.recvLock.release()
				self.waitLock.wait()
				self.waitLock.clear()
				if(self.closed):
					return ''
				self.recvLock.acquire()
			frame = self.frameBuffer.pop(0)
			self.recvLock.release()
			return frame

		def recv(self, count):
			data = ''
			while(len(data) < count):
				if(self.closed):
					return ''
				while(len(self.recvBuffer) and len(data) < count):
					data += self.recvBuffer.pop(0)
				if(len(data) < count):
					self.recvBuffer.extend(self.recvFrame())
			return data
		
		def close(self):
			self.closed = True
			self.waitLock.set()
			self.sendLock.release()
		
		def queueRecvData(self, data):
			self.recvLock.acquire()
			self.frameBuffer.append(data)
			log(self, "received data from %s" % self.sid, 3)
			#log(self, "buffered frame: %s" % repr(data), 4)
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

		def recvFrame(self):
			data = ''
			assert(self.sock.recv(1) == '\x00')
			while True:
				byte = self.sock.recv(1)
				if(byte == '\xFF'):
					return data
				data += byte
		
		def close(self):
			self.sock.close()

	class WebSocket2:
		def __init__(self, sock):
			self.sock = sock
			self.buffer = list()
			self.closed = False

		def send(self, data, opcode=1): # opcode 1 is text, 9 is ping, A is pong
			self.sock.send(struct.pack("B", 0x80 | (0x0F & opcode))) # final frame of opcode type
			if(len(data) > 0xFFFF):
				self.sock.send(struct.pack("B", 127))
				self.sock.send(struct.pack(">Q", len(data)))
			elif(len(data) > 125):
				self.sock.send(struct.pack("B", 126))
				self.sock.send(struct.pack(">H", len(data)))
			else:
				self.sock.send(struct.pack("B", len(data)))
			self.sock.sendall(data)

		def decode(data, key):
			out = ''
			for i in range(len(data)):
				out += chr(ord(data[i]) ^ ord(key[i % len(key)]))
			return out
		decode = staticmethod(decode)
		
		def recvPayload(self):
			payLen = struct.unpack("B", self.sock.recv(1))[0] & 0x7F
			if(payLen == 126):
				payLen = struct.unpack(">H", self.sock.recv(2))[0]
			elif(payLen == 127):
				payLen = struct.unpack(">Q", self.sock.recv(8))[0]
			key = self.sock.recv(4)
			return self.decode(recvall(self.sock, payLen), key)

		def recvFrame(self):
			data = ''
			while(True):
				start = struct.unpack("B", self.sock.recv(1))[0]
				final_fragment = ((start & 0x80) != 0)
				opcode = start & 0x0F
				if(opcode in [0, 1, 2]):
					# fragment, text data, binary data 
					data += self.recvPayload()
					if(final_fragment):
						log(self, "recieved data frame: %r" % data, 4)
						return data
				elif(opcode == 8): # close opcode
					log(self, "recieved close frame: %r" % self.recvPayload())
					self.closed = True
					return ''
				elif(opcode == 9): # ping opcode
					pingdata = self.recvPayload()
					self.send(pingdata, 0x0A) # pong
					log(self, "recieved ping frame: %r" % pingdata, 4)
				elif(opcode == 10): # pong opcode
					pongdata = self.recvPayload()
					log(self, "received pong frame: %r" % pongdata, 4)

		def recv(self, count):
			data = ''
			while(len(data) < count):
				if(self.closed):
					return ''
				while(len(self.buffer) and len(data) < count):
					data += self.buffer.pop(0)
				if(len(data) < count):
					self.buffer.extend(self.recvFrame())
			return data

		def close(self):
			self.send('', 0x08) # close opcode
			self.sock.close()
	
	class acceptQueue:
		def __init__(self):
			self.queueLen = threading.Semaphore(0)
			self.queue = list()
			
		def insert(self, session):
			self.queue.insert(0, session)
			self.queueLen.release()
		
		def acceptHTTPSession(self): #Called by external application to get incoming HTTP sessions
			self.queueLen.acquire()
			return self.queue.pop()
	
	def __init__(self, webRoot="../HTML", SSLRedirect=False):
		self.sessionList = self.sessionList()
		self.sessionQueues = dict()
		self.redirects = dict()
		self.webRoot = webRoot
		self.SSLRedirect = SSLRedirect
	
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
		headers = lowerKeys(parseToDict(data, ": ", "\r\n"))
		body = False
		if(headers.has_key("expect") and headers["expect"] == "100-continue"):
			sock.send("HTTP/1.1 100 Continue\r\n\r\n")
		if(headers.has_key("content-length")):
			body = recvall(sock, int(headers["content-length"]))
		if(headers.has_key("content-type") and headers["content-type"].startswith("multipart/form-data")):
			formHeaders = parseToDict(headers["content-type"], '=', "; ")
			log(self, "multipart/form-data boundary: %s" % formHeaders["boundary"], 3)
			if(body):
				log(self, "Nice client gave us a Content-Length: %s" % headers["content-length"], 3)
			else:# didn't send us a goddamn Content-Length
				body = readTo(sock, "--%s--" % formHeaders["boundary"], [])
				log(self, "No Content-Length, read multipart from sock using boundary, length: %d" % len(formData), 3)
			body = body.split("--%s" % formHeaders["boundary"])[1:-1]
			output = list()
			for data in body:
				(dataHeaders, data) = data.split("\r\n\r\n", 1)
				dataHeaders = lowerKeys(parseToDict(dataHeaders, ": ", "\r\n"))
				if(dataHeaders.has_key("content-disposition")):
					dataHeaders["content-disposition"] = parseToDict(dataHeaders["content-disposition"], '=', "; ")
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
		if(self.SSLRedirect and type(sock) is not ssl.SSLSocket):
			self.writeHTTP(sock, 302, {"Location": "https://%s:%d/%s" % (headers["host"], self.SSLRedirect, resource)}, "302 Redirect")
			log(self, "redirected request from %r for %r to port %d as https" % (addr, urllib.unquote(resource), self.SSLRedirect), 3)
			return
		resource = urllib.unquote(resource)
		if(self.redirects.has_key(resource)):
			redirect = self.redirects[resource]
			if(type(redirect) is str):
				self.writeHTTP(sock, 302, {"Location": redirect}, "302 Redirect")
				log(self, "redirected %r from %s to %s" % (addr, resource, self.redirects[resource]), 3)
				return
			elif(headers.has_key(redirect["header"]) and headers[redirect["header"]].find(redirect["value"]) != -1):
				self.writeHTTP(sock, 302, {"Location": redirect["location"]}, "302 Redirect")
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
			if(headers.has_key("websocket-protocol") and self.sessionQueues.has_key(headers["websocket-protocol"])): # protocol draft 75
				responseHeaders = [ \
					("Upgrade", "WebSocket"), \
					("Connection", "Upgrade"), \
					("WebSocket-Origin", headers["origin"]), \
					("WebSocket-Location", "%s://%s/web-socket" % (["ws", "wss"][type(sock) is ssl.SSLSocket], headers["host"])), \
					("WebSocket-Protocol", headers["websocket-protocol"]), \
				]
				log(self, "got WebSocket from %r" % (addr,), 3)
				self.writeHTTP(sock, 101, {}, None, responseHeaders)
				sock.send("\r\n")
				self.sessionQueues[headers["websocket-protocol"]].insert((self.WebSocket(sock), addr))
				# now get out of the socket loop and let the cc server take over
				return "WebSocket" 
			elif(headers.has_key("sec-websocket-protocol") and self.sessionQueues.has_key(headers["sec-websocket-protocol"]) and not headers.has_key("sec-websocket-version")): # protocol draft 76
				responseHeaders = [ \
					("Upgrade", "WebSocket"), \
					("Connection", "Upgrade"), \
					("Sec-WebSocket-Origin", headers["origin"]), \
					("Sec-WebSocket-Location", "%s://%s/web-socket" % (["ws", "wss"][type(sock) is ssl.SSLSocket], headers["host"])), \
					("Sec-WebSocket-Protocol", headers["sec-websocket-protocol"]), \
				]
				# now we have to figure out the key
				Value1 = 0
				Spaces1 = 0
				for char in headers["sec-websocket-key1"]:
					if(char.isdigit()):
						Value1 *= 10
						Value1 += int(char)
					elif(char == ' '):
						Spaces1 += 1
				Value1 /= Spaces1
				Value2 = 0
				Spaces2 = 0
				for char in headers["sec-websocket-key2"]:
					if(char.isdigit()):
						Value2 *= 10
						Value2 += int(char)
					elif(char == ' '):
						Spaces2 += 1
				Value2 /= Spaces2
				Value3 = sock.recv(8)
				# finish the handshake
				log(self, "got Sec-WebSocket from %r" % (addr,), 3)
				self.writeHTTP(sock, 101, {}, None, responseHeaders)
				sock.send("\r\n" + md5(struct.pack(">I", Value1) + struct.pack(">I", Value2) + Value3).digest())
				self.sessionQueues[headers["sec-websocket-protocol"]].insert((self.WebSocket(sock), addr))
				# now get out of the socket loop and let the cc server take over
				return "WebSocket"
			elif(headers.has_key("sec-websocket-version") and headers["sec-websocket-version"] in ["8", "13"] and self.sessionQueues.has_key(headers["sec-websocket-protocol"])): # http://tools.ietf.org/html/draft-ietf-hybi-thewebsocketprotocol-08
				responseHeaders = [ \
				        ("Upgrade", "websocket"), \
			        	("Connection", "Upgrade"), \
					("Sec-WebSocket-Accept", base64.encodestring(sha1(headers["sec-websocket-key"] + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest()).strip()), \
			        	("Sec-WebSocket-Protocol", headers["sec-websocket-protocol"]), \
				]
				log(self, "got Sec-WebSocket Version 8 from %r" % (addr,), 3)
				self.writeHTTP(sock, 101, {}, None, responseHeaders)
				sock.send("\r\n")
				self.sessionQueues[headers["sec-websocket-protocol"]].insert((self.WebSocket2(sock), addr))
				return "WebSocket"
			else:
				self.writeHTTP(sock, 400) #Bad Request
				log(self, "bad websocket request from %r headers: %r" % (addr, headers), 3);
				return
		elif(method == "GET"):
			try:
				resourceFile = file("%s/%s" % (self.webRoot, resource), "rb")
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
				log(self, "authorized file upload from %r, looking for file" % (addr,), 3)
				for part in body:
					if(part["headers"]["Content-Disposition"].has_key("filename")):
						filename = part["headers"]["Content-Disposition"]["filename"][1:-1] # filename is quoted
						if(filename == ""):
							log(self, "empty filename", 3)
							self.writeHTTP(sock, 400, {}, "empty filename")
							return
						newFileURI = "images/%s" % filename
						outputFile = file("%s/%s" % (self.webRoot, newFileURI), "wb")
						outputFile.write(part["data"])
						outputFile.close()
						log(self, "sucessfully uploaded file: %s" % filename, 3)
						self.writeHTTP(sock, 201, {}, newFileURI)
						self.fileUploaded(newFileURI)
						return
				log(self, "no file found", 3)
				self.writeHTTP(sock, 400, {}, "no file in post")
			else:
				log(self, "unauthorized upload attempt from %r" % (addr,), 3)
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
	
	def acceptLoop(self, port=80, useSSL=False): #Threaded per-server port
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
			if(useSSL):
				try:
					sock = ssl.wrap_socket(sock, server_side=True, certfile="server.crt", keyfile="server.key", suppress_ragged_eofs=True)
				except Exception as error:
					log(self, "Error during SSL handshake: %s" % error)
					continue
			sockThread = threading.Thread(None, self.sockLoop, "sockLoop", (sock, addr))
			sockThread.setDaemon(1)
			sockThread.start()

	def sockLoop(self, sock, addr): #Threaded per-socket
		while 1:
			try:
				(method, resource, protocol, headers, body, getOptions) = self.readHTTP(sock)
			except IOError:
				log(self, "socket closed %r" % (addr,), 3)
				return
			log(self, "%s %s from %r" % (method, resource, addr), 3)
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

