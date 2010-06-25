from Logger import *
from Utils import *
from HTTP_Server import HTTP_Server

import threading
import random
import socket
import time

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
		
		def checkAuthKey(self, authKey):
			log(self, "checking authkey: %s" % authKey, 3)
			for connection in self.connections:
				if(connection.authKey != "" and connection.authKey == authKey):
					return connection.authLevel
			return 0
		
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
				logging = int(newPrefs[pref])
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
		acceptQueue = self.HTTPServ.registerProtocol("cyanchat")
		self.HTTPServThread = threading.Thread(None, self.HTTPServ.acceptLoop, "HTTPServThread", (port,))
		self.HTTPServThread.setDaemon(1)
		self.HTTPServThread.start()
		self.HTTPWatchdogThread = threading.Thread(None, self.watchHTTP, "HTTPWatchdogThread", ())
		self.HTTPWatchdogThread.setDaemon(1)
		self.HTTPWatchdogThread.start()
		while 1:
			(sock, addr) = acceptQueue.acceptHTTPSession()
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
