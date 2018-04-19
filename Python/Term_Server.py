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
import re

import Logger
log = Logger.log

from Utils import parseToDict
from HTTP_Server import HTTP_Server
from VTParse import Parser

MSG_MODES = 1
MSG_INIT = 2
MSG_DIFF = 3
MSG_TITLE = 4
DIFF_CHAR = 0
DIFF_SHIFT = 1
DIFF_NEXT_CHAR = 2
DIFF_NEXT_CHAR_NOSTYLE = 3

class Style:
	# this object represents the font style of a single character
	# it bit-packs 4 attributes (fgColor, bgColor, bold, underline) into a one byte
	# representation
	def __init__(self, init=None):
		if(init):
			self.bold = init.bold
			self.bgBold = init.bgBold
			self.italic = init.italic
			self.underline = init.underline
			self.fgColor = init.fgColor
			self.bgColor = init.bgColor
			self.inverted = init.inverted
		else:
			self.bold = False
			self.bgBold = False
			self.italic = False
			self.underline = False
			self.fgColor = 9
			self.bgColor = 9
			self.inverted = False

	def value(self):
		# bbbbffff---iiubb
		if(not self.inverted):
			return ( \
				(self.bold      & 0x01)       | \
				(self.bgBold    & 0x01) << 1  | \
				(self.underline & 0x01) << 2  | \
				(self.italic    & 0x01) << 3  | \
				(self.inverted  & 0x01) << 4  | \
				(self.fgColor   & 0x0F) << 8  | \
				(self.bgColor   & 0x0F) << 12   \
			)
		else:
			return ( \
				(self.bold      & 0x01)       | \
				(self.bgBold    & 0x01) << 1  | \
				(self.underline & 0x01) << 2  | \
				(self.italic    & 0x01) << 3  | \
				(self.inverted  & 0x01) << 4  | \
				(self.bgColor   & 0x0F) << 8  | \
				(self.fgColor   & 0x0F) << 12   \
			)

	def update(self, value):
		# the update takes the form of the integer portion of the
		# 'm' character attribute command
		if(value == 0):
			self.__init__()
		elif(value == 1):
			self.bold = True
		elif(value == 3):
			self.italic = True
		elif(value == 4):
			self.underline = True
		elif(value == 7):
			self.inverted = True
		elif(value == 22):
			self.bold = False
		elif(value == 23):
			self.italic = False
		elif(value == 24):
			self.underline = False
		elif(value == 27):
			self.inverted = False
		else:
			cmd = value / 10
			num = value % 10
			if(cmd == 3):
				self.fgColor = num
			elif(cmd == 4):
				self.bgBold = False
				self.bgColor = num
			elif(cmd == 9):
				self.bold = True
				self.fgColor = num
			elif(cmd == 10):
				self.bgBold = True
				self.bgColor = num

