import collections
import threading

from Logger import log

escapeCodeStrings = { \
	'=': 'setAppKeys', \
	'>': 'setNormKeys', \
	'(B': 'setG0CharSet', \
	'(0': 'setG0CharSet', \
	')B': 'setG1CharSet', \
	')0': 'setG1CharSet', \
	'E': 'nextLine', \
	'D': 'index', \
	'M': 'reverseIndex', \
	'H': 'tabSet', \
	'7': 'saveCursor', \
	'8': 'restoreCursor', \
	'#8': 'screenAlignment', \
}

paramCmdStrings = { \
	's': 'saveCursor', \
	'u': 'restoreCursor', \
	'H': 'home', \
	'f': 'home', \
	'r': 'setScrollRegion', \
	'm': 'charAttributes', \
	'h': 'setMode', \
	'l': 'resetMode', \
	'd': 'linePosAbs', \
	'g': 'tabClear', \
	'G': 'curCharAbs', \
	'J': 'eraseOnDisplay', \
	'K': 'eraseOnLine', \
	'S': 'scrollUp', \
	'T': 'scrollDown', \
	'L': 'insertLines', \
	'M': 'removeLines', \
	'A': 'cursorUp', \
	'B': 'cursorDown', \
	'C': 'cursorFwd', \
	'D': 'cursorBack', \
	'P': 'deleteChars', \
	'@': 'addBlanks', \
	'X': 'eraseChars', \
}

DECModeCmdStrings = { \
	'h': 'setDECMode', \
	'l': 'resetDECMode', \
}

termCmdStrings = { \
	'T': 'resetTitleMode', \
	'c': 'sendDeviceAttributes2', \
	'm': 'setModifierSeqs', \
	'n': 'resetModifierSeqs', \
	'p': 'setPointerMode', \
	't': 'setTitleModeFeatures', \
}

privateMarkers = { \
	'':  paramCmdStrings, \
	'?': DECModeCmdStrings, \
	'>': termCmdStrings, \
}

class Command:
	def __init__(self, cmd, args):
		self.cmd = cmd
		self.args = args

	def __repr__(self):
		return "<command(%s) %r>" % (self.cmd, self.args)

