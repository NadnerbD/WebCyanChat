from Logger import log
from Utils import readTo, parseToDict
from CC_Server import CC_Server

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
		self.HTTPServ.isAuthorized = self.connections.checkAuthKey
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

	def updateGridFile(self):
		gridOut = file(self.prefs["grid_filename"], 'w')
		gridOut.write('|'.join(self.tileGrid))
		gridOut.close()