class Buffer:
	def __init__(self, width=80, height=24):
		self.size = (width, height)
		self.len = width * height
		self.pos = 0
		self.atEnd = False
		self.chars = [' ' for i in range(self.len)]
		self.attrs = [Style() for i in range(self.len)]
		self.changeStream = []
		self.lastChangePos = -1
		self.lastChangeStyle = 0

	def __len__(self):
		return self.len

	def __setitem__(self, i, d):
		self.chars[i] = d[0]
		self.attrs[i] = d[1]
		# byte type, int pos, short style, utf-8 data
		# log(self, repr((d[0], d[1].value())))
		if i == self.lastChangePos + 1 and d[1].value() == self.lastChangeStyle:
			self.changeStream.append(struct.pack('!B', DIFF_NEXT_CHAR_NOSTYLE) + d[0].encode('utf-8'))
		elif i == self.lastChangePos + 1:
			self.changeStream.append(struct.pack('!BH', DIFF_NEXT_CHAR, d[1].value()) + d[0].encode('utf-8'))
		else:
			self.changeStream.append(struct.pack('!BiH', DIFF_CHAR, i, d[1].value()) + d[0].encode('utf-8'))
		self.lastChangePos = i
		self.lastChangeStyle = d[1].value()

	def __getitem__(self, i):
		if type(i) == slice:
			return zip(self.chars[i], self.attrs[i])
		else:
			return (self.chars[i], self.attrs[i])

	def copy(self, src):
		oWidth, oHeight = src.size
		nWidth, nHeight = self.size
		oX = src.pos % oWidth
		oY = src.pos / oWidth
		# if we push the cursor up, scroll content with it
		scroll = max(0, oY - (nHeight - 1))
		for y in range(min(oHeight, nHeight)):
			for x in range(min(oWidth, nWidth)):
				self.chars[x + y * nWidth] = src.chars[x + (y + scroll) * oWidth]
				self.attrs[x + y * nWidth] = src.attrs[x + (y + scroll) * oWidth]
		self.pos = min(oX, nWidth - 1) + min(oY, nHeight - 1) * nWidth
		if nWidth > oWidth and src.atEnd:
			self.atEnd = False
			self.pos += 1
		elif nWidth <= oX:
			self.atEnd = True
		else:
			self.atEnd = src.atEnd

	def shift(self, start, end, offset):
		# shift the contents of the specified area by offset
		buffer = self[start:end]
		index = min(start + offset, start)
		while index < max(end + offset, end) and index < len(self):
			if(index < start + offset or index >= end + offset):
				self.chars[index] = ' '
				self.attrs[index] =  Style()
			else:
				n = buffer[index - start - offset]
				self.chars[index] = n[0]
				self.attrs[index] = n[1]
			index += 1
		# byte type, int start, int end, int offset
		# log(self, repr([start, end, offset]))
		self.changeStream.append(struct.pack('!Biii', DIFF_SHIFT, start, end, offset))

	def initMsg(self, showCursor):
		# byte type, short width, short height, int pos, [short style], [utf-8 style]
		# network stream (big endian)
		return struct.pack('!Bhhi',
			MSG_INIT,
			self.size[0],
			self.size[1],
			(showCursor * self.pos) + (-1 * (not showCursor))
		) + ''.join([struct.pack('!H', a.value()) for a in self.attrs]) + ''.join(self.chars).encode('utf-8')

	def diffMsg(self, showCursor):
		# byte type, int pos, [items]
		# log(self, repr(self.changeStream))
		msg = struct.pack('!Bi',
			MSG_DIFF, 
			(showCursor * self.pos) + (-1 * (not showCursor)), 
		) + ''.join(self.changeStream)
		self.clearDiff()
		return msg

	def clearDiff(self):
		self.changeStream = []
		self.lastChangePos = -1
		self.lastChangeStyle = 0

class Charmap:
	graphics_map = {\
		'_': u'\u2400',\
		'`': u'\u25C6',\
		'a': u'\u2592',\
		'b': u'\u2409',\
		'c': u'\u240C',\
		'd': u'\u240D',\
		'e': u'\u240A',\
		'f': u'\u00B0',\
		'g': u'\u00B1',\
		'h': u'\u2424',\
		'i': u'\u240B',\
		'j': u'\u2518',\
		'k': u'\u2510',\
		'l': u'\u250C',\
		'm': u'\u2514',\
		'n': u'\u253C',\
		'o': u'\u23BA',\
		'p': u'\u23BB',\
		'q': u'\u2500',\
		'r': u'\u23BC',\
		's': u'\u23BD',\
		't': u'\u251C',\
		'u': u'\u2524',\
		'v': u'\u2534',\
		'w': u'\u252C',\
		'x': u'\u2502',\
		'y': u'\u2264',\
		'z': u'\u2265',\
		'{': u'\u03C0',\
		'|': u'\u2260',\
		'}': u'\u00A3',\
		'~': u'\u00B7',\
	}

	def __init__(self, mode='B'):
		self.mode = mode

	def setMode(self, mode):
		self.mode = mode

	def map(self, char):
		if self.mode == 'A':
			if char == '#':
				return u'\u00A3'
		elif self.mode == '0':
			if char in Charmap.graphics_map:
				return Charmap.graphics_map[char]
		return char


