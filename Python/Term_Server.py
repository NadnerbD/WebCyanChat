import threading
import termios
import signal
import struct
import base64
import shlex
import fcntl
import json
import time
import sys
import os

from Logger import log
from Utils import parseToDict
from HTTP_Server import HTTP_Server
from VTParse import CommandParser

class Style:
	# this object represents the font style of a single character
	# it bit-packs 4 attributes (fgColor, bgColor, bold, underline) into a one byte
	# representation
	def __init__(self, init=None):
		if(init):
			self.bold = init.bold
			self.underline = init.underline
			self.fgColor = init.fgColor
			self.bgColor = init.bgColor
			self.inverted = init.inverted
		else:
			self.bold = False
			self.underline = False
			self.fgColor = 7
			self.bgColor = 0
			self.inverted = False

	def pack(self):
		# bbbfffub
		if(not self.inverted):
			return unichr( \
				(self.bold      & 0x01)      | \
				(self.underline & 0x01) << 1 | \
				(self.fgColor   & 0x07) << 2 | \
				(self.bgColor   & 0x07) << 5   \
			)
		else:
			return unichr( \
				(self.bold      & 0x01)      | \
				(self.underline & 0x01) << 1 | \
				(self.bgColor   & 0x07) << 2 | \
				(self.fgColor   & 0x07) << 5   \
			)

	def update(self, value):
		# the update takes the form of the integer portion of the
		# 'm' character attribute command
		if(value == 0):
			self.__init__()
		elif(value == 1):
			self.bold = True
		elif(value == 4):
			self.underline = True
		elif(value == 7):
			self.inverted = True
		elif(value == 22):
			self.bold = False
		elif(value == 24):
			self.underline = False
		elif(value == 27):
			self.inverted = False
		else:
			cmd = value / 10
			num = value % 10
			if(cmd == 3):
				if(num == 9):
					self.fgColor = 7
				else:
					self.fgColor = num
			elif(cmd == 4):
				if(num == 9):
					self.bgColor = 0
				else:
					self.bgColor = num

class Buffer:
	def __init__(self, width=80, height=24):
		self.size = (width, height)
		self.len = width * height
		self.pos = 0
		self.atEnd = False
		self.chars = [' ' for i in range(self.len)]
		self.attrs = [Style() for i in range(self.len)]
		self.cdiff = dict()
		self.sdiff = dict()

	def __len__(self):
		return self.len

	def __setitem__(self, i, d):
		self.chars[i] = d[0]
		self.attrs[i] = d[1]
		self.cdiff[i] = d[0]
		self.sdiff[i] = d[1]

	def __getitem__(self, i):
		return zip(self.chars[i], self.attrs[i])

	def initMsg(self, showCursor):
		return json.dumps({ \
			"cmd": "init", \
			"data": ''.join(self.chars), \
			"styles": ''.join([x.pack() for x in self.attrs]), \
			"cur": (showCursor * self.pos) + (-1 * (not showCursor)), \
			"size": self.size \
		})

	def diffMsg(self, showCursor):
		if(len(self.cdiff) > self.len / 2):
			msg = self.initMsg(showCursor)
		else:
			msg = json.dumps({ \
				"cmd": "change", \
				"data": self.cdiff, \
				"styles": dict([(x, y.pack()) for x, y in self.sdiff.items()]), \
				"cur": (showCursor * self.pos) + (-1 * (not showCursor)) \
			})
		self.cdiff = dict()
		self.sdiff = dict()
		return msg

