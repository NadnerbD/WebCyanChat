from Logger import *
from Utils import *
from CC_Server import CC_Server

class Cursive_Server(CC_Server):
	def __init__(self):
		CC_Server.__init__(self)
		self.HTTPServ.mimeTypes["ttf"] = "application/octet-stream"
		self.HTTPServ.mimeTypes["woff"] = "application/octet-stream"
		self.HTTPServ.mimeTypes["woff2"] = "application/octet-stream"
		self.HTTPServ.mimeTypes["svg"] = "application/octet-stream"
		self.HTTPServ.mimeTypes["eot"] = "application/octet-stream"
		self.HTTPServ.mimeTypes["otf"] = "application/octet-stream"
		self.HTTPServ.redirects["/"] = "CursiveClient.html"

	class connectionList(CC_Server.connectionList):
		def sendUserData(self, target):
			self.accessLock.acquire()
			log(self, "sending user data to %s" % target.msg(), 3)
			message = "200" # user data list msg
			for connection in self.connections:
				message += "|%s|%s|%s" % (connection.addr[1], connection.font, connection.avatar)
			target.send(message)
			self.accessLock.release()

		def updateUserFont(self, target, data):
			self.accessLock.acquire()
			# broadcast to all users, like sendUserList
			target.font = data
			self.broadcast("201|%s|%s" % (target.addr[1], target.font), 1)
			self.accessLock.release()
		
		def updateUserAvatar(self, target, data):
			self.accessLock.acquire()
			# broadcast to all users, like sendUserList
			target.avatar = data
			self.broadcast("202|%s|%s" % (target.addr[1], target.avatar), 1)
			self.accessLock.release()
				
	
	class CC_Connection(CC_Server.CC_Connection):
		def __init__(self, sock, addr):
			CC_Server.CC_Connection.__init__(self, sock, addr)
			self.font = "" #font is sent as data url
			self.avatar = "" #also probably a data url
	
		def msg(self):
			# we add the socket number to user data so users can be uniquely id'd easily
			if(self.ipHash):
				return "%s,%s,%s" % (self.name, self.ipHash, self.addr[1])
			else:
				return self.name
	
	def handleMsg(self, connection, cmd, msg):
		CC_Server.handleMsg(self, connection, cmd, msg)
		if(cmd == 40): # on new join we send everyone's images to the new conn
			self.connections.sendUserData(connection)
		elif(cmd == 201): # font update cmd
			self.connections.updateUserFont(connection, msg)
		elif(cmd == 202): # avatar update cmd
			self.connections.updateUserAvatar(connection, msg)

	def readPrefs(self, filename="CCServer.conf"):
		# force the censor off, it interferes with sending images
		CC_Server.readPrefs(self, filename)
		self.prefs["censor_level"] = 0
			
			
