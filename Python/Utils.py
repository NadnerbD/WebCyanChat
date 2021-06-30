from io import StringIO, BytesIO

def readTo(stream, delim, ignore):
	matches = 0
	if(type(delim) == bytes):
		output = BytesIO()
	else:
		output = StringIO()
	if(hasattr(stream, 'recv')):
		read = stream.recv
	else:
		read = stream.read
	while(matches < len(delim)):
		char = read(1)
		if(not char):
			return None
		elif(char == delim[matches:matches+1]):
			matches += 1
		elif(not char in ignore):
			matches = 0
		output.write(char)
	return output.getvalue()

def parseToDict(string, eq, delim):
	output = dict()
	items = string.split(delim)
	for item in items:
		keyVal = item.split(eq, 1)
		if(len(keyVal) == 2):
			output[keyVal[0]] = keyVal[1]
	return output