class Parser:
	# Parser class: consumes input from a stream, and queues it for consumption by a terminal thread
	# Based on vt series parser documentation found at: http://vt100.net/emu/dec_ansi_parser
	# Currently only implements
	def __init__(self, stream):
		self.stream = stream
		self.char = ''
		self.clear()
		self.parseState = self.ground
		self.commandQueue = collections.deque()
		self.commandReady = threading.Semaphore(0)
		parseThread = threading.Thread(target=self.parseLoop, name="parseLoop", args=())
		parseThread.daemon = True
		parseThread.start()

	def rangeTest(self, ranges):
		# tests self.char against the supplied ranges
		test = ord(self.char)
		for range in ranges:
			if(len(range) == 1 and test == range[0]):
				return True
			elif(len(range) == 2 and test >= range[0] and test <= range[1]):
				return True
			elif(len(range) > 2 or len(range) < 1):
				raise Exception("invalid range")
		return False

	def missingAction(self, state):
		log(self, "state '%s' has no action for: %r (%s) in %r" % \
			(state, self.char, hex(self.char), self.debugStr))
		self.setState(self.ground)
		

	#### I/O Facilitation functions ####
		
	def getCommand(self):
		# called by whatever thread is consuming parser output
		self.commandReady.acquire()
		if(len(self.commandQueue) == 0):
			return None
		return self.commandQueue.popleft()

	def putCommand(self, command):
		# called to send a command to the parser output queue
		self.commandQueue.append(command)
		self.commandReady.release()

	def setState(self, state):
		# using this function to change state
		# allows states to have start and end event hooks
		### end hooks
		if(self.parseState == self.osc_string):
			self.osc_end()
		### start hooks
		if(state == self.escape):
			self.clear()
		elif(state == self.csi_entry):
			self.clear()
		self.parseState = state

	def parseLoop(self):
		# the main loop, started by __init__
		# consumes input from self.stream
		while True:
			# Consume the next character
			try:
				self.char = self.stream.read(1)
			except:
				self.char = ''
			if(self.char == ''):
				self.commandReady.release()
				return
			#log(self, "got char: %r" % self.char)
			self.debugStr += self.char
			# Check the 'from anywhere' directives
			if(self.char   == '\x1B'): # ESC
				self.setState(self.escape)
			elif(self.char == '\x9D'):
				self.setState(self.osc_string)
			elif(self.char == '\x9B'):
				self.setState(self.csi_entry)
			elif(self.char == '\x9C'): # ST
				self.setState(self.ground)
			elif(self.rangeTest([[0x18], [0x1A], [0x80, 0x8F], [0x91, 0x97], [0x99], [0x9A]])):
				self.execute()
				self.setState(self.ground)
			else:
				# Execute the current state
				self.parseState()

	#### Commands, to be executed from inside parser states ####

	def clear(self):
		self.oscStr = str()
		self.paramStr = str()
		self.privateMarker = str()
		# used for parse failure log messages
		self.debugStr = str()

	def execute(self):
		self.putCommand(Command('add', self.char))

	def print_act(self):
		self.putCommand(Command('add', self.char))

	def esc_dispatch(self):
		cmd = self.privateMarker + self.char
		if(cmd in escapeCodeStrings):
			self.putCommand(Command(escapeCodeStrings[cmd], None))
		elif(cmd[0] in escapeCodeStrings):
			self.putCommand(Command(escapeCodeStrings[cmd[0]], [cmd[1]]))
		else:
			log(self, 'Unrecognized ESC code: %r' % self.debugStr)

	def csi_dispatch(self):
		if(self.privateMarker in privateMarkers \
		and self.char in privateMarkers[self.privateMarker]):
			params = [int(i) for i in self.paramStr.split(';') if len(i) > 0]
			cmdName = privateMarkers[self.privateMarker][self.char]
			self.putCommand(Command(cmdName, params))
		else:
			log(self, 'Unrecognized CSI code: %r' % self.debugStr)

	def osc_end(self):
		try:
			(cmd, str) = self.oscStr.split(';', 1)
			self.putCommand(Command('OSCommand', [int(cmd), unicode(str, 'utf-8')]))
		except:
			log(self, 'Error parsing OSC string: %r' % self.debugStr)

	def osc_put(self):
		self.oscStr += self.char

	def param(self):
		self.paramStr += self.char

	def collect(self):
		self.privateMarker += self.char

	#### States, executed by parseLoop ####

	def ground(self):
		if(self.rangeTest([[0x00, 0x17], [0x19], [0x1C, 0x1F]])):
			self.execute()
		elif(self.rangeTest([[0x20, 0x7F]])):
			self.print_act()
		else:
			self.missingAction('ground')

	def escape(self):
		if(self.rangeTest([[0x00, 0x17], [0x19], [0x1C, 0x1F]])):
			self.execute()
		elif(self.char == '\x7F'):
			pass
		elif(self.rangeTest([[0x20, 0x2F]])):
			self.collect()
			self.setState(self.escape_intermediate)
		elif(self.rangeTest([[0x30, 0x4F], [0x51, 0x57], [0x59], [0x5A], [0x5C], [0x60, 0x7E]])):
			self.esc_dispatch()
			self.setState(self.ground)
		elif(self.char == '\x5B'): # [
			self.setState(self.csi_entry)
		elif(self.char == '\x5D'): # ]
			self.setState(self.osc_string)
		else:
			self.missingAction('escape')

	def escape_intermediate(self):
		if(self.rangeTest([[0x00, 0x17], [0x19], [0x1C, 0x1F]])):
			self.execute()
		elif(self.rangeTest([[0x20, 0x2F]])):
			self.collect()
		elif(self.char == '\x7F'):
			pass
		elif(self.rangeTest([[0x30, 0x7E]])):
			self.esc_dispatch()
			self.setState(self.ground)
		else:
			self.missingAction('escape_intermediate')

	def osc_string(self):
		if(self.char == '\x07'):
			# for some reason, the diagram I made this from does
			# not show osc_string ending with a BEL character
			self.osc_end()
			self.setState(self.ground)
		elif(self.rangeTest([[0x00, 0x17], [0x19], [0x1C, 0x1F]])):
			pass
		elif(self.rangeTest([[0x20, 0x7F]])):
			self.osc_put()
		else:
			self.missingAction('osc_string')

	def csi_entry(self):
		if(self.rangeTest([[0x00, 0x17], [0x19], [0x1C, 0x1F]])):
			self.execute()
		elif(self.char == '\x7F'):
			pass
		elif(self.rangeTest([[0x40, 0x7E]])):
			self.csi_dispatch()
			self.setState(self.ground)
		elif(self.rangeTest([[0x30, 0x39], [0x3B]])):
			self.param()
			self.setState(self.csi_param)
		elif(self.rangeTest([[0x3C, 0x3F]])):
			self.collect()
			self.setState(self.csi_param)
		elif(self.char == '\x3A'):
			self.setState(self.csi_ignore)
		elif(self.rangeTest([[0x20, 0x2F]])):
			self.collect()
			self.setState(self.csi_intermediate)
		else:
			self.missingAction('csi_entry')

	def csi_intermediate(self):
		if(self.rangeTest([[0x00, 0x17], [0x19], [0x1C, 0x1F]])):
			self.execute()
		elif(self.rangeTest([[0x20, 0x2F]])):
			self.collect()
		elif(self.char == '\x7F'):
			pass
		elif(self.rangeTest([[0x30, 0x3F]])):
			self.setState(self.csi_ignore)
		elif(self.rangeTest([[0x40, 0x7E]])):
			self.csi_dispatch()
			self.setState(self.ground)
		else:
			self.missingAction('csi_intermediate')

	def csi_param(self):
		if(self.rangeTest([[0x00, 0x17], [0x19], [0x1C, 0x1F]])):
			self.execute()
		elif(self.rangeTest([[0x30, 0x39], [0x3B]])):
			self.param()
		elif(self.char == '\x7F'):
			pass
		elif(self.rangeTest([[0x3A], [0x3C, 0x3F]])):
			self.setState(self.csi_ignore)
		elif(self.rangeTest([[0x20, 0x2F]])):
			self.collect()
			self.setState(self.csi_intermediate)
		elif(self.rangeTest([[0x40, 0x7E]])):
			self.csi_dispatch()
			self.setState(self.ground)
		else:
			self.missingAction('csi_param')

	def csi_ignore(self):
		if(self.rangeTest([[0x00, 0x17], [0x19], [0x1C, 0x1F]])):
			self.execute()
		elif(self.rangeTest([[0x20, 0x3F], [0x7F]])):
			pass
		elif(self.rangeTest([[0x40, 0x7E]])):
			self.setState(self.ground)
		else:
			self.missingAction('csi_ignore')