# for setting default argument values
def argDefaults(srcArgs, defArgs):
	for i in range(max(len(srcArgs), len(defArgs))):
		if(len(srcArgs) <= i):
			srcArgs.append(defArgs[i])
		elif(srcArgs[i] == 0):
			srcArgs[i] = defArgs[i]

class Terminal:
	def __init__(self, parent, width=80, height=24):
		self.buffers = [Buffer(width, height), Buffer(width, height)]
		self.buffer = self.buffers[0]
		self.bufferIndex = 0
		# stuff which is not duplicated with buffers
		self.scrollRegion = [1, height]
		self.horizontalTabs = set(range(8, width, 8))
		self.echo = True
		self.edit = True
		self.attrs = Style()
		self.charmaps = [Charmap('B'), Charmap('0')]
		self.shift_out = 0
		self.showCursor = True
		self.autoWrap = True
		self.originMode = False
		self.savedPos = 0
		self.savedStyle = Style()
		self.savedShift = 0
		self.savedCharsets = ['B', '0']
		self.parent = parent
		self.updateEvent = threading.Event()
		self.appKeyMode = False # 0 is normal, 1 is application mode
		self.screenMode = False # 0 is normal, 1 is inverted
		# this is mainly to prevent message mixing during the initial state burst
		self.bufferLock = threading.Lock()

	def swapBuffers(self):
		self.bufferIndex = not self.bufferIndex
		self.buffer = self.buffers[self.bufferIndex]

	def resize(self, nWidth, nHeight, copyData=True):
		newBuffers = [Buffer(nWidth, nHeight), Buffer(nWidth, nHeight)]
		oWidth, oHeight = self.buffers[0].size
		# keep saved pos in bounds
		oX = self.savedPos % oWidth
		oY = self.savedPos / oWidth
		self.savedPos = min(oX, nWidth - 1) + min(oY, nHeight - 1) * nWidth
		# extend scroll region if it's at the bottom, and contract it if it's too large
		if nHeight > oHeight and self.scrollRegion[1] == oHeight:
			self.scrollRegion[1] = nHeight
		elif nHeight < oHeight:
			self.scrollRegion[1] = min(self.scrollRegion[1], nHeight)
		# copy data if requested
		if(copyData):
			for i in range(2):
				newBuffers[i].copy(self.buffers[i])
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
		self.buffer.shift(max(start, start - offset), min(end, end - offset), offset)

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
			hpos = self.buffer.pos % self.buffer.size[0]
			# move to the first available tab stop
			for tab in sorted(self.horizontalTabs):
				if(tab > hpos):
					self.move(tab - hpos, 0)
					return
			# if we don't encounter a tab stop, move to the right margin
			self.move(self.buffer.size[0] - 1 - hpos, 0)
		elif(char == '\x08'): # backspace
			if not self.buffer.pos % self.buffer.size[0] == 0: # don't reverse-wrap
				self.buffer.pos -= 1
				self.buffer.atEnd = False
		elif(char == '\x07'):
			pass # bell
		elif(char == '\x0E'):
			self.shift_out = 1
		elif(char == '\x0F'):
			self.shift_out = 0
		elif(ord(char) < 0x20 or char == '\x7F'):
			pass # other ascii control chars we don't understand
		else:
			if(self.buffer.atEnd and self.autoWrap):
				self.buffer.pos += 1
				self.buffer.atEnd = False
				if(self.buffer.pos == self.scrollRegion[1] * self.buffer.size[0]):
					self.scroll(1)
					self.buffer.pos -= self.buffer.size[0]
			if(self.buffer.pos >= self.buffer.len):
				self.buffer.pos = self.buffer.len - 1
			self.buffer[self.buffer.pos] = (self.charmaps[self.shift_out].map(char), Style(self.attrs))
			if(self.buffer.pos % self.buffer.size[0] == self.buffer.size[0] - 1 and self.buffer.atEnd == False):
				self.buffer.atEnd = True
			elif(not (self.buffer.atEnd and self.autoWrap == False)):
				self.buffer.pos += 1

	def broadcast(self, msg, opcode=2):
		lost = []
		for sock in self.parent.connections:
			try:
				sock.send(msg, opcode) # opcode 2 indicates binary data
			except IOError as e:
				lost.append((sock, e))
		for err in lost:
			self.parent.connections.remove(err[0])
			log(self, "Removed connection: %r (%s)" % err)

	def home(self, args):
		argDefaults(args, [0, 0])
		self.setPos(args[1] - 1, args[0] - 1)

	def tabSet(self, args):
		self.horizontalTabs.add(self.buffer.pos % self.buffer.size[0])

	def tabClear(self, args):
		hpos = self.buffer.pos % self.buffer.size[0]
		if(args[0] == 0 and hpos in self.horizontalTabs):
			self.horizontalTabs.remove(hpos)
		elif(args[0] == 3):
			self.horizontalTabs = set()

	def saveCursor(self, args):
		self.savedPos = self.buffer.pos
		self.savedStyle = Style(self.attrs)
		self.savedShift = self.shift_out
		self.savedCharsets[0] = self.charmaps[0].mode
		self.savedCharsets[1] = self.charmaps[1].mode

	def restoreCursor(self, args):
		self.buffer.pos = self.savedPos
		self.attrs = self.savedStyle
		self.shift_out = self.savedShift
		self.charmaps[0].setMode(self.savedCharsets[0])
		self.charmaps[1].setMode(self.savedCharsets[1])

	def cursorFwd(self, args):
		argDefaults(args, [1])
		self.move(args[0], 0)

	def cursorBack(self, args):
		argDefaults(args, [1])
		self.move(-args[0], 0)

	def cursorUp(self, args):
		argDefaults(args, [1])
		self.move(0, -args[0])

	def cursorDown(self, args):
		argDefaults(args, [1])
		self.move(0, args[0])

	def linePosAbs(self, args):
		if(len(args) == 2):
			self.setPos(args[1] - 1, args[0] - 1)
		elif(len(args) == 1):
			self.setPos(self.getPos()[0], args[0] - 1)
		else:
			self.setPos(self.getPos()[0], 0)

	def curCharAbs(self, args):
		argDefaults(args, [1])
		self.setPos(args[0] - 1, self.getPos()[1])

	def nextLine(self, args):
		if(self.buffer.pos / self.buffer.size[0] == self.scrollRegion[1] - 1):
			self.scroll(1)
		else:
			self.move(0, 1)
		self.buffer.pos -= self.buffer.pos % self.buffer.size[0]

	def index(self, args):
		if(self.buffer.pos / self.buffer.size[0] == self.scrollRegion[1] - 1):
			self.scroll(1)
		else:
			self.move(0, 1)

	def reverseIndex(self, args):
		if(self.buffer.pos / self.buffer.size[0] == self.scrollRegion[0] - 1):
			self.scroll(-1)
		else:
			self.move(0, -1)

	def eraseOnDisplay(self, args):
		if(args[0] == 1): # Above
			self.erase(0, self.buffer.pos + 1)
		elif(args[0] == 2): # All
			self.erase(0, self.buffer.len)
		else: # 0 (Default) Below
			self.erase(self.buffer.pos, self.buffer.len)

	def eraseOnLine(self, args):
		lineStart = self.getPos()[1] * self.buffer.size[0]
		if(args[0] == 1): # Left
			self.erase(lineStart, self.buffer.pos + 1)
		elif(args[0] == 2): # All
			self.erase(lineStart, lineStart + self.buffer.size[0])
		else: # 0 (Default) Right
			self.erase(self.buffer.pos, lineStart + self.buffer.size[0])

	def scrollUp(self, args):
		argDefaults(args, [1])
		self.scroll(args[0])

	def scrollDown(self, args):
		argDefaults(args, [1])
		self.scroll(-args[0])

	def insertLines(self, args):
		# adds (erases) lines at curPos and pushes (scrolls) subsequent ones down
		argDefaults(args, [1])
		tmp = self.scrollRegion # store scroll region
		self.scrollRegion = [self.buffer.pos / self.buffer.size[0] + 1, self.scrollRegion[1]]
		self.scroll(-args[0])
		self.scrollRegion = tmp # restore scroll region

	def removeLines(self, args):
		# removes (erases) lines at curPos and pulls (scrolls) subsequent ones up
		argDefaults(args, [1])
		tmp = self.scrollRegion # store scroll region
		self.scrollRegion = [self.buffer.pos / self.buffer.size[0] + 1, self.scrollRegion[1]]
		self.scroll(args[0])
		self.scrollRegion = tmp # restore scroll region

	def deleteChars(self, args):
		# delete n chars in the current line starting at curPos, pulling the rest back
		argDefaults(args, [1])
		self.buffer.shift(self.buffer.pos + args[0], self.buffer.pos + (self.buffer.size[0] - self.buffer.pos % self.buffer.size[0]), -args[0])

	def addBlanks(self, args):
		# insert n blanks in the current line starting at curPos, pushing the rest forward
		argDefaults(args, [1])
		self.buffer.shift(self.buffer.pos, self.buffer.pos + (self.buffer.size[0] - self.buffer.pos % self.buffer.size[0] - args[0]), args[0])

	def eraseChars(self, args):
		argDefaults(args, [1])
		self.erase(self.buffer.pos, self.buffer.pos + args[0], True)

	def setScrollRegion(self, args):
		if(len(args) != 2):
			args = [1, self.buffer.size[1]]
		self.scrollRegion = args
		self.setPos(0, 0)

	def resetDECMode(self, args):
		if(3 in args):
			# switch to 80 column mode
			self.resize(80, 24, False)
			return True
		if(5 in args):
			self.screenMode = False
			self.broadcast(self.modeMsg())
		if(6 in args):
			self.originMode = False
			self.setPos(0, 0)
		if(7 in args):
			self.autoWrap = False
		if(25 in args):
			self.showCursor = False
		if(1049 in args and self.bufferIndex == 1):
			self.swapBuffers()
			return True

	def setDECMode(self, args):
		if(3 in args):
			# switch to 132 column mode
			self.resize(132, 24, False)
			return True
		if(5 in args):
			self.screenMode = True
			self.broadcast(self.modeMsg())
		if(6 in args):
			self.originMode = True
			self.setPos(0, 0)
		if(7 in args):
			self.autoWrap = True
		if(25 in args):
			self.showCursor = True
		if(1049 in args and self.bufferIndex == 0):
			self.swapBuffers()
			# clear the alt buffer when switching to it
			self.erase(0, self.buffer.len - 1)
			self.buffer.pos = 0
			self.buffer.atEnd = False
			return True

	def setAppKeys(self, args):
		log(self, "Set Application Cursor Keys", 2)
		self.appKeyMode = True
		self.broadcast(self.modeMsg())

	def setNormKeys(self, args):
		log(self, "Set Normal Cursor Keys", 2)
		self.appKeyMode = False
		self.broadcast(self.modeMsg())

	def modeMsg(self):
		return struct.pack('!BB', MSG_MODES,
			(self.appKeyMode & 0x01)      |
			(self.screenMode & 0x01) << 1
		)

	def sendDeviceAttributes(self, args):
		log(self, "Device attribute request: %r" % args, 2)
		# Identifying as "VT100 with Advanced Video Option" as described on 
		# http://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h2-Functions-using-CSI-_-ordered-by-the-final-character_s_
		return "\033[?1;2c"

	def sendDeviceAttributes2(self, args):
		log(self, "Secondary attribute request: %r" % args, 2)
		# copying the response I observed PuTTY generate
		return "\033[>0;136;0c"

	def deviceStatusReport(self, args):
		log(self, "Device status request: %r" % args, 2)
		# see https://vt100.net/docs/vt100-ug/chapter3.html
		if(args[0] == 5): # report status
			return "\033[0n" # ready
		elif(args[0] == 6): # report cursor position
			pos = self.getPos()
			rep = (pos[1] + 1, pos[0] + 1)
			log(self, "Cursor position report: %r" % (rep,), 2)
			return "\033[%d;%dR" % rep

	def OSCommand(self, args):
		if(len(args) > 1 and args[0] == 0):
			self.broadcast(self.titleMsg(args[1].encode('utf-8', 'replace')))
		else:
			log(self, "Unknown OSCommand: %r" % args)

	def titleMsg(self, string):
		return struct.pack('B', MSG_TITLE) + string

	def charAttributes(self, args):
		if(len(args) == 0):
			self.attrs.update(0)
		for arg in args:
			self.attrs.update(arg)

	def setG0CharSet(self, args):
		self.charmaps[0].setMode(args[0])

	def setG1CharSet(self, args):
		self.charmaps[1].setMode(args[0])

	def screenAlignment(self, args):
		self.erase(0, self.buffer.len, True, 'E')

	def handleCmd(self, cmd):
		with self.bufferLock:
			resp = False
			# do stuff
			if(hasattr(self, cmd.cmd)):
				resp = getattr(self, cmd.cmd)(cmd.args)
			else:
				log(self, "Unimplemented command: %s" % cmd)
			if(resp == True):
				# resp is True if we've switched buffers
				self.buffer.clearDiff()
				self.broadcast(self.buffer.initMsg(self.showCursor))
			elif(type(resp) == str):
				# resp is set to a string if we want to talk back to the host program
				return resp
			else:
				self.updateEvent.set()

	def sendInit(self, sock):
		with self.bufferLock:
			sock.send(self.modeMsg(), 2) # opcode 2 indicates binary data
			sock.send(self.buffer.initMsg(self.showCursor), 2) # opcode 2 indicates binary data

	def sendDiff(self):
		with self.bufferLock:
			self.broadcast(self.buffer.diffMsg(self.showCursor))
			self.updateEvent.clear()

	def sendPing(self):
		with self.bufferLock:
			self.broadcast('', 9) # ping opcode

