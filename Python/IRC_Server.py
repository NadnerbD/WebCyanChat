from Logger import *
from Utils import *
from HTTP_Server import HTTP_Server

import threading
import socket

class IRC_Server:
	# max name length is 9 characters
	class IRC_Message:
		def __init__(self, message):
			self.prefix = str()
			self.command = str()
			self.params = list()
			self.trail = str()
			args = message.split(' ')
			args.reverse()
			if(message.startswith(':')): 
				# the prefix, if present, indicates the origin of the message
				self.prefix = args.pop()[0:]
			# a command is required for all messages
			self.command = args.pop()
			while(len(args) > 0 and not args[-1].startswith(':')):
				# command parameters
				self.params.append(args.pop())
			# and any characters following a ':' are trailing chars
			args.reverse()
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
		def __init__(self, flagstring=""):
			self.flags = list()
			for flag in flagstring:
				if(not flag in self.flags):
					self.flags.append(flag)

		def change(self, changestring):
			for flag in changestring[1:]:
				if(changestring[0] == "+"):
					if(not flag in self.flags):
						self.flags.append(flag)
				elif(changestring[0] == "-"):
					if(flag in self.flags):	
						self.flags.remove(flag)

		def __repr__(self):
			return "+%s" % ''.join(self.flags)

		def __contains__(self, flag):
			return flag in self.flags

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
		
		def fullUser(self):
			if(self.username):
				return "%s!%s@%s" % (self.nick, self.username, self.hostname)
			else:
				return self.nick

		def __repr__(self):
			return "<%s %s>" % (self.fullUser(), self.flags)
	
	class IRC_Server:
		def __init__(self, connection, hostname, hopcount, info):
			self.connection = connection
			self.hostname = hostname
			self.hopcount = hopcount
			self.info = info
	
	class IRC_Channel:
		class Channel_User:
			def __init__(self, user):
				self.user = user
				self.flags = IRC_Server.IRC_Flags()

			def sigil(self):
				if('v' in self.flags):
					return "+"
				if('o' in self.flags):
					return "@"
				return ""

			def toString(self):
				return self.sigil() + self.user.nick

			def __repr__(self):
				return "<%s>" % self.toString()
			
		def __init__(self, name):
			self.name = name
			self.topic = str()
			self.flags = IRC_Server.IRC_Flags()
			self.users = list()

		def __repr__(self):
			return "<%s %s>" % (self.name, self.flags)

		def addUser(self, user):
			self.users.append(self.Channel_User(user))
			user.channels.append(self)

		def removeUser(self, user):
			for cuser in self.users:
				if(cuser.user == user):
					self.users.remove(cuser)
					break
			user.channels.remove(self)

		def findCUser(self, nick):
			nick = nick.split("!")[0]
			for cuser in self.users:
				if(cuser.user.nick == nick):
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
		# prefs
		self.prefs = { \
			"irc_port": 6667, \
			"server_password": "seekrit", \
		}
		# irc servers need to know a lot of stuff
		self.connections = list()
		self.users = list()
		self.servers = list()
		self.channels = list()

	def findUser(self, nick):
		log(self, "Looking for %s in %s" % (nick, self.users), 4)
		nick = nick.split("!")[0]
		for user in self.users:
			if(user.nick == nick):
				log(self, "Found user %s" % user, 4)
				return user
		log(self, "Didn't find user", 4)
		return None

	def findChannel(self, name):
		log(self, "Looking for %s in %s" % (name, self.channels), 4)
		for channel in self.channels:
			if(channel.name == name):
				log(self, "Found channel %s" % channel, 4)
				return channel
		log(self, "Didn't find channel", 4)
		return None

	def removeUser(self, user):
		# perform all the cleanup that needs to be done to get a user out of the system
		if(not user):
			return
		self.users.remove(user)
		for channel in user.channels:
			channel.removeUser(user)
		if(user.connection.type == self.IRC_Connection.CLIENT):
			user.connection.sock.close()
			user.connection.closed = True
			self.connections.remove(user.connection)

	def start(self):
		acceptThread = threading.Thread(None, self.acceptLoop, "acceptLoop", (self.prefs["irc_port"],))
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
			elif(connection.type == self.IRC_Connection.SERVER):
				for user in self.users:
					if(user.connection == connection):
						# any user which was connected to us through the lost server must quit
						msg = self.IRC_Message("QUIT :Lost in netsplit")
						msg.prefix = user.fullUser()
						self.localBroadcast(msg, user, connection)
						self.broadcast(msg, connection, self.IRC_Connection.SERVER)
						self.removeUser(user)
		# get rid of the connection and associated users (server or client)
		if(connection.type == self.IRC_Connection.CLIENT):
			self.removeUser(connection.user)
		else:
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
		for connection in self.connections:
			if(connection != excludeConn and (connType == None or connType == connection.type)):
				connection.send(msg.toString())
		self.broadcastLock.release()

	def localBroadcast(self, msg, relUser, excludeConn=None):
		localUsers = list()
		for channel in relUser.channels:
			for cuser in channel.users:
				user = cuser.user
				connection = cuser.user.connection
				if((not user in localUsers) and connection.type == self.IRC_Connection.CLIENT and connection != excludeConn):
					localUsers.append(user)
		for user in localUsers:
			user.connection.send(msg.toString())

	def sendMOTD(self, connection):
		msg = self.IRC_Message("001 :Welcome, %s" % connection.user.nick) # WTF: Unknown reply type
		msg.params.append(connection.user.nick)
		msg.prefix = self.hostname
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
	
	def handleMsg(self, connection, msg):
		log(self, "command: %s from %s" % (msg.command, connection), 2)
		if(msg.command == "PASS"):
			# if only all the commands were this simple :(
			connection.password = msg.params[0]
		elif(msg.command == "NICK"):
			if(connection.type == self.IRC_Connection.SERVER):
				user = self.findUser(msg.params[0])
				if(user):
					sender = msg.prefix
					msg.prefix = self.hostname
					msg.command = "KILL"
					msg.params = [msg.params[0]]
					# send a KILL to the server we received this from
					connection.send(msg.toString())
					# if this was a name change, we need to KILL both nicks
					if(sender):
						msg.params = [sender]
						self.broadcast(msg, connection, self.IRC_Connection.SERVER)
					# broadcast this to local clients which know about the user
					self.localBroadcast(msg)
					# get rid of the user
					self.removeUser(user)
					return
				hopcount = int(msg.params[1])
				if(msg.prefix):
					# name change
					user = self.findUser(msg.prefix)
					user.nick = msg.params[0]
				else:
					# new user
					self.users.append(self.IRC_User(connection, nick, hopcount))
				# increment the hopcount and forward to servers
				msg.params[1] = str(hopcount + 1)
				self.broadcast(msg, connection, self.IRC_Connection.SERVER)
				# forward the nick msg to local users who need to know
				msg.params.remove(msg.params[1])
				self.localBroadcast(msg, user)
			elif(connection.type == self.IRC_Connection.CLIENT):
				if(self.findUser(msg.params[0])):
					# check that nobody's taken the nick already
					errmsg = self.IRC_Message("433 :Nickname is already in use")
					errmsg.prefix = self.hostname
					#TODO: WTF is the star for?
					errmsg.params = ["*", msg.params[0]]
					connection.send(errmsg.toString())
					return
				if(connection.user.nick):
					# get this connections previous username and set it as the sender of the nick msg
					msg.prefix = connection.user.fullUser()
					connection.user.nick = msg.params[0]
				else:
					connection.user.nick = msg.params[0]
					self.sendMOTD(connection)
				# forward the nick msg to the servers
				msg.params.append("0")
				self.broadcast(msg, None, self.IRC_Connection.SERVER)
				# now we can change the name of the user locally
				# forward the nick msg to local users who need to know
				msg.params.remove(msg.params[1])
				self.localBroadcast(msg, connection.user)
			elif(connection.type == self.IRC_Connection.UNKNOWN):
				# check that the name isn't already taken
				if(self.findUser(msg.params[0])):
					# check that nobody's taken the nick already
					errmsg = self.IRC_Message("433 :Nickname is already in use")
					errmsg.prefix = self.hostname
					#TODO: WTF is the star for?
					errmsg.params = ["*", msg.params[0]]
					connection.send(errmsg.toString())
					return
				# now we know it's a client
				connection.type = self.IRC_Connection.CLIENT
				connection.user = self.IRC_User(connection, msg.params[0])
				self.users.append(connection.user)
				self.sendMOTD(connection)
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
			user.username = msg.params[0]
			if(connection.type == self.IRC_Connection.SERVER):
				user.hostname = msg.params[1] # only trust these if it comes from another server
				user.servername = msg.params[2]
			else:
				user.hostname = connection.addr[0]
				user.servername = self.hostname
			user.realname = msg.trail
			if(connection.user.nick):
				# now we can send the user to the other servers
				nickMsg = self.IRC_Message("NICK")
				nickMsg.prefix = self.hostname
				nickMsg.params = [user.nick]
				self.broadcast(nickMsg, connection, self.IRC_Connection.SERVER)
				userMsg = self.IRC_Message("USER")
				userMsg.prefix = user.nick
				userMsg.params = [user.username, user.hostname, user.servername]
				userMsg.trail = user.realname
				self.broadcast(userMsg, connection, self.IRC_Connection.SERVER)
		elif(msg.command == "SERVER"):
			if(self.findServer(msg.params[0])):
				# duplicate server! terminate the connection immediately
				raise Exception("Duplicate Server")
			if(connection.type == self.IRC_Connection.UNKNOWN):
				# this is a server attempting to register with us
				if(connection.password == self.prefs["server_password"]):
					connection.type = self.IRC_Connection.SERVER
					newServer = self.IRC_Server(connection, msg.params[0], int(msg.params[1]), msg.trail)
					self.servers.append(newServer)
					connection.user = newServer
					# TODO: now we must synchronize all of our data with this new server
			elif(connection.type == self.IRC_Connection.SERVER):
				# this is a server informing us of the presence of servers behind it
				self.servers.append(self.IRC_Server(connection, msg.params[0], int(msg.params[1]), msg.trail))
		elif(msg.command == "OPER"):
			pass
		elif(msg.command == "QUIT"):
			if(connection.type == self.IRC_Connection.CLIENT):
				msg.prefix = connection.user.fullUser()
			user = self.findUser(msg.prefix)
			# need to do this while the user still exists, so we can find links
			# but users don't recieve their own quit message
			self.localBroadcast(msg, user, connection)
			self.broadcast(msg, connection, self.IRC_Connection.SERVER)
			self.removeUser(user)
		elif(msg.command == "SQUIT"):
			pass
		elif(msg.command == "JOIN"):
			for chanName in msg.params[0].split(","):
				channel = self.findChannel(chanName)
				if(not channel):
					channel = self.IRC_Channel(chanName)
					self.channels.append(channel)
					log(self, "Added channel %s" % channel, 2)
				msg.params[0] = chanName
				if(connection.type == self.IRC_Connection.CLIENT):
					msg.prefix = connection.user.fullUser()
				channel.addUser(self.findUser(msg.prefix))
				channel.broadcast(msg, None, localOnly=True)
				self.broadcast(msg, connection, self.IRC_Connection.SERVER)
			if(connection.type == self.IRC_Connection.CLIENT):
				# this is a local user, we must send them all the stuff (like topic, userlist)
				# first send the channel topic
				self.sendTopic(connection, channel)
				# Now send the channel userlist
				msg = self.IRC_Message("353") # RPL_NAMEREPLY
				msg.prefix = self.hostname
				#TODO: WTF is the @ for?
				msg.params = [connection.user.nick, "@", channel.name]
				for cuser in channel.users:
					msg.trail += "%s " % cuser.toString()
				connection.send(msg.toString())
				msg = self.IRC_Message("366 :End of /NAMES list") # RPL_ENDOFNAMES
				msg.prefix = self.hostname
				msg.params = [connection.user.nick, channel.name]
				connection.send(msg.toString())
		elif(msg.command == "PART"):
			for chanName in msg.params[0].split(","):
				channel = self.findChannel(chanName)
				msg.params[0] = chanName
				if(connection.type == self.IRC_Connection.CLIENT):
					msg.prefix = connection.user.fullUser()
				channel.broadcast(msg, None, localOnly=True)
				self.broadcast(msg, connection, self.IRC_Connection.SERVER)
				channel.removeUser(self.findUser(msg.prefix))
		elif(msg.command == "MODE"):
			if(len(msg.params) == 1):
				# user is requesting modes
				if(msg.params[0].startswith("#") or msg.params[0].startswith("&")):
					channel = self.findChannel(msg.params[0])
					# now send the channel modes
					msg = self.IRC_Message("324") # RPL_CHANNELMODEIS
					msg.prefix = self.hostname
					msg.params = [connection.user.nick, channel.name, str(channel.flags)]
					connection.send(msg.toString())
				else:
					user = self.findUser(msg.params[0])
					msg = self.IRC_Message("221") # RPL_UMODEIS
					msg.prefix = self.hostname
					msg.params = [connection.user.nick, user.nick, str(user.flags)]
			elif(len(msg.params) > 1):
				# user is trying to change a mode
				# TODO: This performs NO VALIDATION and will accept ALL FLAGS
				if(connection.type == self.IRC_Connection.CLIENT):
					msg.prefix = connection.user.fullUser()
				if(msg.params[0].startswith("#") or msg.params[0].startswith("&")):
					# channel mode being set
					channel = self.findChannel(msg.params[0])
					targetIndex = 2
					for flag in msg.params[1][1:]:
						if(flag in ['o', 'v']):
							# these are channel-user modes
							cuser = channel.findCUser(msg.params[targetIndex])
							cuser.flags.change(msg.params[1][0] + flag)
							targetIndex += 1
						else:
							# everything else can be assumed to be a channel mode
							channel.flags.change(msg.params[1][0] + flag)
					# forward the message
					channel.broadcast(msg)
					self.broadcast(msg, connection, self.IRC_Connection.SERVER)
				else:
					# user mode being set
					user = self.finduser(msg.params[0])
					user.flags.change(msg.params[1])
					self.localBroadcast(msg, user)
					self.broadcast(msg, connection, self.IRC_Connection.SERVER)
		elif(msg.command == "TOPIC"):
			channel = self.findChannel(msg.params[0])
			if(msg.trail):
				channel.topic = msg.trail
				msg.prefix = connection.user.fullUser()
				channel.broadcast(msg)
			else:
				# first send the channel topic
				self.sendTopic(connection, channel)
		elif(msg.command == "NAMES"):
			pass
		elif(msg.command == "LIST"):
			pass
		elif(msg.command == "INVITE"):
			pass
		elif(msg.command == "KICK"):
			pass
		elif(msg.command == "VERSION"):
			pass
		elif(msg.command == "STATS"):
			pass
		elif(msg.command == "LINKS"):
			pass
		elif(msg.command == "TIME"):
			pass
		elif(msg.command == "CONNECT"):
			pass
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
				if(target.startswith("#") or target.startswith("&")):
					self.findChannel(target).broadcast(msg, connection)
				else:
					self.findUser(target).connection.send(msg.toString())
		elif(msg.command == "NOTICE"):
			if(connection.type == self.IRC_Connection.CLIENT):
				msg.prefix = connection.user.fullUser()
			for target in msg.params[0].split(","):
				# hopefully this doesn't count as modifying the iterable
				msg.params[0] = target
				if(target.startswith("#") or target.startswith("&")):
					self.findChannel(target).broadcast(msg, connection)
				else:
					self.findUser(target).connection.send(msg.toString())
		elif(msg.command == "WHO"):
			# Now send the channel userlist
			for target in msg.params[0].split(','):
				if(target.startswith("#") or target.startswith("&")):
					channel = self.findChannel(target)
					# TODO: XChat doesn't like my whoreplies
					msg = self.IRC_Message("352") # RPL_WHOREPLY
					msg.prefix = self.hostname
					for cuser in channel.users:
						user = cuser.user
						msg.params = [ \
							connection.user.nick, \
							channel.name, \
							user.username, \
							user.hostname, \
							user.servername, \
							user.nick, \
							# TODO: WTF is all this stuff about?
							['H', 'G'][0] + cuser.sigil(), \
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
			self.broadcast(msg, connection)
			user = self.findUser(msg.prefix)
			self.removeUser(user)
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
				

