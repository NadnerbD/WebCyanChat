from Logger import *
from CC_Server import CC_Server

import Skype4Py

class CC_Skype_Relay(CC_Server):
	class connectionList(CC_Server.connectionList):
		def sendUserList(self):
			log(self, "sending skype userlist", 2)
			message = "35"
			for user in self.parent.chat.Members:
				message += "|%s" % self.parent.CC_Skype_User(user).msg()
			self.broadcast(message, 1)

	class CC_Skype_User:
		def __init__(self, user):
			self.user = user

		def msg(self):
			flag = 0
			if(self.user.OnlineStatus != "OFFLINE"):
				flag = 1
			return "%d%s" % (flag, self.user.Handle.encode("utf-8"))

	def __init__(self):
		CC_Server.__init__(self)
		skypePrefs = {
			"room_id": '#mattwitkowski/$cbd88fa129f3d1f0', \
		}
		self.prefs.update(skypePrefs)
		self.skype = Skype4Py.Skype(Events=self)
		for chat in self.skype.Chats:
			if(chat.Name == self.prefs["room_id"]):
				self.chat = chat
		log(self, "listening to %s" % self.prefs["room_id"])

	def UserStatus(self, status):
		log(self, status)
	
	def MessageStatus(self, message, status):
		log(self, (status, message.ChatName, self.prefs["room_id"]))
		if((status == "SENT" or status == "RECEIVED") and message.ChatName == self.prefs["room_id"]):
			for line in message.Body.split('\n'):
				log(self, "%s: %s" % (message.Sender.Handle, line))
				self.connections.sendChat(self.CC_Skype_User(message.Sender), line.encode('utf-8'))

	def handleMsg(self, connection, cmd, msg):
		if(cmd == 30 and connection.authLevel > 0): # send chat
			log(self, "relaying chat from from %s to skype: %s" % (connection, msg[2:]), 2)
			self.chat.SendMessage(msg[2:])
			return # break here so that we don't get echo
		# messages that we don't handle get passed to the usual handler
		CC_Server.handleMsg(self, connection, cmd, msg)
