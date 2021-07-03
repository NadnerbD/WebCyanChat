import sys, termios, tty, codecs
from io import BytesIO

def readToEsc(stream):
	bio = BytesIO()
	while True:
		c = stream.read(1)
		if c == b'\033':
			return bio.getvalue()
		elif c == b'':
			raise Exception
		else:
			bio.write(c)

if len(sys.argv) == 2:
	attrs = termios.tcgetattr(sys.stdin)
	tty.setraw(sys.stdin.fileno())
	inFile = open(sys.argv[1], 'rb')
	while True:
		try:
			so = readToEsc(inFile)
		except:
			termios.tcsetattr(sys.stdin, termios.TCSADRAIN, attrs)
			sys.stdout.buffer.write(b"\r\n\033[31mREACHED END OF OUTPUT\033[m\r\n")
			break
		sys.stdout.buffer.write(codecs.escape_decode(so)[0])
		sys.stdout.buffer.flush()
		# skip the user input
		readToEsc(inFile)
		inFile.read(2)
		sys.stdin.read(1)
	inFile.close()
else:
	print('usage: %s <log_file>' % sys.argv[0])
