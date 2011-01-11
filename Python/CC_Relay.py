from Logger import *
from Utils import *
from CC_Server import CC_Server

import socket

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
			elif(cmd in [21, 31, 70]):
				msg = msg.split('|', 1)
				msg[0] = self.replaceUsers(msg[0:1])[0]
				msg = '|'.join(msg)
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
			# TODO: for directed messages (20, 70) we can bypass the server entirely
			# this would also eliminate potential problems with shadowing and directed messages
			log(self, "forwarding %s to server" % "%d|%s" % (cmd, msg), 2)
			connection.forward("%d|%s" % (cmd, msg))
		if(cmd == 15): # logout (must be done after forward, or the above will block it)
			connection.named = 0
