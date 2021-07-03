var sock;
var modCtrl = false;
var appkeymode = false;
var firstInit = true;

var colors = [
	"black",
	"red",
	"green",
	"yellow",
	"blue",
	"magenta",
	"cyan",
	"white"
];

function unpackStyle(value) {
	return {
		bold:              value        & 0x01 ,
		bgBold:           (value >>  1) & 0x01 ,
		underline:        (value >>  2) & 0x01 ,
		italic:           (value >>  3) & 0x01 ,
		inverted:         (value >>  4) & 0x01 ,
		color:     colors[(value >>  8) & 0x0F],
		backg:     colors[(value >> 12) & 0x0F]
	};
}
// "default" color is 9
var blank_style = (9 << 8) | (9 << 12);

function init() {
	document.addEventListener("keydown", keydown, false);
	document.addEventListener("paste", handlePaste, false);
	window.addEventListener("resize", handleResize, false);
	grid = new Grid(0, 0);

	setTheme(localStorage.getItem("consoleTheme") || "default");

	sock = new WebSocket((window.location.protocol=="https:"?"wss://":"ws://") + window.location.host + "/term-socket", "term");
	sock.binaryType = "arraybuffer";
	MSG_MODES = 1;
	MSG_INIT = 2;
	MSG_DIFF = 3;
	MSG_TITLE = 4;
	DIFF_CHAR = 0;
	DIFF_SHIFT = 1;
	DIFF_NEXT_CHAR = 2;
	DIFF_NEXT_CHAR_NOSTYLE = 3;
	var decoder = new TextDecoder('utf-8');
	sock.onmessage = function (msgEvent) {
		var dv = new DataView(msgEvent.data);
		var cmd = dv.getUint8(0);
		switch(cmd) {
		case MSG_MODES:
			var modes = dv.getUint8(1);
			appkeymode = modes & 0x01;
			grid.inverted = !!(modes & 0x02);
			break;
		case MSG_TITLE:
			var dc = new TextDecoder("utf-8");
			document.title = dc.decode(new Uint8Array(msgEvent.data, 1, msgEvent.data.byteLength - 1));
			break;
		case MSG_INIT:
			var mWidth = dv.getInt16(1);
			var mHeight = dv.getInt16(3);
			// console.log("INIT " + mWidth + " " + mHeight);
			var mCursor = dv.getInt32(5);
			if(grid.width != mWidth || grid.height != mHeight) {
				grid = new Grid(mWidth, mHeight);
			}
			var charGrid = decoder.decode(new Uint8Array(msgEvent.data, 9 + grid.width * grid.height * 2));
			for(var i = 0; i < grid.width * grid.height; i++) {
				grid.cells[i].glyph = charGrid[i];
				grid.cells[i].style = dv.getUint16(9 + 2 * i);
			}
			grid.cursor = mCursor;
			if(firstInit) {
				sizeToWindow();
				firstInit = false;
			}
			break;
		case MSG_DIFF:
			var mCursor = dv.getInt32(1);
			var mOffset = 5;
			// var LOGMSG = [];
			var chPos = 0;
			var chStyle = 0;
			while(mOffset < msgEvent.data.byteLength) {
				var chType = dv.getUint8(mOffset++);
				switch(chType) {
				case DIFF_CHAR:
					var chPos = dv.getInt32(mOffset);
					mOffset += 4;
				case DIFF_NEXT_CHAR:
					var chStyle = dv.getUint16(mOffset);
					mOffset += 2;
				case DIFF_NEXT_CHAR_NOSTYLE:
					var fb = dv.getUint8(mOffset);
					var cLen = 1;
					for(var b = 0; b < 4 && (fb & (0x80 >> b)); b++) cLen = b + 1;
					var chChar = decoder.decode(new Uint8Array(msgEvent.data, mOffset, cLen));
					mOffset += cLen;
					// LOGMSG.push("char: " + JSON.stringify([chPos, chStyle, chChar]));
					grid.cells[chPos].glyph = chChar;
					grid.cells[chPos].style = chStyle;
					chPos++;
					break;
				case DIFF_SHIFT:
					var start = dv.getInt32(mOffset);
					var end = dv.getInt32(mOffset + 4);
					var offset = dv.getInt32(mOffset + 8);
					mOffset += 12;
					// LOGMSG.push("shift: " + JSON.stringify([start, end, offset]));
					var srcgrid = grid.cells.slice(start, end).map(c => [c.glyph, c.style]);
					var index = Math.min(start + offset, start);
					while(index < Math.max(end + offset, end) && index < grid.cells.length) {
						if(index < start + offset || index >= end + offset) {
							grid.cells[index].glyph = " ";
							grid.cells[index].style = blank_style;
						}else{
							var src = srcgrid[index - start - offset];
							grid.cells[index].glyph = src[0];
							grid.cells[index].style = src[1];
						}
						index++;
					}
					break;
				}
			}
			grid.cursor = mCursor;
			// console.log(LOGMSG);
			break;
		}
	}
	sock.onclose = function () {
		window.close();
	}
}

