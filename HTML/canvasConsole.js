class Grid {
	constructor(width, height) {
		this.width = width;
		this.height = height;
		this.cells = new Array(width * height);
		this.cursor_cell = undefined;
		this.cursor = -1;
		this.inverted = false;
		for(var i = 0; i < width * height; i++) {
			this.cells[i] = {
				glyph: ' ',
				style: blank_style
			};
		}
	}
}

var grid = new Grid(0, 0);

function setTheme(theme) {
}

function sizeToWindow() {
	var charRect = {width: fontWidth+1, height: fontSize[1]+1}; //document.querySelector("span#char").getBoundingClientRect();
	reqResize(
		Math.floor(window.innerWidth / charRect.width),
		Math.floor(window.innerHeight / charRect.height)
	);
}

// each int represents a letter, 6x5 (2 unused high order bits)
var font = [1339714, 807363, 1577030, 807235, 1839303, 274503, 1593414, 1339717, 1843335, 545028, 2388297, 1839169, 4544209, 2413257, 1610310, 274755, 68719174, 1323331, 802886, 532615, 1610313, 1090641, 2708817, 1331333, 1065617, 3940623, 1593728, 807105, 1577344, 1593732, 1585536, 274498, 50868416, 1331393, 266241, 17043457, 1323329, 266305, 5591744, 1331392, 544896, 17584320, 68702592, 266432, 795008, 532930, 1593664, 545088, 2708544, 1319232, 51409216, 1843648, 545090, 1843394, 1839363, 803203, 1077572, 802887, 1863750, 270599, 544963, 1077575, 35398082, 553088, 448, 20613, 270600, 1835456, 2367753, 325, 65, 175941578, 1577286, 1609862, 117440512, 33820738, 17309825, 17039360, 262144, 17039424, 262208, 524547, 262209, 2113665, 17043521, 101200006, 50880643, 67637380, 17318017, 50597955, 50864259, 129, 322, 330];
var fontIndex = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789$+-*/=%\"'#@&_(),.;:?!\\|{}<>[]`^~";
var fontSize = [6, 5];
var fontWidth = 5;

var font = [0, 470235598, 330, 368409920, 524752836, 866266720, 747841574, 132, 409147596, 214315398, 156718208, 139432064, 205520896, 458752, 201326592, 104012172, 1069412223, 1053176207, 1043463967, 1066171167, 831291259, 1066171519, 1069415551, 207827743, 1069416319, 1066172287, 6291648, 106954944, 409049472, 14694400, 214708416, 201810703, 1008662062, 935325550, 532529007, 498175854, 532541295, 1009892478, 103922814, 1035832446, 935198587, 509810895, 247869855, 935174011, 1043434595, 935198715, 935194479, 498986862, 104329071, 1023274862, 934539119, 529283198, 207821023, 498986875, 149811067, 939519867, 935170939, 529301371, 1043542815, 476256462, 830877894, 482750862, 324, 1040187392, 130, 800978944, 1069399139, 1009907712, 1035860760, 1014872064, 208640220, 529493886, 935181411, 409147398, 247869836, 917745507, 409147590, 935307264, 935181312, 532543488, 104329071, 831483774, 104708096, 532936704, 409156806, 1035856896, 145615872, 368962560, 934767616, 495939451, 1046903808, 407048576, 138547328, 411836800, 5440, 10976384];
var fontIndex = " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~*";
var fontSize = [5, 6];
var fontWidth = 5;

function BlitChar(ctx, chr, cursor_x, cursor_y) {
	if(chr == " ") {
		cursor_x += 1;
		return;
	}
	var data = font[fontIndex.indexOf(chr)];
	var mask = 0x01;
	var x;
	var y;
	var max = 0;
	for(y = 0; y < fontSize[1]; y++) {
		for(x = 0; x < fontSize[0]; x++) {
			if(mask & data) {
				ctx.fillRect(x + cursor_x, y + cursor_y, 1, 1);
				if(x > max) {
					max = x;
				}
			}
			mask = mask << 1;
		}
	}
	cursor_x += max + 2;
}

function startDisplay() {
	var canvas = document.querySelector("canvas#grid");
	var ctx = canvas.getContext("2d");
	//var span = document.querySelector("span#char").getBoundingClientRect();
	var ch = fontSize[1]+1; //span.height;
	var cw = fontWidth+1; //span.width;
	function canvasResize(event) {
		canvas.height = window.innerHeight;
		canvas.width = window.innerWidth;
		ctx = canvas.getContext("2d");
		ctx.textBaseline = "hanging";
		ctx.font = ch + "px monospace";
		ctx.fillStyle = "rgba(0, 0, 0, 1.0)";
		ctx.fillRect(0, 0, canvas.width, canvas.height);
	}
	window.addEventListener("resize", canvasResize);
	canvasResize();
	// fill loop
	setInterval(function() {
		// instead of clearing fade
		ctx.fillStyle = "rgba(0, 0, 0, 0.1)";
		ctx.fillRect(0, 0, canvas.width, canvas.height);
		// then add our data
		for(var y = 0; y < grid.height; y++) {
			for(var x = 0; x < grid.width; x++) {
				var cell = grid.cells[y * grid.width + x];
				if((cell.style >> 15) & 0x1) {
					if((cell.style >> 4) & 0x1) {
						ctx.fillStyle = "rgb(255, 255, 255)";
						ctx.fillRect(x * cw, y * ch, cw, ch);
					}
				}else{
					ctx.fillStyle = "rgb(" +
						255 * ((cell.style >> 12) & 0x1) + "," +
						255 * ((cell.style >> 13) & 0x1) + "," +
						255 * ((cell.style >> 14) & 0x1) + ")";
					ctx.fillRect(x * cw, y * ch, cw, ch);
				}
				if((cell.style >> 11) & 0x1) {
					if((cell.style >> 4) & 0x1) {
						ctx.fillStyle = "rgb(0, 0, 0)";
					}else{
						ctx.fillStyle = "rgb(255, 255, 255)";
					}
				}else{ ctx.fillStyle = "rgb(" +
					255 * ((cell.style >> 8) & 0x1) + "," +
					255 * ((cell.style >> 9) & 0x1) + "," +
					255 * ((cell.style >> 10) & 0x1) + ")";
				}
				BlitChar(ctx, cell.glyph, x * cw, y * ch);
			}
		}
		// cursor
		if(grid.cursor != -1) {
			var cursorx = grid.cursor % grid.width;
			var cursory = Math.floor(grid.cursor / grid.width);
			ctx.fillRect(cursorx * cw, cursory * ch, cw, ch);
			// cursor contains inverted copy of the letter it is occluding
			ctx.fillStyle = "rgb(0, 0, 0)";
			BlitChar(ctx, grid.cells[grid.cursor].glyph, cursorx * cw, cursory * ch);
		}
	}, 1000 / 60);
}
