from Logger import log

class ParseException(Exception):
	# Special exception for parsing errors, so that the try doesn't 
	# silence more important errors
	pass

class CommandParser:
	class command:
		def __init__(self, cmd, args):
			self.cmd = cmd
			self.args = args

		def __repr__(self):
			return "<command(%s) %r>" % (self.cmd, self.args)

	def __init__(self, stream):
		self.stream = stream
		self.char = str()
		self.lastCode = str()
		self.needChar = True

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
		if(self.accept('\x1b')):
			return self.escapeCode()
		if(self.accept('\x00')):
			return self.command('padding', None)
		elif(self.accept('')): #EOF
			return None
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
			return self.command('add', unicode(char, "utf-8", errors='replace'))

	def escapeCode(self):
		if(self.accept('?')):
			return self.DECModeCmd()
		elif(self.accept('[')):
			return self.paramCmd()
		elif(self.accept(']')):
			return self.osCmd()
		elif(self.accept('=')):
			return self.command('setAppKeys', None)
		elif(self.accept('>')):
			return self.command('setNormKeys', None)
		elif(self.accept('(')):
			return self.command('setG0CharSet', self.consume())
		elif(self.accept(')')):
			return self.command('setG1CharSet', self.consume())
		elif(self.accept('D')):
			return self.command('index', None)
		elif(self.accept('E')):
			return self.command('newLine', None)
		elif(self.accept('M')):
			return self.command('reverseIndex', None)
		elif(self.accept('#') and self.accept('8')):
			return self.command('screenAlignment', None)
		else:
			self.error("Unknown escape code")

	def osCmd(self):
		cmd = self.number()
		self.expect(';')
		value = self.string()
		return self.command('OSCommand', [cmd, value])

	def paramCmd(self):
		if(self.accept('?')):
			return self.DECModeCmd()
		elif(self.accept('>')):
			return self.termCmd()
		elif(self.accept('s')):
			return self.command('saveCursor', None)
		elif(self.accept('u')):
			return self.command('restoreCursor', None)
		values = self.numberList()
		if(self.accept('H') or self.accept('f')):
			return self.command('home', values)
		elif(self.accept('r')):
			return self.command('setScrollRegion', values)
		elif(self.accept('m')):
			return self.command('charAttributes', values)
		elif(self.accept('h')):
			return self.command('setMode', values)
		elif(self.accept('l')):
			return self.command('resetMode', values)
		elif(self.accept('d')):
			return self.command('linePosAbs', values)
		elif(self.accept('G')):
			return self.command('curCharAbs', values[0])
		elif(self.accept('J')):
			return self.command('eraseOnDisplay', values[0])
		elif(self.accept('K')):
			return self.command('eraseOnLine', values[0])
		elif(self.accept('S')):
			return self.command('scrollUp', values[0])
		elif(self.accept('T')):
			return self.command('scrollDown', values[0])
		elif(self.accept('L')):
			return self.command('insertLines', values[0])
		elif(self.accept('M')):
			return self.command('removeLines', values[0])
		#ABCD - up, down, forward, back
		elif(self.accept('A')):
			return self.command('cursorUp', values[0])
		elif(self.accept('B')):
			return self.command('cursorDown', values[0])
		elif(self.accept('C')):
			return self.command('cursorFwd', values[0])
		elif(self.accept('D')):
			return self.command('cursorBack', values[0])
		elif(self.accept('P')):
			return self.command('deleteChars', values[0])
		elif(self.accept('@')):
			return self.command('addBlanks', values[0])
		elif(self.accept('X')):
			return self.command('eraseChars', values[0])
		else:
			self.error("Unknown paramCmd code")
	
	def DECModeCmd(self):
		values = self.numberList()
		if(self.accept('h')):
			return self.command('setDECMode', values)
		elif(self.accept('l')):
			return self.command('resetDECMode', values)
		else:
			self.error("Unknown DEC mode command")

	def termCmd(self):
		values = self.numberList()
		if(self.accept('T')):
			return self.command('resetTitleMode', values)
		elif(self.accept('c')):
			return self.command('sendDeviceAttributes2', values[0])
		elif(self.accept('m')):
			return self.command('setModifierSeqs', values)
		elif(self.accept('n')):
			return self.command('resetModifierSeqs', values)
		elif(self.accept('p')):
			return self.command('setPointerMode', values[0])
		elif(self.accept('t')):
			return self.command('setTitleModeFeatures', values[0])
		else:
			self.error("Unknown termCmd")
		
	def numberList(self):
		# accepts 0 or more numbers
		values = [self.number()]
		while(self.accept(';')):
			values.append(self.number())
		return values

	def number(self):
		value = str()
		while(self.accept(['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'])):
			value += self.char
		if(len(value)):
			return int(value)
		else:
			return None

	def string(self):
		value = str()
		while(not self.accept(['\x9c', '\x07'])):
			value += self.char
			self.consume()
		return value