class Terminal:
	def __init__(self, parent, width=80, height=24):
		self.buffers = [Buffer(width, height), Buffer(width, height)]
		self.buffer = self.buffers[0]
		self.bufferIndex = 0
		# stuff which is not duplicated with buffers
		self.scrollRegion = [1, height]
		self.echo = True
		self.edit = True
		self.attrs = Style()
		self.showCursor = True
		self.autoWrap = True
		self.originMode = False
		self.savedPos = 0
		self.parent = parent
		self.updateEvent = threading.Event()
		self.lastUpdate = 0
		# this is mainly to prevent message mixing during the initial state burst
		self.bufferLock = threading.Lock()

	def swapBuffers(self):
		self.bufferIndex = not self.bufferIndex
		self.buffer = self.buffers[self.bufferIndex]

	def resize(self, nWidth, nHeight, copyData=True):
		newBuffers = [Buffer(nWidth, nHeight), Buffer(nWidth, nHeight)]
		(oWidth, oHeight) = self.buffers[0].size
		if(copyData):
			for i in range(2):
				for y in range(min(oHeight, nHeight)):
					for x in range(min(oWidth, nWidth)):
						newBuffers[i][x + y * nWidth] = self.buffers[i][x + y * oWidth]
		self.buffer = newBuffers[self.bufferIndex]
		self.buffers = newBuffers
		self.parent.resize(nWidth, nHeight)

	def getPos(self):
		if(self.originMode):
			return (self.buffer.pos % self.buffer.size[0], self.buffer.pos / self.buffer.size[0] \
				- (self.scrollRegion[0] - 1))
		else:
			return (self.buffer.pos % self.buffer.size[0], self.buffer.pos / self.buffer.size[0])

	def setPos(self, x, y):
		x = min(max(x, 0), self.buffer.size[0] - 1)
		if(self.originMode):
			y = min(max(y, 0), self.scrollRegion[1] - self.scrollRegion[0]) \
				+ self.scrollRegion[0] - 1
		else:
			y = min(max(y, 0), self.buffer.size[1] - 1)
		self.buffer.atEnd = False
		self.buffer.pos = x + y * self.buffer.size[0]

	def move(self, x, y):
		start = self.getPos()
		self.setPos(start[0] + x, start[1] + y)

	def erase(self, start, stop, setNormal=False, char=' '):
		for x in range(start, stop):
			if(setNormal):
				self.buffer[x] = (char, Style())
			else:
				self.buffer[x] = (char, Style(self.attrs))
	
	def scroll(self, value):
		# shifts the scroll region contents by value (positive shifts up, negative down)
		start = (self.scrollRegion[0] - 1) * self.buffer.size[0] 
		end = self.scrollRegion[1] * self.buffer.size[0]
		offset = -value * self.buffer.size[0]
		# shift within the scroll window area only
		self.shift(max(start, start - offset), min(end, end - offset), offset)

	def shift(self, start, end, offset):
		# shift the contents of the specified area by offset
		buffer = self.buffer[start:end]
		index = min(start + offset, start)
		while index < max(end + offset, end) and index < self.buffer.len:
			if(index < start + offset or index >= end + offset):
				self.buffer[index] = (' ', Style())
			else:
				self.buffer[index] = buffer[index - start - offset]
			index += 1

	def add(self, char):
		if(char == '\r'):
			self.buffer.pos -= self.buffer.pos % self.buffer.size[0]
			self.buffer.atEnd = False
		elif(char == '\n' or char == '\x0b' or char == '\x0c'): # LineFeed, VerticalTab, FormFeed
			if(self.buffer.pos / self.buffer.size[0] == self.scrollRegion[1] - 1):
				self.scroll(1)
			else:
				self.buffer.pos += self.buffer.size[0]
			self.buffer.atEnd = False
		elif(char == '\t'):
			self.move(8 - (self.buffer.pos % self.buffer.size[0]) % 8, 0)
		elif(char == '\x08'): # backspace
			self.buffer.pos -= 1
			self.buffer.atEnd = False
		elif(char == '\x07'):
			pass # bell
		else:
			if(self.buffer.atEnd and self.autoWrap):
				self.buffer.pos += 1
				self.buffer.atEnd = False
				if(self.buffer.pos == self.scrollRegion[1] * self.buffer.size[0]):
					self.scroll(1)
					self.buffer.pos -= self.buffer.size[0]
			if(self.buffer.pos >= self.buffer.len):
				self.buffer.pos = self.buffer.len - 1
			self.buffer[self.buffer.pos] = (char, Style(self.attrs))
			if(self.buffer.pos % self.buffer.size[0] == self.buffer.size[0] - 1 and self.buffer.atEnd == False):
				self.buffer.atEnd = True
			elif(not (self.buffer.atEnd and self.autoWrap == False)):
				self.buffer.pos += 1

	def broadcast(self, msg):
		lost = []
		for sock in self.parent.connections:
			try:
				sock.send(msg)
			except Exception as error:
				log(self, "Send error to %r, %s", (sock, error))
				lost.append(sock)
		for sock in lost:
			self.parent.connections.remove(sock)
			log(self, "Removed connection: %r" % sock)

	def handleCmd(self, cmd):
		self.bufferLock.acquire()
		reInit = False
		# do stuff
		if(cmd.cmd == "add"):
			self.add(cmd.args)
		elif(cmd.cmd == "home"):
			if(len(cmd.args) == 2):
				self.setPos(cmd.args[1] - 1, cmd.args[0] - 1)
			else:
				self.setPos(0, 0)
		elif(cmd.cmd == "saveCursor"):
			self.savedPos = self.buffer.pos
		elif(cmd.cmd == "restoreCursor"):
			self.buffer.pos = self.savedPos
		elif(cmd.cmd == "cursorFwd"):
			if(cmd.args == None):
				cmd.args = 1
			cmd.args = max(cmd.args, 1)
			self.move(cmd.args, 0)
		elif(cmd.cmd == "cursorBack"):
			if(cmd.args == None):
				cmd.args = 1
			cmd.args = max(cmd.args, 1)
			self.move(-cmd.args, 0)
		elif(cmd.cmd == "cursorUp"):
			if(cmd.args == None):
				cmd.args = 1
			self.move(0, -cmd.args)
		elif(cmd.cmd == "cursorDown"):
			if(cmd.args == None):
				cmd.args = 1
			self.move(0, cmd.args)
		elif(cmd.cmd == "linePosAbs"):
			if(len(cmd.args) == 2):
				self.setPos(cmd.args[1] - 1, cmd.args[0] - 1)
			elif(len(cmd.args) == 1):
				self.setPos(self.getPos()[0], cmd.args[0] - 1)
			else:
				self.setPos(self.getPos()[0], 0)
		elif(cmd.cmd == "curCharAbs"):
			if(cmd.args == None):
				cmd.args = 1
			self.setPos(cmd.args - 1, self.getPos()[1])
		elif(cmd.cmd == "nextLine"):
			if(self.buffer.pos / self.buffer.size[0] == self.scrollRegion[1] - 1):
				self.scroll(1)
			else:
				self.move(0, 1)
			self.buffer.pos -= self.buffer.pos % self.buffer.size[0]
		elif(cmd.cmd == "index"):
			if(self.buffer.pos / self.buffer.size[0] == self.scrollRegion[1] - 1):
				self.scroll(1)
			else:
				self.move(0, 1)
		elif(cmd.cmd == "reverseIndex"):
			if(self.buffer.pos / self.buffer.size[0] == self.scrollRegion[0] - 1):
				self.scroll(-1)
			else:
				self.move(0, -1)
		elif(cmd.cmd == "eraseOnDisplay"):
			if(cmd.args == 1): # Above
				self.erase(0, self.buffer.pos + 1)
			elif(cmd.args == 2): # All
				self.erase(0, self.buffer.len)
			else: # 0 (Default) Below
				self.erase(self.buffer.pos, self.buffer.len)
		elif(cmd.cmd == "eraseOnLine"):
			lineStart = self.getPos()[1] * self.buffer.size[0]
			if(cmd.args == 1): # Left
				self.erase(lineStart, self.buffer.pos + 1)
			elif(cmd.args == 2): # All
				self.erase(lineStart, lineStart + self.buffer.size[0])
			else: # 0 (Default) Right
				self.erase(self.buffer.pos, lineStart + self.buffer.size[0])
		elif(cmd.cmd == "scrollUp"):
			if(cmd.args == None):
				cmd.args = 1
			self.scroll(cmd.args)
		elif(cmd.cmd == "scrollDown"):
			if(cmd.args == None):
				cmd.args = 1
			self.scroll(-cmd.args)
		elif(cmd.cmd == "insertLines"):
			# adds (erases) lines at curPos and pushes (scrolls) subsequent ones down
			if(cmd.args == None):
				cmd.args = 1
			tmp = self.scrollRegion # store scroll region
			self.scrollRegion = [self.buffer.pos / self.buffer.size[0] + 1, self.scrollRegion[1]]
			self.scroll(-cmd.args)
			self.scrollRegion = tmp # restore scroll region
		elif(cmd.cmd == "removeLines"):
			# removes (erases) lines at curPos and pulls (scrolls) subsequent ones up
			if(cmd.args == None):
				cmd.args = 1
			tmp = self.scrollRegion # store scroll region
			self.scrollRegion = [self.buffer.pos / self.buffer.size[0] + 1, self.scrollRegion[1]]
			self.scroll(cmd.args)
			self.scrollRegion = tmp # restore scroll region
		elif(cmd.cmd == "deleteChars"):
			# delete n chars in the current line starting at curPos, pulling the rest back
			if(cmd.args == None):
				cmd.args = 1
			self.shift(self.buffer.pos + cmd.args, self.buffer.pos + (self.buffer.size[0] - self.buffer.pos % self.buffer.size[0]), -cmd.args)
		elif(cmd.cmd == "addBlanks"):
			# insert n blanks in the current line starting at curPos, pushing the rest forward
			if(cmd.args == None):
				cmd.args = 1
			self.shift(self.buffer.pos, self.buffer.pos + (self.buffer.size[0] - self.buffer.pos % self.buffer.size[0] - cmd.args), cmd.args)
		elif(cmd.cmd == "eraseChars"):
			if(cmd.args == None):
				cmd.args = 1
			self.erase(self.buffer.pos, self.buffer.pos + cmd.args, True)
		elif(cmd.cmd == "setScrollRegion"):
			if(cmd.args[0] == None):
				cmd.args = [1, self.buffer.size[1]]
			self.scrollRegion = cmd.args
			self.buffer.pos = 0
		elif(cmd.cmd == "resetDECMode"):
			if(3 in cmd.args):
				# switch to 80 column mode
				self.resize(80, 24, False)
				reInit = True
			if(6 in cmd.args):
				self.originMode = False
				self.setPos(0, 0)
			if(7 in cmd.args):
				self.autoWrap = False
			if(25 in cmd.args):
				self.showCursor = False
			if(1049 in cmd.args and self.bufferIndex == 1):
				self.swapBuffers()
				reInit = True
		elif(cmd.cmd == "setDECMode"):
			if(3 in cmd.args):
				# switch to 132 column mode
				self.resize(132, 24, False)
				reInit = True
			if(6 in cmd.args):
				self.originMode = True
				self.setPos(0, 0)
			if(7 in cmd.args):
				self.autoWrap = True
			if(25 in cmd.args):
				self.showCursor = True
			if(1049 in cmd.args and self.bufferIndex == 0):
				self.swapBuffers()
				# clear the alt buffer when switching to it
				self.erase(0, self.buffer.len - 1)
				self.buffer.pos = 0
				self.buffer.atEnd = False
				reInit = True
		elif(cmd.cmd == "charAttributes"):
			for arg in cmd.args:
				if(arg == None):
					arg = 0
				self.attrs.update(arg)
		elif(cmd.cmd == "screenAlignment"):
			self.erase(0, self.buffer.len, True, 'E')
		if(reInit):
			# reInit is set if we've switched buffers
			self.broadcast(self.buffer.initMsg(self.showCursor))
		else:
			self.lastUpdate += 1
			self.updateEvent.set()
		self.bufferLock.release()

	def sendInit(self, sock):	
		self.bufferLock.acquire()
		sock.send(self.buffer.initMsg(self.showCursor))
		self.bufferLock.release()

	def sendDiff(self):
		self.bufferLock.acquire()
		self.broadcast(self.buffer.diffMsg(self.showCursor))
		self.lastUpdate = 0
		self.bufferLock.release()