class Term_Server:
	def __init__(self):
		self.server = HTTP_Server()
		self.server.redirects["/"] = "console.html"
		self.server.registerAuthorizer(re.compile("^/(term-socket|console\.html).*$"), self.authorize)
		self.sessionQueue = self.server.registerProtocol("term", "/term-socket")
		self.connections = list()
		self.master = None
		self.prefs = { \
			"enable_http": 0, \
			"http_port": 8080, \
			"enable_https": 1, \
			"https_port": 443, \
			"term_proc": "/bin/bash", \
			"term_args": "", \
			"term_height": 24, \
			"term_width": 80, \
			"term_pass": "user:pass", \
			"https_redirect": 0, \
			"https_cert": "server.crt", \
			"https_key": "server.key", \
		}

	def readPrefs(self, filename="TermServer.conf"):
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

	def resize(self, width, height):
		# winsize is 4 unsigned shorts: (ws_row, ws_col, ws_xpixel, ws_ypixel)
		winsize = struct.pack('HHHH', height, width, 0, 0)
		fcntl.ioctl(self.master, termios.TIOCSWINSZ, winsize)

	def authorize(self, headers):
		try:
			return base64.b64decode(headers['authorization'].split(' ')[1]) == self.prefs['term_pass']
		except:
			return False
	
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
		self.wstream = os.fdopen(self.master, "w")
		self.rstream = os.fdopen(self.master, "r")

		# this is passed locally so we can shut down only threads that were started by this invocation
		shutdown = threading.Event()

		# start a loop to accept incoming http sessions
		a = threading.Thread(target=self.sessionLoop, name="sessionLoop", args=(shutdown,))
		a.daemon = True
		a.start()

		# start a thread to read output from the shell
		o = threading.Thread(target=self.handleOutput, name="oThread", args=(shutdown,))
		o.daemon = True
		o.start()

		if(self.prefs["enable_http"]):
			# start the http listener
			s = threading.Thread(target=self.server.acceptLoop, name="httpThread", kwargs={
				'port': self.prefs["http_port"],
				'useSSL': False,
				'SSLRedirect': self.prefs["https_port"] if self.prefs["https_redirect"] else False,
			})
			s.daemon = True
			s.start()

		if(self.prefs["enable_https"]):
			# start the https listener
			s = threading.Thread(target=self.server.acceptLoop, name="httpsThread", kwargs={
				'port': self.prefs["https_port"],
				'useSSL': True,
				'SSLCert': self.prefs["https_cert"],
				'SSLKey': self.prefs["https_key"],
			})
			s.daemon = True
			s.start()

		# start a thread to push diff updates to the clients
		u = threading.Thread(target=self.updateLoop, name="updateThread", args=(shutdown,))
		u.daemon = True
		u.start()

		# start a thread to ping clients
		p = threading.Thread(target=self.pingLoop, name="pingLoop", args=(shutdown,))
		p.daemon = True
		p.start()

		# now wait for the subprocess to terminate, and for us to flush the last of it's output
		try:
			os.waitpid(pid, 0)
		except KeyboardInterrupt:
			os.kill(pid, signal.SIGKILL)
			os.waitpid(pid, 0) # wait on the process so we don't create a zombie
		finally:
			#signal the worker threads to shut down
			shutdown.set()

	def handleOutput(self, shutdown):
		parser = Parser(self.rstream)
		while not shutdown.is_set():
			command = parser.getCommand()
			if(command == None):
				return
			log(self, "cmd: %r" % command, 4)
			resp = self.terminal.handleCmd(command)
			if(resp):
				self.wstream.write(resp)
				self.wstream.flush()
			
	def handleInput(self, sock, addr):
		# the first frame sent over the socket must be the password
		log(self, "Accepted term connection from %r" % (addr,))
		self.terminal.sendInit(sock)
		while True:
			try:
				frame = sock.recvFrame()
			except Exception as error:
				# if we hit an error reading from the socket, remove it and end the thread
				log(self, "Error reading from %r: %s" % (addr, error))
				self.connections.remove(sock)
				return
			if len(frame) == 0:
				log(self, "End of stream from %r" % (addr,))
				self.connections.remove(sock)
				return
			if frame[0] == 'k': # keypress
				log(self, "recvd keypress: %r" % frame[1], 4)
				self.wstream.write(frame[1])
				self.wstream.flush()
			elif frame[0] == 'r': #resize
				if len(frame) != 5:
					log(self, "Malformed resize request: %r" % frame)
				sreq = struct.unpack('!HH', frame[1:5])
				log(self, "recvd resize req: %r" % (sreq,))
				with self.terminal.bufferLock:
					self.terminal.resize(sreq[0], sreq[1]) # this will call self.resize
					self.terminal.broadcast(self.terminal.buffer.initMsg(self.terminal.showCursor))

	def sessionLoop(self, shutdown):
		while not shutdown.is_set():
			(sock, addr) = self.sessionQueue.acceptHTTPSession()
			if(shutdown.is_set()):
				# if our primary thread has terminated, put the session back and exit
				self.sessionQueue.insert((sock, addr))
				return
			self.connections.append(sock)
			# start a thread to send input to the shell
			i = threading.Thread(target=self.handleInput, name="iThread", args=(sock, addr))
			i.daemon = True
			i.start()

	def updateLoop(self, shutdown):
		while not shutdown.is_set():
			self.terminal.updateEvent.wait()
			self.terminal.sendDiff()
			time.sleep(0.001)

	def pingLoop(self, shutdown):
		while not shutdown.is_set():
			self.terminal.sendPing()
			time.sleep(30)

