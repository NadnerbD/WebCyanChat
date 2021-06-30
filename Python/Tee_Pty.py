import os, sys, threading, signal, tty, termios, fcntl, signal, errno, codecs

if len(sys.argv) < 2:
	print("usage: %s <command>" % sys.argv[0])
	exit()

pid, master = os.forkpty()
if pid == 0:
	os.environ['TERM'] = 'xterm'
	os.execvp(sys.argv[1], sys.argv[1:])

wstream = os.fdopen(master, 'wb')
rstream = os.fdopen(master, 'rb')

log = open('pty_log', 'a')

orig_attrs = termios.tcgetattr(sys.stdin)

def handler(sig, frame):
	sz = fcntl.ioctl(sys.stdin, termios.TIOCGWINSZ, b'\0\0\0\0\0\0\0\0')
	fcntl.ioctl(master, termios.TIOCSWINSZ, sz)
signal.signal(signal.SIGWINCH, handler)
handler(0, 0)

tty.setraw(sys.stdin.fileno()) # tell python to receive all keypresses without buffering

def readUI():
	while True:
		try:
			ui = sys.stdin.buffer.read(1)
			wstream.write(ui)
			wstream.flush()
			log.write('\033[32m%s\033[m' % codecs.escape_encode(ui)[0].decode('latin1'))
			log.flush()
		except:
			pass

def readSO():
	while True:
		try:
			so = rstream.read(1)
			sys.stdout.buffer.write(so)
			sys.stdout.buffer.flush()
			log.write('%s' % codecs.escape_encode(so)[0].decode('latin1'))
			log.flush()
		except:
			pass

t = threading.Thread(target=readSO, name='readSO', args=())
t.daemon = True
t.start()

t = threading.Thread(target=readUI, name='readUI', args=())
t.daemon = True
t.start()

running = True
while running:
	try:
		os.waitpid(pid, 0)
		running = False
	except OSError as e:
		if e.errno != errno.EINTR:
			raise
log.close()
try:
	wstream.close()
	rstream.close()
except:
	pass
termios.tcsetattr(sys.stdin, termios.TCSADRAIN, orig_attrs)