class Term_Server:
	def __init__(self):
		self.server = HTTP_Server()
		self.server.redirects["/"] = "console.html"
		self.server.redirects["/console.html"] = {"header": "User-Agent", "value": "iPhone", "location": "textConsole.html"}
		self.sessionQueue = self.server.registerProtocol("term")
		self.connections = list()
		self.master = None
		self.prefs = { \
			"https_port": 8080, \
			"term_proc": "/bin/bash", \
			"term_args": "", \
			"term_height": 24, \
			"term_width": 80, \
			"term_pass": "pass", \
		}

	def readPrefs(self, filename="TermServer.conf"):
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

	def resize(self, width, height):
		# winsize is 4 unsigned shorts: (ws_row, ws_col, ws_xpixel, ws_ypixel)
		winsize = struct.pack('HHHH', height, width, 0, 0)
		fcntl.ioctl(self.master, termios.TIOCSWINSZ, winsize)
		
	
	def start(self):
		# init the terminal emulator
		self.terminal = Terminal(self, self.prefs["term_width"], self.prefs["term_height"])

		(pid, self.master) = os.forkpty()
		if(pid == 0):
			# ensure that the right terminal type is set
			os.environ['TERM'] = 'xterm'
			# launch the target
			os.execv(self.prefs["term_proc"], [self.prefs["term_proc"]] + shlex.split(self.prefs["term_args"]))
		
		# set the attributes of the terminal (size, for now)
		self.resize(self.prefs["term_width"], self.prefs["term_height"])

		# open the psuedo terminal master file (this is what we read/write to)
		wstream = os.fdopen(self.master, "w")
		rstream = os.fdopen(self.master, "r")

		# start a loop to accept incoming http sessions
		a = threading.Thread(target=self.sessionLoop, name="sessionLoop", args=(wstream,))
		a.daemon = True
		a.start()

		# start a thread to read output from the shell
		o = threading.Thread(target=self.handleOutput, name="oThread", args=(rstream,))
		o.daemon = True
		o.start()

		# start the http server (using ssl)
		s = threading.Thread(target=self.server.acceptLoop, name="httpThread", args=(self.prefs["http_port"], False))
		s.daemon = True
		s.start()

		# start a thrad to push diff updates to the clients
		u = threading.Thread(target=self.updateLoop, name="updateThread", args=())
		u.daemon = True
		u.start()

		# now wait for the subprocess to terminate, and for us to flush the last of it's output
		try:
			os.waitpid(pid, 0)
		except KeyboardInterrupt:
			os.kill(pid, signal.SIGKILL)
			os.waitpid(pid, 0) # wait on the process so we don't create a zombie

	def handleOutput(self, stream):
		parser = CommandParser(stream)
		while True:
			command = parser.getCommand()
			if(command == None):
				return
			log(self, "cmd: %r" % command, 4)
			self.terminal.handleCmd(command)
			
	def handleInput(self, sock, stream, addr):
		# the first frame sent over the socket must be the password
		passwd = sock.recvFrame()
		if(passwd != self.prefs["term_pass"]):
			log(self, "Incorrect password attempt from %s: %r" % (addr, passwd))
			sock.send("{\"cmd\": \"badpass\"}")
			sock.close()
			return
		log(self, "Accepted password from (%s, %s)" % addr)
		self.terminal.sendInit(sock)
		while True:
			char = chr(int(sock.recvFrame()))
			if(char == '\r'):
				char = '\n'
			log(self, "recvd: %r" % char, 4)
			stream.write(char)
			stream.flush()

	def sessionLoop(self, stream):
		while True:
			(sock, addr) = self.sessionQueue.acceptHTTPSession()
			self.connections.append(sock)
			# start a thread to send input to the shell
			i = threading.Thread(target=self.handleInput, name="iThread", args=(sock, stream, addr))
			i.daemon = True
			i.start()

	def updateLoop(self):
		# condenses rapid updates into a single message
		while True:
			self.terminal.updateEvent.wait()
			prev = self.terminal.lastUpdate
			while True:
				time.sleep(0.001)
				if(prev != self.terminal.lastUpdate):
					prev = self.terminal.lastUpdate
				else:
					break
			self.terminal.sendDiff()
			self.terminal.updateEvent.clear()