function sendKey(keyCode) {
	var msg = new Uint8Array([107, keyCode]); // 'k'
	sock.send(msg);
	// console.log(String.fromCharCode(keyCode));
}

function reqResize(x, y) {
	var msg = new Uint8Array([114, 0, 0, 0, 0]); // 'r'
	var dv = new DataView(msg.buffer);
	dv.setUint16(1, x);
	dv.setUint16(3, y);
	sock.send(msg);
}

var cursorCodes = {35: 52, 36: 49, 37: 68, 38: 65, 39: 67, 40: 66, 33: 53, 34: 54, 45: 50, 46: 51}; // 41DACB5623
function keydown(event) {
	// directional and special keys will only be
	// picked up here
	//console.log(event.which);
	handled = true;
	switch(event.which) {
		// cursor keys
		case 37: // left
		case 38: // up
		case 39: // right
		case 40: // down
			sendKey(27); // Esc
			if(appkeymode) {
				sendKey(79); // O (application mode)
			}else{
				sendKey(91); // [ (normal mode)
			}
			sendKey(cursorCodes[event.which]);
			break;
		// editing keys
		case 33: // pg up
		case 34: // pg down
		case 35: // end
		case 36: // home
		case 45: // insert
		case 46: // del
			sendKey(27); // Esc
			sendKey(91); // [
			sendKey(cursorCodes[event.which]);
			sendKey(126); // ~
			break;
		case 8: // Backspace
			sendKey(127); // 0x7F (ASCII DEL)
			break;
		case 112: // F1
		case 113: // F2
		case 114: // F3
		case 115: // F4
			sendKey(27); // Esc
			sendKey(79); // O
			sendKey(event.which - 32);
			break;
		case 116: // F5
			sendKey(27); // Esc
			sendKey(91); // [
			sendKey(49); // 1
			sendKey(53); // 5
			sendKey(126); // ~
			break;
		case 117: // F6
		case 118: // F7
		case 119: // F8
		case 120: // F9
		case 121: // F10
			sendKey(27); // Esc
			sendKey(91); // [
			for(var digit of (event.which - 100).toString())
				sendKey(digit.charCodeAt(0));
			sendKey(126); // ~
			break;
		case 122: // F11
		case 123: // F12
			sendKey(27); // Esc
			sendKey(91); // [
			for(var digit of (event.which - 99).toString())
				sendKey(digit.charCodeAt(0));
			sendKey(126); // ~
			break;
		case 9: // Tab
		case 13: // Enter
		case 27: // Esc
			// send key code directly
			sendKey(event.which);
			break;
		case 16: // Shift
		case 17: // Ctrl
		case 18: // Alt
		case 19: // Pause/Break
		case 20: // Caps Lock
		case 91: // Left Windows
		case 92: // Right Windows
		case 93: // Context Menu
			// don't send anything on modifier key events
			break;
		default: // Send character code for anything we don't recognize
			if(event.ctrlKey && event.key == "v") { // real ctrl-v needs to trigger browser paste event
				handled = false;
				break;
			}
			if(modCtrl || event.ctrlKey) { // ctrl and soft-ctrl
				sendKey(event.which & 0037);
				modCtrl = false;
			}else{
				sendKey(event.key.charCodeAt(0));
			}
			break;
	}
	if(handled) {
		event.preventDefault();
		event.stopPropagation();
	}
}

var encoder = new TextEncoder('utf-8');
function handlePaste(event) {
	event.stopPropagation();
	event.preventDefault();

	var cData = event.clipboardData || window.clipboardData;
	var data = encoder.encode(cData.getData("Text"));

	for(var i = 0; i < data.byteLength; i++) {
		if(data[i] == 13) continue;    // ignore \r
		if(data[i] == 10) sendKey(13); // \n -> \r
		else sendKey(data[i]);
	}
}

var resizeTimeout;
function handleResize(event) {
	clearTimeout(resizeTimeout);
	resizeTimeout = setTimeout(sizeToWindow, 200);
}

