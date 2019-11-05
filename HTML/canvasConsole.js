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

var font = [1363539022, 276, 1363473487, 244, 1090786382, 228, 1363481679, 244, 1090809951, 496, 1090809951, 16, 1363513438, 228, 1363539025, 276, 2181570695, 112, 1346438160, 228, 1361343057, 276, 1090785345, 496, 1363498705, 276, 1365595345, 276, 1363481678, 228, 1090843727, 16, 1363481678, 354, 1363473487, 276, 1346429022, 228, 68174111, 65, 1363481681, 228, 2437223505, 66, 3578074193, 278, 1361592977, 276, 68174481, 65, 1108378655, 496, 1581309952, 484, 1363988545, 244, 1095032832, 228, 1365599248, 484, 1598349312, 480, 2181623948, 32, 2437275648, 15623, 1363988545, 276, 1090785281, 16, 1346437136, 14612, 1125421121, 145, 1090785345, 32, 1431613440, 276, 1363472384, 276, 1363468288, 228, 3511472128, 1043, 2439340032, 16647, 1095553024, 16, 235266048, 244, 2181591170, 64, 1363480576, 484, 2437222400, 66, 1430589440, 421, 2217283584, 274, 2437222400, 15623, 2216816640, 496, 1398117454, 228, 68174212, 497, 1110508622, 496, 1345389646, 228, 524625176, 260, 1346433119, 228, 1362890892, 228, 69272671, 65, 1362695246, 228, 276370510, 98, 1073741824, 16, 1073741824, 1040, 1073745984, 1040, 1073745984, 16, 3493336964, 67, 2670326410, 162, 4226, 0, 21130, 0, 17043521, 16, 2182119952, 16, 69272654, 64, 2182120017, 276, 1297629828, 354, 2164527244, 192, 136347907, 49, 2109134942, 992, 33825032, 129, 2216706177, 16, 1090785351, 112, 68174087, 113, 2181308556, 192, 69222659, 49, 1638, 0, 8257, 0, 1090523201, 16, 135274625, 258, 70276, 0, 2384448, 0, 75251968, 1, 8126464, 0, 3221352448, 7, 0, 31744];
var fontIndex = 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z a b c d e f g h i j k l m n o p q r s t u v w x y z 0 1 2 3 4 5 6 7 8 9 . , ; : $ # \' " ! / ? % & ( ) @ < > [ ] { } ~ ` | \\ ^ * + - = _';
var fontSize = [6, 8];
var fontWidth = 6;

function BlitChar(ctx, chr, cursor_x, cursor_y) {
	if(chr == " ") {
		cursor_x += 1;
		return;
	}
	var di = fontIndex.indexOf(chr);
	var data = font[di];
	var mask = 1;
	var x;
	var y;
	var max = 0;
	for(y = 0; y < fontSize[1]; y++) {
		for(x = 0; x < fontSize[0]; x++) {
			if(mask == 0) {
				data = font[++di];
				mask = 1;
			}
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
