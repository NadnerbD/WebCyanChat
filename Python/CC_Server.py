import Logger
log = Logger.log

from Utils import readTo, parseToDict
from HTTP_Server import HTTP_Server

import threading
import random
import socket
import time

# check for the dnspython module
# if it is available, we can use it to do reverse dns lookups
try:
	from dns import resolver, reversename
	HAS_DNSPYTHON = True
except ImportError:
	HAS_DNSPYTHON = False

class CC_Server(object):
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

		def findByBounceKey(self, key):
			for user in self.connections:
				if(user.bounceKey == key):
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
				elif(HAS_DNSPYTHON and self.parent.prefs["use_reverse_dns"]):
					try:
						addr = reversename.from_address(connection.addr[0])
						host = '.'.join(str(resolver.query(addr, "PTR")[0]).split('.')[-3:-1])
					except:
						host = "somewhere on the internet"
					self.sendChat(connection, "<links in from %s Age>" % host, 2)
				else:
					self.sendChat(connection, "<links in from somewhere on the internet Age>", 2)
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
			self.accessLock.acquire()
			target.send("70|%s" % sender.msg())
			# cho broadcasts the userlist immediately following an ignore forward
			# this is to refresh the client userlist
			self.sendUserList()
			self.accessLock.release()
		
		def setLevel(self, connection, level):
			self.accessLock.acquire()
			connection.name = str(level) + connection.name[1:]
			self.sendUserList()
			self.accessLock.release()
		
		def checkAuthKey(self, authKey):
			log(self, "checking authkey: %s" % authKey, 3)
			for connection in self.connections:
				if(connection.authKey != "" and connection.authKey == authKey):
					return connection.authLevel
			return 0
		
		def kick(self, target):
			# disconnected admins may be kicked, as they may be ghosting
			if(target.authLevel < 2 or target.bounceDisconnected.isSet()):
				# prevent the bouncer from holding on to the connection if we're kicking it
				target.bounceEnable = False
				if(target.bounceDisconnected.isSet()):
					# restart the target's sock loop so it will be cleaned up and not wait forever
					target.bounceConnect.set()
				else:
					# only send this PM if there's a connected client to see it
					self.sendPM(CC_Server.chatServer(3), target, "An oscillating inharmonic interference error(OIIE) was detected. Please close and restart your browser.", 1)
				self.remove(target, 2)
				if(self.parent.prefs["enable_bans"]):
					self.parent.banlist.append(target.addr[0])
		
		def insert(self, connection):
			self.accessLock.acquire()
			# give the connection a random (unique) bounceKey
			while(connection.bounceKey == "" or self.findByBounceKey(connection.bounceKey) != None):
				connection.bounceKey = hex(random.randint(0, 0x7FFFFFFE))[2:]
			self.connections.append(connection)
			if(len(self.connections) > self.parent.maxconnections):
				self.parent.maxconnections = len(self.connections)
			self.sendUserList()
			self.accessLock.release()
		
		def remove(self, connection, cause=1):
			try:
				connection.sock.close()
			except:
				pass
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
			# bouncer data
			self.bounceEnable = 0
			self.bounceBufferSize = 0
			self.bounceKey = ""
			self.bounceDisconnected = threading.Event()
			self.bounceBursting = 0
			self.bounceConnect = threading.Event()
			self.bounceBuffer = []
		
		def __repr__(self):
			return "[%s] %r" % (self.name, self.addr)
		
		def msg(self):
			if(self.ipHash):
				return "%s,%s" % (self.name, self.ipHash)
			else:
				return self.name
		
		def level(self):
			return int(self.name[0])
		
		def send(self, message):
			self.comLock.acquire()
			if(self.bounceEnable and not self.bounceBursting):
				self.bounceBuffer.append(message)
				# this naively buffers all messages, probably non-optimal, but simple
				while(len(self.bounceBuffer) > self.bounceBufferSize):
					self.bounceBuffer.remove(self.bounceBuffer[0])
			if(not self.bounceDisconnected.isSet() or self.bounceBursting):
				try:
					log(self, "sending: %s to %s" % (repr(message), self), 2)
					self.sock.send(message + "\r\n")
				except Exception as error:
					log(self, "send error to %s: %s" % (self, error), 2)
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
		self.HTTPServ.redirects["/ChatClient.html"] = {"header": "User-Agent", "value": "iPhone", "location": "MobileClient.html"}
		self.welcomeMessage = """
			Welcome to %(server_version)s
			Using protocol versions 0, 1 and 2
			Written by 'Nadnerb'
			There are only a few rules:
			    Don't send invalid commands. ;)
			    Language filter is currently %(censor_level)s
			    Bans are currently %(enable_bans)s
			Comments can be sent to Nadnerb@urulive.guildaxis.net
			Server commands now available, type !\\? at the beginning of a line."""
		self.welcomeParams = { \
			"server_version": ["value"], \
			"censor_level": ["disabled", "replace", "warn", "kick"], \
			"enable_bans": ["disabled", "enabled"], \
		}
		self.prefs = { \
			"server_version": "CyanChat (Py CC Server 2.1)", \
			"enable_http": 1, \
			"enable_https": 0, \
			"https_redirect": 0, \
			"https_cert": "server.crt", \
			"https_key": "server.key", \
			"enable_cc": 1, \
			"cc_port": 1812, \
			"http_port": 81, \
			"https_port": 443, \
			"welcome_file": "CCWelcome.conf", \
			"word_file": "BadWords.conf", \
			"enable_bans": 0, \
			"censor_level": 1, \
			"debug_mode": 0, \
			"use_reverse_dns": 1, \
			"enable_admin_extensions": 1, \
			"enable_protocol_extensions": 1, \
			"auth_1": "huru", \
			"auth_2": "tia", \
			"enable_bouncer": 0, \
			"bounce_buffer_size": 40, \
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
				Logger.logging = int(newPrefs[pref])
		self.prefs.update(newPrefs)
	
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
		self.readWelcome()
		self.readWordList()
		if(self.prefs["enable_cc"]):
			acceptThread = threading.Thread(None, self.acceptLoop, "acceptLoop", (self.prefs["cc_port"],))
			acceptThread.setDaemon(1)
			acceptThread.start()
		if(self.prefs["enable_http"]):
			# start the http server's thread
			HTTPServThread = threading.Thread(None, self.HTTPServ.acceptLoop, "HTTPServThread", (self.prefs["http_port"], False, None, None, self.prefs["https_port"] if self.prefs["https_redirect"] else False))
			HTTPServThread.setDaemon(1)
			HTTPServThread.start()
			HTTPWatchdogThread = threading.Thread(None, self.watchThread, "HTTPWatchdogThread", (HTTPServThread,))
			HTTPWatchdogThread.setDaemon(1)
			HTTPWatchdogThread.start()
		if(self.prefs["enable_https"]):
			# start the http server's https thread
			HTTPSServThread = threading.Thread(None, self.HTTPServ.acceptLoop, "HTTPSServThread", (self.prefs["https_port"], True, self.prefs["https_cert"], self.prefs["https_key"]))
			HTTPSServThread.setDaemon(1)
			HTTPSServThread.start()
			HTTPSWatchdogThread = threading.Thread(None, self.watchThread, "HTTPSWatchdogThread", (HTTPSServThread,))
			HTTPSWatchdogThread.setDaemon(1)
			HTTPSWatchdogThread.start()
		if(self.prefs["enable_http"] or self.prefs["enable_https"]):
			# accept websockets from the http server
			acceptThread = threading.Thread(None, self.acceptHTTP, "acceptHttpLoop", ())
			acceptThread.setDaemon(1)
			acceptThread.start()
		self.run()
	
	def watchThread(self, servThread):
		servThread.join()
		log(self, "%s terminated" % servThread.getName())
		self.quit.set() #Terminate the server if a server thread dies

	def run(self):
		while(not self.quit.isSet()):
			time.sleep(10)
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
		listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
	
	def acceptHTTP(self): #Threaded per-server
		acceptQueue = self.HTTPServ.registerProtocol("cyanchat")
		while 1:
			(sock, addr) = acceptQueue.acceptHTTPSession()
			self.addConnection(sock, addr)
	
	def cleanSock(self, connection, sockThread):
		sockThread.join()
		self.connections.remove(connection)
		log(self, "connection socket removed: %r" % (connection.addr,), 2)
	
	def sockLoop(self, connection): #Threaded per-socket
		while 1:
			try:
				line = readTo(connection.sock, '\n', ['\r'])
			except Exception as error:
				log(self, "error reading from socket on %s: %s" % (connection, error), 2)
				line = None
			if(not line or connection.status == 0):
				if(connection.bounceEnable and connection.named and connection.status != 0):
					log(self, "bounced session %s disconnected" % connection, 2)
					connection.bounceDisconnected.set()
					connection.bounceConnect.wait()
					# when the session is reconnected, bounceConnect will be set
					connection.bounceConnect.clear()
					connection.bounceDisconnected.clear()
					continue
				else:
					log(self, "lost connection to %s" % connection, 2)
					return
			#line = line.rstrip("\r\n")
			line = line.strip()
			log(self, "received: %r from %s" % (line, connection), 2) 
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
		else:
			if(self.prefs["enable_admin_extensions"]):
				self.handleExt(connection, cmd, msg)
			if(self.prefs["enable_bouncer"]):
				self.handleBounce(connection, cmd, msg)
	
	def handleExt(self, connection, cmd, msg):
		if(cmd == 12): # auth
			if(self.authDict.has_key(msg)):
				connection.authLevel = self.authDict[msg]
				connection.authKey = hex(random.randint(0, 0x7FFFFFFE))[2:]
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
				self.parseAuth()
				self.readWelcome()
				self.readWordList()
	
	def handleBounce(self, connection, cmd, msg):
		if(cmd == 100): # bounce key request
			connection.send("101|%s" % connection.bounceKey)
			connection.bounceEnable = 1
			connection.bounceBufferSize = self.prefs["bounce_buffer_size"]
		elif(cmd == 102): # bounce connect request
			bounceTarget = self.connections.findByBounceKey(msg)
			if(bounceTarget):
				if(not bounceTarget.bounceDisconnected.isSet()):
					# forcibly disconnect the client
					bounceTarget.sock.close()
					# and wait for sockLoop to notice
					bounceTarget.bounceDisconnected.wait()
				bounceTarget.sock = connection.sock
				connection.status = 0 # mark this session to be removed
				connection.sock = None # remove the sock from the original session
				bounceTarget.bounceBursting = 1
				bounceTarget.send("103|%s" % bounceTarget.name) # bounce connect accept
				for line in bounceTarget.bounceBuffer:
					bounceTarget.send(line)
				bounceTarget.send("104") # end of bounce init burst
				bounceTarget.bounceBursting = 0
				bounceTarget.bounceConnect.set() # resume the sock recv thread
			else:
				connection.send("102") # bounce connect reject
		elif(cmd == 104): # disable bounce request
			connection.bounceEnable = 0
			connection.bounceBuffer = []
	
	def handleServCmd(self, connection, msg):
		if(msg == "?"):
			self.showHelp(connection)
		elif(msg == "time"):
			self.showTime(connection)
		elif(msg == "stats"):
			self.showStats(connection)
		# extended chat commands for server administration
		elif(connection.authLevel > 1 and self.prefs["enable_admin_extensions"]):
			if(msg == "reload"):
				self.readPrefs()
			elif(msg.startswith("set ")):
				args = msg[4:].split(" ", 1)
				if(len(args) == 2):
					self.prefs[args[0]] = int(args[1]) if args[1].isdigit() else args[1]
				self.connections.sendPM(self.chatServer(2), connection, "%s=%r" % (args[0], self.prefs[args[0]]), 1)
			elif(msg.startswith("get ")):
				args = msg[4:].split(" ")
				for arg in args:
					if(self.prefs.has_key(arg)):
						self.connections.sendPM(self.chatServer(2), connection, "%s=%r" % (arg, self.prefs[arg]), 1)
			else:
				return 0
			# do these in case a relevant pref was changed
			self.parseAuth()
			self.readWelcome()
			self.readWordList()
		else:
			return 0
		return 1
	
	def showHelp(self, connection):
		commandsmessage = [
			'Server commands:', \
			'!\\stats	(displays server stats)', \
			'!\\time	(displays server current time)' \
		]
		if(connection.authLevel > 1 and self.prefs["enable_admin_extensions"]):
			commandsmessage += [ \
				'!\\reload	(reloads server config file)', \
				'!\\set <pref> <value>	(sets a pref value)', \
				'!\\get <pref>	(displays a pref value)' \
			]
		commandsmessage.reverse()
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
				fill = '*' * (match[1] - match[0])
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
