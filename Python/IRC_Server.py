from Logger import *
from Utils import *
from HTTP_Server import HTTP_Server

import threading
import socket

class IRC_Server:
	# these are ordered lists of channel-user and user mode characters
	# they represent all the modes that the server will accept for users
	# and channel users, and their mapping to sigils put in WHO replies
	# and NAMES replies. For NAMES replies, earlier chars take precedence
	# op, voice, half-op currently supported
	cuser_modes = "ohv"
	cuser_sigils = "@%+"
	# IRCop supported
	user_modes = "o"
	user_sigils = "*"
	# Global, Local, and Modeless channels
	chan_types = "#&+"
	# add-remove from list chanmodes
	# set-unset with param chanmodes
	# set with param only chanmodes
	# flag only chanmodes
	chan_modes = "b,k,,stnmi"
	network = "Nadru"

	# max name length is 9 characters
	class IRC_Message:
		def __init__(self, message):
			self.prefix = str()
			self.command = str()
			self.params = list()
			self.trail = str()
			args = message.split(' ')
			if(message.startswith(':')): 
				# the prefix, if present, indicates the origin of the message
				self.prefix = args.pop(0)[1:]
			# a command is required for all messages
			self.command = args.pop(0)
			while(len(args) > 0 and not args[0].startswith(':')):
				# command parameters
				self.params.append(args.pop(0))
			# and any characters following a ':' are trailing chars
			self.trail = ' '.join(args)[1:]

		def toString(self):
			out = str()
			if(self.prefix != ""):
				out += ":%s " % self.prefix
			out += self.command
			if(len(self.params)):
				out += " %s" % ' '.join(self.params)
			if(self.trail != ""):
				out += " :%s" % self.trail
			return out

		def __repr__(self):
			return self.toString()

	class IRC_Flags:
		# here I go, redefining the set type
		# (plus some useful functions, and alpha only)
		def __init__(self, flags=""):
			# since IRC_Flags is iterable, we 
			# can use this as a copy constructor
			self.flags = list()
			for flag in flags:
				if(flag not in self and flag.isalpha()):
					self.flags.append(flag)

		def change(self, changestring):
			if(changestring[0] == "+"):
				self.flags = (self + changestring).flags
			elif(changestring[0] == "-"):
				self.flags = (self - changestring).flags

		def hasAny(self, flags):
			for flag in flags:
				if(flag in self.flags):
					return True
			return False

		def hasAll(self, flags):
			for flag in flags:
				if(flag not in self.flags):
					return False
			return True

		def __add__(self, flags):
			out = IRC_Server.IRC_Flags(self)
			for flag in flags:
				if(flag not in out and flag.isalpha()):
					out.flags.append(flag)
			return out

		def __sub__(self, flags):
			out = IRC_Server.IRC_Flags(self)
			for flag in flags:
				if(flag in out):
					out.flags.remove(flag)
			return out

		def __repr__(self):
			return "+%s" % ''.join(self.flags)

		def __iter__(self):
			return self.flags.__iter__()

	class IRC_Connection:
		# type flags
		UNKNOWN = 0
		CLIENT = 1
		SERVER = 2

		def __init__(self, sock, addr):
			self.comLock = threading.Lock()
			self.type = self.UNKNOWN
			self.sock = sock
			self.addr = addr
			self.password = str()
			self.user = None # this is either the client or server object
			self.closed = False
			self.pendingServer = False

		
		def __repr__(self):
			if(self.user):
				return "<Connection to %s at %s>" % (self.user, self.addr[0])
			else:
				return "<Connection to %s>" % (self.addr[0])

		def send(self, message):
                        self.comLock.acquire()
                        try:
                                log(self, "sending: %s to %s" % (repr(message), self), 2)
                                self.sock.send(message + "\r\n")
                        except:
                                log(self, "send error to: %s" % self, 2)
                        self.comLock.release()

	class IRC_User:
		def __init__(self, connection, user="", hopcount = 0):
			self.username = str()
			self.hostname = str()
			args = user.split("!")
			self.nick = args[0]
			if(len(args) == 2):
				args = args[1].split("@")
				self.username = args[0]
			if(len(args) == 2):
				self.hostname = args[1]
			self.realname = str()
			self.servername = str()
			self.flags = IRC_Server.IRC_Flags()
			self.hopcount = hopcount
			# this is either the connection to the client
			# or the connection to the server the client is
			# connected to us through
			self.connection = connection
			# a list of channel objects which the user is 
			# subscribed to
			self.channels = list()
			self.here = True
			self.invites = list()

		def whoSigils(self):
			out = ['G', 'H'][self.here] # Here/Gone
			for flag in range(len(IRC_Server.user_modes)):
				if(IRC_Server.user_modes[flag] in self.flags):
					out += IRC_Server.user_sigils[flag]
			return out
		
		def fullUser(self):
			if(self.username):
				return "%s!%s@%s" % (self.nick, self.username, self.hostname)
			else:
				return self.nick

		def __repr__(self):
			return "<%s(%s)>" % (self.fullUser(), self.flags)
	
	class IRC_Server:
		def __init__(self, connection, hostname, hopcount, info):
			self.connection = connection
			self.hostname = hostname
			self.hopcount = hopcount
			self.info = info
			
		def __repr__(self):
			return "<%s>" % self.hostname
	
	class IRC_Channel:
		class Channel_User:
			def __init__(self, user):
				self.user = user
				self.flags = IRC_Server.IRC_Flags()

			def sigil(self):
				# the highest-order mode takes precedence
				for flag in range(len(IRC_Server.cuser_modes)):
					if(IRC_Server.cuser_modes[flag] in self.flags):
						return IRC_Server.cuser_sigils[flag]
				return ""

			def whoSigils(self):
				out = self.user.whoSigils()
				for flag in range(len(IRC_Server.cuser_modes)):
					if(IRC_Server.cuser_modes[flag] in self.flags):
						out += IRC_Server.cuser_sigils[flag]
				return out

			def toString(self):
				return self.sigil() + self.user.nick

			def __repr__(self):
				return "<%s(%s)>" % (self.toString(), self.flags)
			
		def __init__(self, name):
			self.name = name
			self.topic = str()
			self.flags = IRC_Server.IRC_Flags()
			self.users = list()
			self.key = ""
			self.bans = list()

		def __repr__(self):
			return "<%s(%s)>" % (self.name, self.flags)

		def addUser(self, user):
			if(self.findCUser(user.nick) == None):
				self.users.append(self.Channel_User(user))
				user.channels.append(self)
				return True
			return False

		def removeUser(self, user):
			for cuser in self.users:
				if(cuser.user == user):
					self.users.remove(cuser)
			user.channels.remove(self)

		def findCUser(self, nick):
			nick = nick.split("!")[0]
			for cuser in self.users:
				if(cuser.user.nick.lower() == nick.lower()):
					return cuser
			return None

		def broadcast(self, msg, exclude=None, localOnly=False):
			connections = list()
			for cuser in self.users:
				connection = cuser.user.connection
				if((not connection in connections) and connection != exclude and \
				(localOnly == False or connection.type == IRC_Server.IRC_Connection.CLIENT)):
					connections.append(connection)
			for connection in connections:
				connection.send(msg.toString())
	
	def __init__(self):
		self.quit = threading.Event()
		self.broadcastLock = threading.Lock()
		self.accessLock = threading.Lock()
		self.hostname = socket.gethostname()
		self.info = "I am a server"
		# prefs
		self.prefs = { \
			"irc_port": 6667, \
			"server_password": "seekrit", \
			"enable_http": 1, \
			"http_port": 6668, \
			"oper_user": "oper", \
			"oper_pass": "huru", \
		}
		self.HTTPServ = HTTP_Server()
		# irc servers need to know a lot of stuff
		self.connections = list()
		self.users = list()
		self.servers = list()
		self.channels = list()

	def findUser(self, nick):
		log(self, "Looking for %s in %s" % (nick, self.users), 4)
		nick = nick.split("!")[0]
		for user in self.users:
			if(user.nick.lower() == nick.lower()):
				log(self, "Found user %s" % user, 4)
				return user
		log(self, "Didn't find user", 4)
		return None

	def findChannel(self, name):
		log(self, "Looking for %s in %s" % (name, self.channels), 4)
		for channel in self.channels:
			if(channel.name.lower() == name.lower()):
				log(self, "Found channel %s" % channel, 4)
				return channel
		log(self, "Didn't find channel", 4)
		return None

	def findServer(self, hostname):
		for server in self.servers:
			if(server.hostname == hostname):
				return server
		return None

	def removeUser(self, user):
		# perform all the cleanup that needs to be done to get a user out of the system
		if(user in self.users):
			self.users.remove(user)
		for channel in user.channels:
			channel.removeUser(user)
		if(user.connection.type == self.IRC_Connection.CLIENT):
			user.connection.sock.close()
			user.connection.closed = True
			self.connections.remove(user.connection)

	def removeServer(self, server):
		if(server in self.servers):
			self.servers.remove(server)
		if(server == server.connection.user):
			server.connection.sock.close()
			server.connection.closed = True
			self.connections.remove(server.connection)

	def matchBan(self, user, banMask):
		banUser = self.IRC_User(None, banMask)
		if(user.nick != banUser.nick and banUser.nick != '*'):
			return False
		if(user.username != banUser.username and banUser.username != '*'):
			return False
		if(user.hostname != banUser.hostname and banUser.hostname != '*'):
			return False
		return True

	def start(self):
		acceptThread = threading.Thread(None, self.acceptLoop, "acceptLoop", (self.prefs["irc_port"],))
		acceptThread.setDaemon(1)
		acceptThread.start()
		if(self.prefs["enable_http"]):
			acceptThread = threading.Thread(None, self.acceptHTTP, "acceptHttpLoop", (self.prefs["http_port"],))
			acceptThread.setDaemon(1)
			acceptThread.start()
		self.run()

	def run(self):
		self.quit.wait()
	
	def acceptLoop(self, port=6667): #Threaded per-server
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

	def watchHTTP(self, HTTPServThread):
		HTTPServThread.join()
		log(self, "HTTP server thread terminated")
		self.quit.set() #Terminate the server if the HTTP server dies

	def acceptHTTP(self, port=81): #Threaded per-server
		acceptQueue = self.HTTPServ.registerProtocol("irc")
		HTTPServThread = threading.Thread(None, self.HTTPServ.acceptLoop, "HTTPServThread", (port,))
		HTTPServThread.setDaemon(1)
		HTTPServThread.start()
		HTTPWatchdogThread = threading.Thread(None, self.watchHTTP, "HTTPWatchdogThread", (HTTPServThread,))
		HTTPWatchdogThread.setDaemon(1)
		HTTPWatchdogThread.start()
		while 1:
			(sock, addr) = acceptQueue.acceptHTTPSession()
			self.addConnection(sock, addr)

	def addConnection(self, sock, addr):
		newConnection = self.IRC_Connection(sock, addr)
		self.connections.append(newConnection)
		# the connection will be added to the list (either server or client) by the message handler
		sockThread = threading.Thread(None, self.sockLoop, "sockLoop", (newConnection,))
		sockThread.setDaemon(1)
		sockThread.start()
		watchdogThread = threading.Thread(None, self.watchConnection, "watchdogThread", (newConnection, sockThread))
		watchdogThread.setDaemon(1)
		watchdogThread.start()
		return newConnection

	def watchConnection(self, connection, sockThread):
		sockThread.join()
		if(not connection.closed):
			# send a quit message
			if(connection.type == self.IRC_Connection.CLIENT):
				msg = self.IRC_Message("QUIT :Lost connection")
				msg.prefix = connection.user.fullUser()
				self.localBroadcast(msg, connection.user, connection)
				# this method should never attempt to send messages to the dead connection
				self.broadcast(msg, connection, self.IRC_Connection.SERVER)
				self.removeUser(connection.user)
			elif(connection.type == self.IRC_Connection.SERVER):
				for user in self.users:
					if(user.connection == connection):
						# any user which was connected to us through the lost server must quit
						msg = self.IRC_Message("QUIT :Lost in netsplit")
						msg.prefix = user.fullUser()
						self.localBroadcast(msg, user, connection)
						self.broadcast(msg, connection, self.IRC_Connection.SERVER)
						self.removeUser(user)
				for server in self.servers:
					if(server.connection == connection):
						# this removes both the lost server, and all servers behind it
						msg = self.IRC_Message("SQUIT :Lost in netsplit")
						msg.prefix = self.hostname
						msg.params = [server.hostname]
						self.broadcast(msg, connection, self.IRC_Connection.SERVER)
						self.removeServer(server)
			else:
				# that was fast :P
				connection.sock.close()
				self.connections.remove(connection)

	def sockLoop(self, connection): #Threaded per-socket
		while 1:
			line = readTo(connection.sock, "\n", ['\r'])
			if(not line):
				log(self, "lost connection to %s" % connection, 2)
				return
			line = line.strip()
			log(self, "received: %s from %s" % (repr(line), connection), 2)
			self.handleMsg(connection, self.IRC_Message(line))

	def broadcast(self, msg, excludeConn=None, connType=None):
		self.broadcastLock.acquire()
		if(type(excludeConn) != list):
			excludeConn = [excludeConn]
		for connection in self.connections:
			if(connection not in excludeConn and (connType == None or connType == connection.type)):
				connection.send(msg.toString())
		self.broadcastLock.release()

	def localBroadcast(self, msg, relUser, excludeConn=None):
		self.broadcastLock.acquire()
		localUsers = list()
		for channel in relUser.channels:
			for cuser in channel.users:
				user = cuser.user
				connection = cuser.user.connection
				if((not user in localUsers) and connection.type == self.IRC_Connection.CLIENT and connection != excludeConn):
					localUsers.append(user)
		for user in localUsers:
			user.connection.send(msg.toString())
		self.broadcastLock.release()

	def sendMOTD(self, connection):
		msg = self.IRC_Message("001 :Welcome, %s" % connection.user.nick) # WTF: Unknown reply type
		msg.params.append(connection.user.nick)
		msg.prefix = self.hostname
		connection.send(msg.toString())
		#ISUPPORT message example: CHANTYPES=#&+ PREFIX=(Naohv)$&@%+ CHANMODES=be,k,l,cimnpqstAKMNORS NETWORK=Nadru
		msg = self.IRC_Message("005 :are supported by this server") # RPL_ISUPPORT
		msg.prefix = self.hostname
		msg.params = [
			connection.user.nick,
			"CHANTYPES=%s" % (self.chan_types), \
			"PREFIX=(%s)%s" % (self.cuser_modes, self.cuser_sigils), \
			"CHANMODES=%s" % (self.chan_modes), \
			"NETWORK=%s" % (self.network), \
			"CASEMAPPING=ascii", \
		]
		connection.send(msg.toString())
		msg = self.IRC_Message("375 :- %s Message of the day -" % self.hostname) # RPL_MOTDSTART
		msg.params.append(connection.user.nick)
		msg.prefix = self.hostname
		connection.send(msg.toString())
		msg = self.IRC_Message("372 :- awesome text goes here") # RPL_MOTD
		msg.params.append(connection.user.nick)
		msg.prefix = self.hostname
		connection.send(msg.toString())
		msg = self.IRC_Message("376 :End of /MOTD command") # RPL_ENDOFMOTD
		msg.params.append(connection.user.nick)
		msg.prefix = self.hostname
		connection.send(msg.toString())
	
	def sendTopic(self, connection, channel):
		if(channel.topic):
			msg = self.IRC_Message("332") # RPL_TOPIC
			msg.trail = channel.topic
		else:
			msg = self.IRC_Message("331 :No topic is set") # RPL_NOTOPIC
		msg.prefix = self.hostname
		msg.params = [connection.user.nick, channel.name]
		connection.send(msg.toString())

	def sendNames(self, connection, channel):
		msg = self.IRC_Message("353") # RPL_NAMEREPLY
		msg.prefix = self.hostname
		#TODO: WTF is the @ for?
		msg.params = [connection.user.nick, "@", channel.name]
		isInChannel = channel.findCUser(connection.user.nick) != None
		for cuser in channel.users:
			if('i' in cuser.user.flags and not isInChannel):
				# hide +i users from users not in the channel
				continue
			msg.trail += "%s " % cuser.toString()
		msg.trail = msg.trail.rstrip()
		connection.send(msg.toString())
		msg = self.IRC_Message("366 :End of /NAMES list") # RPL_ENDOFNAMES
		msg.prefix = self.hostname
		msg.params = [connection.user.nick, channel.name]
		connection.send(msg.toString())

	def sendServerData(self, connection):
		# respond with our own PASS, SERVER combo
		passMsg = self.IRC_Message("PASS")
		passMsg.prefix = self.hostname
		passMsg.params = [self.prefs["server_password"]]
		connection.send(passMsg.toString())
		servMsg = self.IRC_Message("SERVER")
		servMsg.params = [self.hostname, "1"]
		servMsg.trail = self.info
		connection.send(servMsg.toString())
		# now we must synchronize all of our data with this new server
		for server in self.servers:
			servMsg = self.IRC_Message("SERVER")
			servMsg.params = [server.hostname, str(server.hopcount)]
			servMsg.trail = server.info
			servMsg.prefix = self.hostname
			connection.send(servMsg.toString())
		for user in self.users:
			# NICK, USER, MODE, JOIN
			userMsg = self.IRC_Message("NICK")
			userMsg.params = [user.nick, "1"]
			connection.send(userMsg.toString())
			userMsg = self.IRC_Message("USER")
			userMsg.prefix = user.nick
			userMsg.params = [user.username, user.hostname, user.servername]
			userMsg.trail = user.realname
			connection.send(userMsg.toString())
			userMsg = self.IRC_Message("MODE")
			userMsg.prefix = self.hostname
			userMsg.params = [user.nick, str(user.flags)]
			connection.send(userMsg.toString())
			userMsg = self.IRC_Message("JOIN")
			channelNames = list()
			channelKeys = list()
			channelModes = list()
			for channel in user.channels:
				if(channel.name.startswith("&")):
					# don't sync local channels
					continue
				channelNames.append(channel.name)
				channelKeys.append(channel.key)
				channelModes.append(channel.findCUser(user.nick).flags)
			userMsg.params = [','.join(channelNames), ','.join(channelKeys)]
			userMsg.prefix = user.nick
			connection.send(userMsg.toString())
			for channel in range(len(channelModes)):
				userMsg = self.IRC_Message("MODE")
				userMsg.prefix = self.hostname
				userMsg.params = [channelNames[channel], str(channelModes[channel]), user.nick]
				connection.send(userMsg.toString())
		for channel in self.channels:
			chanMsg = self.IRC_Message("MODE")
			chanMsg.prefix = self.hostname
			chanMsg.params = [channel.name, str(channel.flags)]
			connection.send(chanMsg.toString())
		

	def checkClientNick(self, connection, nick):
		if(self.findUser(nick)):
			# check that nobody's taken the nick already
			errmsg = self.IRC_Message("433 :Nickname is already in use")
			errmsg.prefix = self.hostname
			if(connection.user.nick):
				errmsg.params = [connection.user.nick, nick]
			else:
				errmsg.params = ["*", nick]
			connection.send(errmsg.toString())
			return False
		for char in IRC_Server.cuser_sigils + IRC_Server.chan_types + "!@": #need to include these symbols, as they're nick!user@host delimiters
			if char in nick:
				return False
		# nick is valid
		return True
	
	def handleMsg(self, connection, msg):
		log(self, "command: %s from %s" % (msg.command, connection), 2)
		if(msg.command == "PASS"):
			# if only all the commands were this simple :(
			connection.password = msg.params[0]
		elif(msg.command == "NICK"):
			if(connection.type == self.IRC_Connection.SERVER):
				existingUser = self.findUser(msg.params[0])
				if(existingUser):
					# Nickname collision! The remote server is trying to add a user we already know about!
					# what needs to happen: 
					# QUITs to everywhere on this side of the network (except for existing user if local)
					# KILL to existing user being killed
					# KILL to incoming user being killed
					killMsg = self.IRC_Message("KILL :Nickname collision")
					killMsg.prefix = self.hostname
					killMsg.params = [existingUser.nick]
					existingUser.connection.send(killMsg.toString())
					connection.send(killMsg.toString())
					quitMsg = self.IRC_Message("QUIT :Killed by %s (Nickname collision)" % self.hostname)
					quitMsg.prefix = existingUser.fullUser()
					self.broadcast(quitMsg, [existingUser.connection, connection], self.IRC_Connection.SERVER)
					# this came from a server so we don't need to worry about excluding it
					self.localBroadcast(quitMsg, existingUser, existingUser.connection)
					self.removeUser(existingUser)
					return
				hopcount = int(msg.params[1])
				if(msg.prefix):
					# name change
					user = self.findUser(msg.prefix)
					user.nick = msg.params[0]
				else:
					# new user
					user = self.IRC_User(connection, msg.params[0], hopcount)
					self.users.append(user)
				# increment the hopcount and forward to servers
				msg.params[1] = str(hopcount + 1)
				self.broadcast(msg, connection, self.IRC_Connection.SERVER)
				# forward the nick msg to local users who need to know
				msg.params.remove(msg.params[1])
				self.localBroadcast(msg, user)
			elif(connection.type == self.IRC_Connection.CLIENT):
				# check that the name isn't already taken and is valid
				if(not self.checkClientNick(connection, msg.params[0])):
					return
				if(connection.user.nick):
					# get this connections previous username and set it as the sender of the nick msg
					msg.prefix = connection.user.fullUser()
					connection.user.nick = msg.params[0]
					isNewUser = False
				else:
					# this is the first nick this user has recieved
					connection.user.nick = msg.params[0]
					self.sendMOTD(connection)
					isNewUser = True
				# forward the nick msg to the servers
				msg.params.append("1") # hopcount
				self.broadcast(msg, None, self.IRC_Connection.SERVER)
				if(connection.user.username and isNewUser):
					# now that we have a nick broadcast to the servers, we can send the user as well
					userMsg = self.IRC_Message("USER")
					userMsg.prefix = connection.user.nick
					userMsg.params = [connection.user.username, connection.user.hostname, connection.user.servername]
					userMsg.trail = connection.user.realname
					self.broadcast(userMsg, connection, self.IRC_Connection.SERVER)
				# now we can change the name of the user locally
				# forward the nick msg to local users who need to know
				msg.params.remove(msg.params[1])
				self.localBroadcast(msg, connection.user)
			elif(connection.type == self.IRC_Connection.UNKNOWN):
				# check that the name isn't already taken and is valid
				if(not self.checkClientNick(connection, msg.params[0])):
					return
				# now we know it's a client
				connection.type = self.IRC_Connection.CLIENT
				connection.user = self.IRC_User(connection, msg.params[0])
				self.users.append(connection.user)
				self.sendMOTD(connection)
				# broadcast new user to the network
				msg.params.append("1") # hopcount
				self.broadcast(msg, None, self.IRC_Connection.SERVER)
		elif(msg.command == "USER"):
			# if this is the first message from a connection, it's a client
			if(connection.type == self.IRC_Connection.UNKNOWN):
				connection.type = self.IRC_Connection.CLIENT
				connection.user = self.IRC_User(connection)
				self.users.append(connection.user)
			# if this comes from a server, we'll get a prefix
			if(connection.type == self.IRC_Connection.CLIENT):
				msg.prefix = connection.user.fullUser()
			user = self.findUser(msg.prefix)
			if(not user):
				return
			user.username = msg.params[0]
			if(connection.type == self.IRC_Connection.SERVER):
				user.hostname = msg.params[1] # only trust these if it comes from another server
				user.servername = msg.params[2]
			else:
				user.hostname = connection.addr[0]
				user.servername = self.hostname
			user.realname = msg.trail
			if(user.nick):
				# if the user has a nick already, we can send the user to the other servers
				userMsg = self.IRC_Message("USER")
				userMsg.prefix = user.nick
				userMsg.params = [user.username, user.hostname, user.servername]
				userMsg.trail = user.realname
				self.broadcast(userMsg, connection, self.IRC_Connection.SERVER)
		elif(msg.command == "SERVER"):
			if(self.findServer(msg.params[0])):
				# duplicate server! terminate the connection immediately
				msg = self.IRC_Message("462 :Server already known") # ERR_ALREADYREGISTERED
				msg.params = [msg.params[0]]
				msg.prefix = self.hostname
				connection.send(msg.toString())
				raise Exception("Duplicate Server")
			if(connection.type == self.IRC_Connection.UNKNOWN):
				# this is a server attempting to register with us
				if(connection.password == self.prefs["server_password"]):
					connection.type = self.IRC_Connection.SERVER
					newServer = self.IRC_Server(connection, msg.params[0], int(msg.params[1]), msg.trail)
					connection.user = newServer
					if(not connection.pendingServer):
						self.sendServerData(connection)
					# add the server to our local server collection
					self.servers.append(newServer)
				else:
					# if the server isn't authenticated, we should terminate the connection
					raise Exception("Unauthenticated server attempt")
			elif(connection.type == self.IRC_Connection.SERVER):
				# this is a server informing us of the presence of servers behind it
				self.servers.append(self.IRC_Server(connection, msg.params[0], int(msg.params[1]), msg.trail))
			elif(connection.type == self.IRC_Connection.CLIENT):
				# NO, BAD CLIENT, SPANKIES
				return
			# increment the hopcount
			msg.params[1] = str(int(msg.params[1]) + 1)
			msg.prefix = self.hostname
			# propagate this to the rest of the network
			self.broadcast(msg, connection, self.IRC_Connection.SERVER)
		elif(msg.command == "OPER"):
			# we should only recieve this message from a client
			if(not connection.type == self.IRC_Connection.CLIENT):
				return
			if(msg.params[0] == self.prefs["oper_user"] and msg.params[1] == self.prefs["oper_pass"]):
				operMsg = self.IRC_Message("MODE")
				operMsg.prefix = self.hostname
				operMsg.params = ['+o', connection.user.nick]
				self.broadcast(operMsg, None, self.IRC_Connection.SERVER)
				connection.user.flags += 'o'
				rpl = self.IRC_Message("381 :You are now an IRC operator") # RPL_YOUREOPER
			else:
				rpl = self.IRC_Message("464 :Password incorrect") # RPL_PASSWDMISMATCH
			rpl.prefix = self.hostname
			rpl.params = [connection.user.nick]
			connection.send(rpl.toString())
		elif(msg.command == "QUIT"):
			if(connection.type == self.IRC_Connection.CLIENT):
				msg.prefix = connection.user.fullUser()
			user = self.findUser(msg.prefix)
			if(not user):
				return
			# need to do this while the user still exists, so we can find links
			# but users don't recieve their own quit message
			self.localBroadcast(msg, user, connection)
			self.broadcast(msg, connection, self.IRC_Connection.SERVER)
			self.removeUser(user)
		elif(msg.command == "SQUIT"):
			if(connection.type == self.IRC_Connection.SERVER and msg.params[0] == self.hostname):
				# this message is directed at us, we must terminate the connection and send SQUITs for all servers
				# that are being split from this half of the network
				# for the moment, I'm going to be lazy and just let the watchdog do all the cleanup work
				raise Exception("Recieved SQUIT command")
			elif(connection.type == self.IRC_Connection.SERVER):
				self.removeServer(self.findServer(msg.params[0]))
			elif(connection.type == self.IRC_Connection.CLIENT):
				if('o' not in connection.user.flags):
					rpl = self.IRC_Message("481 :Permission Denied- You're not an IRC operator") # ERR_NOPRIVILEGES
					rpl.prefix = self.hostname
					rpl.params = [connection.user.nick]
					connection.send(rpl.toString())
					return
				msg.prefix = connection.user.fullUser()
			self.broadcast(msg, connection, self.IRC_Connection.SERVER)
		elif(msg.command == "JOIN"):
			if(not len(msg.params)):
				return
			chans = msg.params[0].split(",")
			if(len(msg.params) > 1):
				keys = msg.params[1].split(",")
			else:
				keys = range(len(chans))
			for i, chanName in enumerate(chans):
				if(chanName[0] not in IRC_Server.chan_types):
					continue
				channel = self.findChannel(chanName)
				if(not channel):
					channel = self.IRC_Channel(chanName)
					self.channels.append(channel)
					log(self, "Added channel %s" % channel, 2)
				msg.params[0] = channel.name
				if(connection.type == self.IRC_Connection.CLIENT):
					msg.prefix = connection.user.fullUser()
					if('i' in channel.flags and chanName not in connection.user.invites):
						# prevent an uninvited user from joining an invite-only channel
						rpl = self.IRC_Message("473 :Cannot join channel (+i)") # ERR_INVITEONLYCHAN
						rpl.prefix = self.hostname
						rpl.params = [connection.user.nick, channel.name]
						connection.send(rpl.toString())
						return
					if('k' in channel.flags and keys[i] != channel.key):
						# prevent a user from joining a +k channel without the channel key
						rpl = self.IRC_Message("475 :Cannot join channel (+k)") # ERR_BADCHANNELKEY
						rpl.prefix = self.hostname
						rpl.params = [connection.user.nick, channel.name]
						connection.send(rpl.toString())
						return
					for ban in channel.bans:
						if(self.matchBan(connection.user, ban)):
							# prevent banned users from joining the channel
							rpl = self.IRC_Message("474 :Cannot join channel (+b)") # ERR_BANNEDFROMCHAN
							rpl.prefix = self.hostname
							rpl.params = [connection.user.nick, channel.name]
							connection.send(rpl.toString())
							return
				# add the user to the channel
				user = self.findUser(msg.prefix)
				if(not (user and channel.addUser(user))):
					# if this fails (due to the user already being there) stop
					# this can happen during a nick collision resolution
					return
				# if this is the first user in the channel, make the cuser an op
				if(len(channel.users) == 1):
					channel.users[0].flags += 'o'
				channel.broadcast(msg, None, localOnly=True)
				if(not channel.name.startswith("&")):
					# don't sync local channels
					self.broadcast(msg, connection, self.IRC_Connection.SERVER)
				if(connection.type == self.IRC_Connection.CLIENT):
					# this is a local user, we must send them all the stuff (like topic, userlist)
					# first send the channel topic
					self.sendTopic(connection, channel)
					# Now send the channel userlist
					self.sendNames(connection, channel)
		elif(msg.command == "PART"):
			for chanName in msg.params[0].split(","):
				channel = self.findChannel(chanName)
				if(not channel):
					return
				msg.params[0] = chanName
				if(connection.type == self.IRC_Connection.CLIENT):
					msg.prefix = connection.user.fullUser()
				cuser = channel.findCUser(msg.prefix)
				if(cuser):
					channel.broadcast(msg, None, localOnly=True)
					if(not channel.name.startswith("&")):
						# don't sync local channels
						self.broadcast(msg, connection, self.IRC_Connection.SERVER)
					channel.removeUser(cuser.user)
		elif(msg.command == "MODE"):
			if(len(msg.params) == 1):
				# user is requesting modes
				if(msg.params[0][0] in IRC_Server.chan_types):
					chanName = msg.params[0]
					channel = self.findChannel(chanName)
					if(channel):
						# now send the channel modes
						msg = self.IRC_Message("324") # RPL_CHANNELMODEIS
						msg.params = [connection.user.nick, channel.name, str(channel.flags)]
					else:
						msg = self.IRC_Message("403 :No such channel") # ERR_NOSUCHCHANNEL
						msg.params = [connection.user.nick, chanName]
					msg.prefix = self.hostname
					connection.send(msg.toString())
				else:
					user = self.findUser(msg.params[0])
					if(not user or user != connection.user and 'o' not in connection.user.flags):
						rpl = self.IRC_Message("502 :You can't change someone else's modes") # ERR_USERSDONTMATCH
						rpl.prefix = self.hostname
						rpl.params = [connection.user.nick]
						connection.send(rpl.toString())
						return
					msg = self.IRC_Message("221") # RPL_UMODEIS
					msg.prefix = self.hostname
					msg.params = [user.nick, str(user.flags)]
					connection.send(msg.toString())
			elif(len(msg.params) > 1):
				# user is trying to change a mode
				# TODO: This performs MINIMAL VALIDATION and will accept ALL FLAGS (but only from operators)
				if(connection.type == self.IRC_Connection.CLIENT):
					msg.prefix = connection.user.fullUser()
				if(msg.params[0][0] in IRC_Server.chan_types):
					# channel mode being set
					channel = self.findChannel(msg.params[0])
					if(not channel):
						return
					if(msg.params[1] == 'b' or (msg.params[1] == '+b' and len(msg.params) == 2)):
						for ban in channel.bans:
							rpl = self.IRC_Message("367") # RPL_BANLIST
							rpl.prefix = self.hostname
							rpl.params = [connection.user.nick, channel.name, ban]
							connection.send(rpl.toString())
						rpl = self.IRC_Message("368 :End of channel ban list") # RPL_ENDOFBANLIST
						rpl.prefix = self.hostname
						rpl.params = [connection.user.nick, channel.name]
						connection.send(rpl.toString())
						return
					elif(msg.params[1] == 'e' or (msg.params[1] == '+e' and len(msg.params) == 2)):
						# TODO: request for exempt mask
						return
					elif(msg.params[1][0] not in ['+', '-']):
						# TODO: invalid, give reply
						return
					if(connection.type == self.IRC_Connection.CLIENT):
						# only need to validate client mode sets
						cuser = channel.findCUser(connection.user.nick)
						if((cuser == None or not cuser.flags.hasAny('oh')) and 'o' not in connection.user.flags):
							# can't set channel modes if you're not in the op'd in the channel and not an ircop
							rpl = self.IRC_Message("482 :You're not a channel operator") # ERR_CHANOPRIVSNEEDED
							rpl.prefix = self.hostname
							rpl.params = [connection.user.nick]
							connection.send(rpl.toString())
							return
						if('o' not in cuser.flags and 'h' in cuser.flags and self.IRC_Flags(msg.params[1]).hasAny('oh')):
							# halfops can do anything chanop-like except modify user modes above voice
							rpl = self.IRC_Message("482 :You're not a channel operator") # ERR_CHANOPRIVSNEEDED
							rpl.prefix = self.hostname
							rpl.params = [connection.user.nick]
							connection.send(rpl.toString())
							return 
					targetIndex = 2
					for flag in msg.params[1][1:]:
						if(flag in IRC_Server.cuser_modes):
							# these are channel-user modes
							if(targetIndex >= len(msg.params)):
								if(connection.type == self.IRC_Connection.CLIENT):
									rpl = self.IRC_Message("461 :Not enough parameters") # ERR_NEEDMOREPARAMS
									rpl.prefix = self.hostname
									rpl.params = [connection.user.nick]
									connection.send(rpl.toString())
								return
							cuser = channel.findCUser(msg.params[targetIndex])
							if(cuser):
								cuser.flags.change(msg.params[1][0] + flag)
							targetIndex += 1
						else:
							# everything else can be assumed to be a channel mode
							if(flag == 'k'):
								# set the channel key
								if(msg.params[1][0] == '+' and not targetIndex >= len(msg.params)):
									channel.key = msg.params[targetIndex]
								targetIndex += 1
							elif(flag == 'b'):
								if(targetIndex >= len(msg.params)):
									continue
								# add or remove bans
								if(msg.params[1][0] == '+'):
									if(msg.params[targetIndex] not in channel.bans):
										channel.bans.append(msg.params[targetIndex])
								elif(msg.params[1][0] == '-'):
									if(msg.params[targetIndex] in channel.bans):
										channel.bans.remove(msg.params[targetIndex])
								targetIndex += 1
								continue
							channel.flags.change(msg.params[1][0] + flag)
					# forward the message
					channel.broadcast(msg, localOnly=True)
					if(not channel.name.startswith("&")):
						# don't sync local channels
						self.broadcast(msg, connection, self.IRC_Connection.SERVER)
				else:
					# user mode being set
					user = self.findUser(msg.params[0])
					# user can set it's own flags as long as it doesn't try to op itself, otherwise, user must be op
					if(not user or connection.type == self.IRC_Connection.CLIENT and (user != connection.user or 'o' in msg.params[1]) and 'o' not in connection.user.flags):
						rpl = self.IRC_Message("502 :You can't change someone else's modes") # ERR_USERSDONTMATCH
						rpl.prefix = self.hostname
						rpl.params = [connection.user.nick]
						connection.send(rpl.toString())
						return
					user.flags.change(msg.params[1])
					# only the target and the server need to know about a user mode change
					user.connection.send(msg.toString())
					self.broadcast(msg, connection, self.IRC_Connection.SERVER)
		elif(msg.command == "TOPIC"):
			channel = self.findChannel(msg.params[0])
			if(msg.trail):
				channel.topic = msg.trail
				if(connection.type == self.IRC_Connection.CLIENT):
					msg.prefix = connection.user.fullUser()
					cuser = channel.findCUser(connection.user.nick)
					if(not cuser or ('t' in channel.flags and not cuser.flags.hasAny('oh'))):
						# if the channel has mode +t, then you must be a chan(op/halfop)
						rpl = self.IRC_Message("482 :You're not a channel operator") # ERR_CHANOPRIVSNEEDED
						rpl.prefix = self.hostname
						rpl.params = [connection.user.nick]
						connection.send(rpl.toString())
						return
				channel.broadcast(msg, localOnly=True)
				if(not channel.name.startswith("&")):
					# don't sync local channels
					self.broadcast(msg, connection, self.IRC_Connection.SERVER)
			else:
				# first send the channel topic
				self.sendTopic(connection, channel)
		elif(msg.command == "NAMES"):
			if(len(msg.params) > 0):
				channelNames = msg.params[0].split(",")
				for channelName in channelNames:
					channel = self.findChannel(channelName)
					# I'm assuming we don't send the end of /NAMES until we've responded to the whole command
					if(channel):
						self.sendNames(connection, channel)
			else:
				for channel in self.channels:
					# I'm assuming we don't send the end of /NAMES until we've responded to the whole command
					self.sendNames(connection, channel)
				allChannel = self.IRC_Channel("*")
				for user in self.users:
					if(len(user.channels) == 0 and 'i' not in user.flags):
						# don't show invisible users we don't know about
						# we don't use addUser() because that would add the channel to the user's channel list
						allChannel.users.append(self.IRC_Channel.Channel_User(user))
				self.sendNames(connection, allChannel)
		elif(msg.command == "LIST"):
			reply = self.IRC_Message("321 :Users  Name") # RPL_LISTSTART
			reply.params = [connection.user.nick, "Channel"]
			reply.prefix = self.hostname
			connection.send(reply.toString())
			for channel in self.channels:
				if('s' in channel.flags and not channel.findCUser(connection.user.nick) and 'o' not in connection.user.flags):
					# if a channel is +s (secret) then don't list it unless our user is in it
					# ircops can see all channels
					continue
				reply = self.IRC_Message("322") # RPL_LIST
				reply.params = [connection.user.nick, channel.name, str(len(channel.users))]
				reply.trail = channel.topic
				reply.prefix = self.hostname
				connection.send(reply.toString())
			reply = self.IRC_Message("323 :End of /LIST") # RPL_LISTEND
			reply.params = [connection.user.nick]
			reply.prefix = self.hostname
			connection.send(reply.toString())
		elif(msg.command == "INVITE"):
			if(connection.type == self.IRC_Connection.CLIENT):
				msg.prefix = connection.user.fullUser()
			target = self.findUser(msg.params[0])
			channel = self.findChannel(msg.params[1])
			if(channel):
				sender = channel.findCUser(msg.prefix)
			if(not target):
				return
			if(channel and 'i' in channel.flags and (not sender or not sender.flags.hasAny('oh'))):
				# to invite to a +i channel, you must be a chanop
				rpl = self.IRC_Message("482 :You're not a channel operator") # ERR_CHANOPRIVSNEEDED
				rpl.prefix = self.hostname
				rpl.params = [connection.user.nick]
				connection.send(rpl.toString())
				return
			target.invites.append(msg.params[1])
			# we don't really need to propagate this to every server, but just to be safe
			self.broadcast(msg, connection, self.IRC_Connection.SERVER)
			if(target.connection.type == self.IRC_Connection.CLIENT):
				target.connection.send(msg.toString())
		elif(msg.command == "KICK"):
			if(connection.type == self.IRC_Connection.CLIENT):
				msg.prefix = connection.user.fullUser()
			if(len(msg.params) < 2):
				return
			channel = self.findChannel(msg.params[0])
			kicker = channel.findCUser(msg.prefix)
			kickee = channel.findCUser(msg.params[1])
			if(not kicker or not kickee or not kicker.flags.hasAny('oh') or (kickee.flags.hasAny('oh') and not kickee.flags.hasAny('o'))):
				# halfops can't kick ops or each other, nonexistent users can't kick nonexistent users, and stuff
				rpl = self.IRC_Message("482 :You're not a channel operator") # ERR_CHANOPRIVSNEEDED
				rpl.prefix = self.hostname
				rpl.params = [connection.user.nick]
				connection.send(rpl.toString())
				return
			partMsg = self.IRC_Message("PART :Kicked by %s (%s)" % (kicker.user.nick, msg.trail))
			partMsg.prefix = kickee.user.fullUser()
			partMsg.params = [channel.name]
			channel.broadcast(partMsg, kickee.user.connection, localOnly=True)
			if(not channel.name.startswith("&")):
				# don't sync local channels
				self.broadcast(msg, kickee.user.connection, self.IRC_Connection.SERVER)
			kickee.user.connection.send(msg.toString())
			channel.removeUser(kickee.user)
		elif(msg.command == "VERSION"):
			pass
		elif(msg.command == "STATS"):
			pass
		elif(msg.command == "LINKS"):
			pass
		elif(msg.command == "TIME"):
			pass
		elif(msg.command == "CONNECT"):
			if(connection.type == self.IRC_Connection.CLIENT):
				if('o' not in connection.user.flags):
					rpl = self.IRC_Message("481 :Permission Denied- You're not an IRC operator") # ERR_NOPRIVILEGES
					rpl.prefix = self.hostname
					rpl.params = [connection.user.nick]
					connection.send(rpl.toString())
					return
				msg.prefix = connection.user.fullUser()
			if(len(msg.params) in [1, 2] or (len(msg.params) == 3 and msg.params[2] == self.hostname)):
				# this message is meant for us, we must now connect to the named server
				if(len(msg.params) == 1):
					msg.params.append("6667")
				sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				addr = (msg.params[0], int(msg.params[1]))
				sock.connect(addr)
				connection = self.addConnection(sock, addr)
				connection.pendingServer = True
				self.sendServerData(connection)
			elif(len(msg.params) == 3):
				# find the named server, and forward message toward it
				server = self.findServer(msg.params[2])
				server.connection.send(msg.toString())
		elif(msg.command == "TRACE"):
			pass
		elif(msg.command == "ADMIN"):
			pass
		elif(msg.command == "INFO"):
			pass
		elif(msg.command == "PRIVMSG"):
			if(connection.type == self.IRC_Connection.CLIENT):
				msg.prefix = connection.user.fullUser()
			for target in msg.params[0].split(","):
				# hopefully this doesn't count as modifying the iterable
				msg.params[0] = target
				if(target[0] in IRC_Server.chan_types):
					channel = self.findChannel(target)
					if(channel):
						if(connection.type == self.IRC_Connection.CLIENT):
							cuser = channel.findCUser(connection.user.nick)
							if('n' in channel.flags and not cuser):
								# +n channels cannot be msg'd by users not in the channel
								return
							if('m' in channel.flags and (not cuser or not cuser.flags.hasAny('ohv'))):
								# only voiced or better users can talk in a +m channel
								return
						channel.broadcast(msg, connection)
				else:
					user = self.findUser(target)
					if(user):
						user.connection.send(msg.toString())
		elif(msg.command == "NOTICE"):
			if(connection.type == self.IRC_Connection.CLIENT):
				msg.prefix = connection.user.fullUser()
			for target in msg.params[0].split(","):
				# hopefully this doesn't count as modifying the iterable
				msg.params[0] = target
				if(target[0] in IRC_Server.chan_types):
					channel = self.findChannel(target)
					if(channel):
						if(connection.type == self.IRC_Connection.CLIENT):
							cuser = channel.findCUser(connection.user.nick)
							if('n' in channel.flags and not cuser):
								# +n channels cannot be msg'd by users not in the channel
								return
							if('m' in channel.flags and (not cuser or not cuser.flags.hasAny('ohv'))):
								# only voiced or better users can talk in a +m channel
								return
						channel.broadcast(msg, connection)
				else:
					user = self.findUser(target)
					if(user):
						user.connection.send(msg.toString())
		elif(msg.command == "WHO"):
			# Now send the channel userlist
			if(len(msg.params) == 0):
				return
			for target in msg.params[0].split(','):
				if(target[0] in IRC_Server.chan_types):
					channel = self.findChannel(target)
					isInChannel = channel.findCUser(connection.user.nick) != None
					msg = self.IRC_Message("352") # RPL_WHOREPLY
					msg.prefix = self.hostname
					for cuser in channel.users:
						if('i' in cuser.user.flags and not isInChannel):
							# hide +i users from users not in the channel
							continue
						user = cuser.user
						msg.params = [ \
							connection.user.nick, \
							channel.name, \
							user.username, \
							user.hostname, \
							user.servername, \
							user.nick, \
							cuser.whoSigils(), \
						]
						msg.trail = "%d %s" % (user.hopcount, user.realname)
						connection.send(msg.toString())
					msg = self.IRC_Message("315 :End of /WHO list") # RPL_ENDOFWHO
					msg.prefix = self.hostname
					msg.params = [connection.user.nick, channel.name]
					connection.send(msg.toString())
				else:
					# TODO: How do you respond to a who request that's not directed at a channel
					pass
		elif(msg.command == "WHOIS"):
			pass
		elif(msg.command == "WHOWAS"):
			pass
		elif(msg.command == "KILL"):
			if(connection.type == self.IRC_Connection.CLIENT):
				if('o' not in connection.user.flags):
					rpl = self.IRC_Message("481 :Permission Denied- You're not an IRC operator") # ERR_NOPRIVILEGES
					rpl.prefix = self.hostname
					rpl.params = [connection.user.nick]
					connection.send(rpl.toString())
					return
				msg.prefix = connection.user.fullUser()
			killSender = msg.prefix.split("!")[0]
			killTarget = self.findUser(msg.params[0])
			if(killTarget):
				# send the KILL towards it's target
				killTarget.connection.send(msg.toString())
				# generate QUITs for the rest of the network to see
				killQuit = self.IRC_Message("QUIT :Killed by %s (%s)" % (killSender, msg.trail))
				killQuit.prefix = killTarget.fullUser()
				self.localBroadcast(killQuit, killTarget, killTarget.connection)
				self.broadcast(killQuit, [connection, killTarget.connection], self.IRC_Connection.SERVER)
				# remove the killed user
				self.removeUser(killTarget)
		elif(msg.command == "PING"):
			msg.prefix = self.hostname
			msg.trail = msg.params[0]
			msg.params = [self.hostname]
			msg.command = "PONG"
			connection.send(msg.toString())
		elif(msg.command == "PONG"):
			pass
		elif(msg.command == "ERROR"):
			pass
				

