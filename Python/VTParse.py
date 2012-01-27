from Logger import log

class ParseException(Exception):
	# Special exception for parsing errors, so that the try doesn't 
	# silence more important errors
	pass

class ReturnException(Exception):
	# this is hax, never do this
	def __init__(self, value):
		self.value = value

escapeCodeStrings = {
	'=': 'setAppKeys', \
	'>': 'setNormKeys', \
	'(': 'setG0CharSet', \
	')': 'setG1CharSet', \
	'E': 'nextLine', \
	'D': 'index', \
	'M': 'reverseIndex', \
	'#': 'screenAlignment', \
	'8': 'screenAlignment', \
}

paramCmdStrings = {
	's': 'saveCursor', \
	'u': 'restoreCursor', \
	'H': 'home', \
	'f': 'home', \
	'r': 'setScrollRegion', \
	'm': 'charAttributes', \
	'h': 'setMode', \
	'l': 'resetMode', \
	'd': 'linePosAbs', \
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

DECModeCmdStrings = {
	'h': 'setDECMode', \
	'l': 'resetDECMode', \
}

termCmdStrings = {
	'T': 'resetTitleMode', \
	'c': 'sendDeviceAttributes2', \
	'm': 'setModifierSeqs', \
	'n': 'resetModifierSeqs', \
	'p': 'setPointerMode', \
	't': 'setTitleModeFeatures', \
}

parserStates = {
	base,
	escapeCode,
	paramCmd,
	DECModeCmd,
	termCmd,
	string,
	integerList,
	integer,
}

	def getCommand(self):
		while True:
			state = getNextState()
		

class CommandParser:
	class command:
		def __init__(self, cmd, args):
			self.cmd = cmd
			self.args = args

		def __repr__(self):
			return "<command(%s) %r>" % (self.cmd, self.args)

	def __init__(self, stream):
		self.stream = stream
		# debug state
		self.lastCode = str()
		# fetch state
		self.char = str()
		self.needChar = True
		# parser state
		self.generator = self.base()
		self.callStack = []
		self.returnValue = None

	def accept(self, char):
		# in order to parse to the end of the stream without needing to fetch a
		# terminator character, a successful accept will actually leave self.char
		# untouched, but will flag it as old, to be removed during the next attempt
		# to accept a character
		if(self.needChar):
			self.getChar()
		if(self.char == char or (isinstance(char, list) and self.char in char)):
			self.needChar = True
			return True
		return False

	def consume(self):
		# this function is equivalent to an accept([all possible characters]) that
		# returns the accepted character
		if(self.needChar):
			self.getChar()
		self.needChar = True
		return self.char

	def getChar(self):
		self.char = self.stream.read(1)
		self.lastCode += self.char
		self.needChar = False
		#log(self, "read: %r" % self.char)

	def expect(self, char):
		if(not self.accept(char)):
			self.error('Expected %r' % char)

	def error(self, string):
		log(self, "Error parsing: %r (%s)" % (self.lastCode, string))
		self.consume()
		# reset the parser
		self.generator = self.base()
		self.callStack = []
		self.returnValue = None
		# escaaape
		raise ParseException
		
	def getCommand(self):
		while True:
			self.lastCode = str()
			try:
				return self.parse()
			except ParseException:
				pass

	def parse(self):
		# begin parsing
		while True:
			# passthrough all ascii control characters (except ESC)
			if(self.accept([chr(i) for i in range(0x20) if i != 0x1b])):
				return self.command('add', self.char)
			elif(self.accept('')): # EOF
				return None
			# main parse loop
			try:
				call = self.generator.next()
				if(call != None):
					self.callStack.append(self.generator)
					self.generator = call()
			except ReturnException as ret:
				self.returnValue = ret.value
				if(len(self.callStack)):
					self.generator = self.callStack.pop()
				else:
					self.generator = self.base()
					return self.returnValue

	def base(self):
		if(self.accept('\x1b')):
			yield self.escapeCode
			raise ReturnException(self.returnValue)
		else:
			# this will consume one UTF-8 character
			# in case of invalid UTF-8 input, this will modify the stream
			char = self.consume()
			charLen = 0
			while((ord(char[0]) << charLen) & 0x80):
				charLen += 1
			if(charLen > 1 and charLen <= 4):
				for i in range(charLen - 1):
					char += self.consume()
			raise ReturnException(self.command('add', unicode(char, "utf-8", errors='replace')))

	def escapeCode(self):
		if(self.accept('[')):
			yield self.paramCmd
			raise ReturnException(self.returnValue)
		elif(self.accept(']')):
			yield self.osCmd
			raise ReturnException(self.returnValue)
		elif(self.accept('=')):
			raise ReturnException(self.command('setAppKeys', None))
		elif(self.accept('>')):
			raise ReturnException(self.command('setNormKeys', None))
		elif(self.accept('(')):
			raise ReturnException(self.command('setG0CharSet', self.consume()))
		elif(self.accept(')')):
			raise ReturnException(self.command('setG1CharSet', self.consume()))
		elif(self.accept('E')):
			raise ReturnException(self.command('nextLine', None))
		elif(self.accept('D')):
			raise ReturnException(self.command('index', None))
		elif(self.accept('M')):
			raise ReturnException(self.command('reverseIndex', None))
		elif(self.accept('#') and self.accept('8')):
			raise ReturnException(self.command('screenAlignment', None))
		else:
			self.error("Unknown escape code")

	def osCmd(self):
		yield self.number
		cmd = self.returnValue
		self.expect(';')
		yield self.string
		value = self.returnValue
		raise ReturnException(self.command('OSCommand', [cmd, value]))

	def paramCmd(self):
		if(self.accept('?')):
			yield self.DECModeCmd
			raise ReturnException(self.returnValue)
		elif(self.accept('>')):
			yield self.termCmd
			raise ReturnException(self.returnValue)
		elif(self.accept('s')):
			raise ReturnException(self.command('saveCursor', None))
		elif(self.accept('u')):
			raise ReturnException(self.command('restoreCursor', None))
		yield self.numberList
		values = self.returnValue
		if(self.accept('H') or self.accept('f')):
			raise ReturnException(self.command('home', values))
		elif(self.accept('r')):
			raise ReturnException(self.command('setScrollRegion', values))
		elif(self.accept('m')):
			raise ReturnException(self.command('charAttributes', values))
		elif(self.accept('h')):
			raise ReturnException(self.command('setMode', values))
		elif(self.accept('l')):
			raise ReturnException(self.command('resetMode', values))
		elif(self.accept('d')):
			raise ReturnException(self.command('linePosAbs', values))
		elif(self.accept('G')):
			raise ReturnException(self.command('curCharAbs', values[0]))
		elif(self.accept('J')):
			raise ReturnException(self.command('eraseOnDisplay', values[0]))
		elif(self.accept('K')):
			raise ReturnException(self.command('eraseOnLine', values[0]))
		elif(self.accept('S')):
			raise ReturnException(self.command('scrollUp', values[0]))
		elif(self.accept('T')):
			raise ReturnException(self.command('scrollDown', values[0]))
		elif(self.accept('L')):
			raise ReturnException(self.command('insertLines', values[0]))
		elif(self.accept('M')):
			raise ReturnException(self.command('removeLines', values[0]))
		#ABCD - up, down, forward, back
		elif(self.accept('A')):
			raise ReturnException(self.command('cursorUp', values[0]))
		elif(self.accept('B')):
			raise ReturnException(self.command('cursorDown', values[0]))
		elif(self.accept('C')):
			raise ReturnException(self.command('cursorFwd', values[0]))
		elif(self.accept('D')):
			raise ReturnException(self.command('cursorBack', values[0]))
		elif(self.accept('P')):
			raise ReturnException(self.command('deleteChars', values[0]))
		elif(self.accept('@')):
			raise ReturnException(self.command('addBlanks', values[0]))
		elif(self.accept('X')):
			raise ReturnException(self.command('eraseChars', values[0]))
		else:
			self.error("Unknown paramCmd code")
	
	def DECModeCmd(self):
		yield self.numberList
		values = self.returnValue
		if(self.accept('h')):
			raise ReturnException(self.command('setDECMode', values))
		elif(self.accept('l')):
			raise ReturnException(self.command('resetDECMode', values))
		else:
			self.error("Unknown DEC mode command")

	def termCmd(self):
		yield self.numberList
		values = self.returnValue
		if(self.accept('T')):
			raise ReturnException(self.command('resetTitleMode', values))
		elif(self.accept('c')):
			raise ReturnException(self.command('sendDeviceAttributes2', values[0]))
		elif(self.accept('m')):
			raise ReturnException(self.command('setModifierSeqs', values))
		elif(self.accept('n')):
			raise ReturnException(self.command('resetModifierSeqs', values))
		elif(self.accept('p')):
			raise ReturnException(self.command('setPointerMode', values[0]))
		elif(self.accept('t')):
			raise ReturnException(self.command('setTitleModeFeatures', values[0]))
		else:
			self.error("Unknown termCmd")
		
	def numberList(self):
		# accepts 0 or more numbers
		yield self.number
		values = [self.returnValue]
		while(self.accept(';')):
			yield self.number
			values.append(self.returnValue)
		raise ReturnException(values)

	def number(self):
		value = str()
		while(self.accept(['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'])):
			value += self.char
			yield None
		if(len(value)):
			raise ReturnException(int(value))
		else:
			raise ReturnException(None)

	def string(self):
		value = str()
		# this does not yield to the parser state machine
		# as it's terminator is one of the passthrough characters
		while(not self.accept(['\x9c', '\x07'])):
			value += self.char
			self.consume()
		raise ReturnException(value)
