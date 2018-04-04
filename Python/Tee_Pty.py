import os, sys, threading, signal, tty, termios

pid, master = os.forkpty()
if pid == 0:
	os.environ['TERM'] = 'xterm'
	os.execv('/bin/bash', ['/bin/bash'])

wstream = os.fdopen(master, 'w')
rstream = os.fdopen(master, 'r')

log = open('pty_log', 'a')

tty.setraw(sys.stdin.fileno()) # tell python to receive all keypresses without buffering

def readUI():
	while True:
		try:
			ui = sys.stdin.read(1)
			wstream.write(ui)
			wstream.flush()
			log.write('UI> %r\n' % ui)
			log.flush()
		except:
			pass

def readSO():
	while True:
		try:
			so = rstream.read(1)
			sys.stdout.write(so)
			sys.stdout.flush()
			log.write('SO> %r\n' % so)
			log.flush()
		except:
			pass

t = threading.Thread(target=readSO, name='readSO', args=())
t.daemon = True
t.start()

t = threading.Thread(target=readUI, name='readUI', args=())
t.daemon = True
t.start()

try:
	os.waitpid(pid, 0)
except KeyboardInterrupt:
	os.kill(pid, signal.SIGKILL)
	os.waitpid(pid, 0)
finally:
	log.close()
	try:
		wstream.close()
		rstream.close()
	except:
		pass
