import sys, termios, tty
from cStringIO import StringIO

def readToEsc(stream):
	sio = StringIO()
	while True:
		c = stream.read(1)
		if c == '\033':
			return sio.getvalue()
		elif c == '':
			raise Exception
		else:
			sio.write(c)

if len(sys.argv) == 2:
	attrs = termios.tcgetattr(sys.stdin)
	tty.setraw(sys.stdin.fileno())
	inFile = open(sys.argv[1], 'r')
	while True:
		try:
			so = readToEsc(inFile)
		except:
			termios.tcsetattr(sys.stdin, termios.TCSADRAIN, attrs)
			print "\r\n\033[31mREACHED END OF OUTPUT\033[m"
			break
		sys.stdout.write(so.decode('string-escape'))
		sys.stdout.flush()
		# skip the user input
		readToEsc(inFile)
		inFile.read(2)
		sys.stdin.read(1)
	inFile.close()
else:
	print 'usage: %s <log_file>' % sys.argv[0]
