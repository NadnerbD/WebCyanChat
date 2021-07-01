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

log = open('pty_log', 'ab')

# save the original terminal settings so we can restore them on shutdown
orig_attrs = termios.tcgetattr(sys.stdin)

def handler(sig, frame):
	# get the terminal size of stdin
	sz = fcntl.ioctl(sys.stdin, termios.TIOCGWINSZ, b'\0\0\0\0\0\0\0\0')
	# and apply it to the pseudo-terminal
	fcntl.ioctl(master, termios.TIOCSWINSZ, sz)

# register a handler for signal window change (will be called when the terminal size changes)
signal.signal(signal.SIGWINCH, handler)

# initially set the window size on the child pty
handler(0, 0)

tty.setraw(sys.stdin.fileno()) # tell python to receive all keypresses without buffering

def readUI():
	while True:
		ui = sys.stdin.buffer.read(1)
		# something will have to send a byte to stdin
		if not running:
			return
		wstream.write(ui)
		wstream.flush()
		log.write(b'\033[32m%s\033[m' % codecs.escape_encode(ui)[0])
		log.flush()

def readSO():
	while True:
		try:
			so = rstream.read(1)
		except OSError: # read will error once the child closes
			return
		sys.stdout.buffer.write(so)
		sys.stdout.buffer.flush()
		log.write(b'%s' % codecs.escape_encode(so)[0])
		log.flush()

t = threading.Thread(target=readSO, name='readSO', args=())
t.daemon = True
t.start()

t = threading.Thread(target=readUI, name='readUI', args=())
t.daemon = True
t.start()

running = True
while running:
	try:
		# wait for the child application to quit
		os.waitpid(pid, 0)
		running = False
	except OSError as e:
		# EINTR means we tried to call waitpid while a system call was in progress
		# we can just retry if that is the case. Otherwise, rethrow the error
		if e.errno != errno.EINTR:
			raise e
# clean up
log.close()
# try to wake up the readUI thread
fcntl.ioctl(sys.stdin, termios.TIOCSTI, b'\n')
# restore original terminal settings
termios.tcsetattr(sys.stdin, termios.TCSADRAIN, orig_attrs)
# close the pty file handles
wstream.close()
