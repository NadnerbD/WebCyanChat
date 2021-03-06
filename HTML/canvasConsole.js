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

var fontSelection = "Bitfont";
function setFont(opt) {
	fontSelection = opt;
	sizeToWindow();
}

function getCharSize() {
	if(fonts[fontSelection] != undefined) {
		return {width: fonts[fontSelection].width+1, height: fonts[fontSelection].height+1};
	}else{
		var rect = document.querySelector("span#char").getBoundingClientRect();
		return {width: Math.ceil(rect.width), height: Math.ceil(rect.height)};
	}
}

function sizeToWindow() {
	var charRect = getCharSize();
	cw = charRect.width;
	ch = charRect.height;
	reqResize(
		Math.floor(window.innerWidth / charRect.width),
		Math.floor(window.innerHeight / charRect.height)
	);
}

// "size" is the size of the glyph bitmaps
// "width" and "height" are the the space allocated for drawing
var fonts = {
	"Bitfont": {
		data: [1339714, 807363, 1577030, 807235, 1839303, 274503, 1593414, 1339717, 1843335, 545028, 2388297, 1839169, 4544209, 2413257, 1610310, 274755, 68719174, 1323331, 802886, 532615, 1610313, 1090641, 2708817, 1331333, 1065617, 3940623, 1593728, 807105, 1577344, 1593732, 1585536, 274498, 50868416, 1331393, 266241, 17043457, 1323329, 266305, 5591744, 1331392, 544896, 17584320, 68702592, 266432, 795008, 532930, 1593664, 545088, 2708544, 1319232, 51409216, 1843648, 545090, 1843394, 1839363, 803203, 1077572, 802887, 1863750, 270599, 544963, 1077575, 35398082, 553088, 448, 20613, 270600, 1835456, 2367753, 325, 65, 175941578, 1577286, 1609862, 117440512, 33820738, 17309825, 17039360, 262144, 17039424, 262208, 524547, 262209, 2113665, 17043521, 101200006, 50880643, 67637380, 17318017, 50597955, 50864259, 129, 322, 330],
		index: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789$+-*/=%\"'#@&_(),.;:?!\\|{}<>[]`^~",
		size: [6, 5],
		width: 5,
		height: 5
	},
	"Pico-8": {
		data: [0, 470235598, 330, 368409920, 524752836, 866266720, 747841574, 132, 409147596, 214315398, 156718208, 139432064, 205520896, 458752, 201326592, 104012172, 1069412223, 1053176207, 1043463967, 1066171167, 831291259, 1066171519, 1069415551, 207827743, 1069416319, 1066172287, 6291648, 106954944, 409049472, 14694400, 214708416, 201810703, 1008662062, 935325550, 532529007, 498175854, 532541295, 1009892478, 103922814, 1035832446, 935198587, 509810895, 247869855, 935174011, 1043434595, 935198715, 935194479, 498986862, 104329071, 1023274862, 934539119, 529283198, 207821023, 498986875, 149811067, 939519867, 935170939, 529301371, 1043542815, 476256462, 830877894, 482750862, 324, 1040187392, 130, 800978944, 1069399139, 1009907712, 1035860760, 1014872064, 208640220, 1603235710, 935181411, 409147398, 1321611660, 917745507, 409147590, 935307264, 935181312, 532543488, 1178070895, 1905225598, 104708096, 532936704, 409156806, 1035856896, 145615872, 368962560, 934767616, 1569681275, 1046903808, 407048576, 138547328, 411836800, 5440, 10976384], 
		index: " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~*",
		size: [5, 6],
		width: 5,
		height: 8
	},
	"Minecraft": {
		data: [1363539022, 276, 1363473487, 244, 1090786382, 228, 1363481679, 244, 1090809951, 496, 1090809951, 16, 1363513438, 228, 1363539025, 276, 2181570695, 112, 1346438160, 228, 1361343057, 276, 1090785345, 496, 1363498705, 276, 1365595345, 276, 1363481678, 228, 1090843727, 16, 1363481678, 354, 1363473487, 276, 1346429022, 228, 68174111, 65, 1363481681, 228, 2437223505, 66, 3578074193, 278, 1361592977, 276, 68174481, 65, 1108378655, 496, 1581309952, 484, 1363988545, 244, 1095032832, 228, 1365599248, 484, 1598349312, 480, 2181623948, 32, 2437275648, 15623, 1363988545, 276, 1090785281, 16, 1346437136, 14612, 1125421121, 145, 1090785345, 32, 1431613440, 276, 1363472384, 276, 1363468288, 228, 3511472128, 1043, 2439340032, 16647, 1095553024, 16, 235266048, 244, 2181591170, 64, 1363480576, 484, 2437222400, 66, 1430589440, 421, 2217283584, 274, 2437222400, 15623, 2216816640, 496, 1398117454, 228, 68174212, 497, 1110508622, 496, 1345389646, 228, 524625176, 260, 1346433119, 228, 1362890892, 228, 69272671, 65, 1362695246, 228, 276370510, 98, 1073741824, 16, 1073741824, 1040, 1073745984, 1040, 1073745984, 16, 3493336964, 67, 2670326410, 162, 4226, 0, 21130, 0, 17043521, 16, 2182119952, 16, 69272654, 64, 2182120017, 276, 1297629828, 354, 2164527244, 192, 136347907, 49, 2109134942, 992, 33825032, 129, 2216706177, 16, 1090785351, 112, 68174087, 113, 2181308556, 192, 69222659, 49, 1638, 0, 8257, 0, 1090523201, 16, 135274625, 258, 70276, 0, 2384448, 0, 75251968, 1, 8126464, 0, 3221352448, 7, 0, 31744],
		index: 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z a b c d e f g h i j k l m n o p q r s t u v w x y z 0 1 2 3 4 5 6 7 8 9 . , ; : $ # \' " ! / ? % & ( ) @ < > [ ] { } ~ ` | \\ ^ * + - = _',
		size: [6, 8],
		width: 6,
		height: 8
	}
};

function BlitChar(ctx, chr, cursor_x, cursor_y) {
	if(chr == " ") {
		cursor_x += 1;
		return;
	}
	var font = fonts[fontSelection];
	if(font == undefined) {
		ctx.fillText(chr, cursor_x, cursor_y);
		return;
	}
	var di = font.index.indexOf(chr);
	var data = font.data[di];
	var mask = 1;
	var x;
	var y;
	var max = 0;
	if(font.size[0] * font.size[1] < 31 && data & (1 << 30)) {
		cursor_y += 2;
	}
	for(y = 0; y < font.size[1]; y++) {
		for(x = 0; x < font.size[0]; x++) {
			if(mask == 0) {
				data = font.data[++di];
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

var cw;
var ch;

function startDisplay() {
	var canvas = document.querySelector("canvas#grid");
	var ctx = canvas.getContext("2d");
	var span = getCharSize();
	ch = span.height;
	cw = span.width;
	function canvasResize(event) {
		canvas.height = window.innerHeight;
		canvas.width = window.innerWidth;
		ctx = canvas.getContext("2d");
		ctx.textBaseline = "hanging";
		ctx.font = document.querySelector("span#char").getBoundingClientRect().height + "px monospace";
		ctx.fillStyle = "rgba(0, 0, 0, 1.0)";
		ctx.fillRect(0, 0, canvas.width, canvas.height);
	}
	window.addEventListener("resize", canvasResize);
	canvasResize();
	// fill loop
	var blink = 0;
	setInterval(function() {
		// instead of clearing fade
		ctx.fillStyle = "rgba(0, 0, 0, 1.0)";
		ctx.fillRect(0, 0, canvas.width, canvas.height);
		// then add our data
		for(var y = 0; y < grid.height; y++) {
			for(var x = 0; x < grid.width; x++) {
				var cell = grid.cells[y * grid.width + x];
				var style = unpackStyle(cell.style);
				var fgF   = style.bold   ? 255 : 127;
				var bgF   = style.bgBold ? 255 : 127;
				var toRGB = (color, F) => 
					"rgb(" +
					F * ((color     ) & 0x1) + "," +
					F * ((color >> 1) & 0x1) + "," +
					F * ((color >> 2) & 0x1) + ")";
				var bgStyle = style.backg == undefined ? toRGB(0x0, bgF) : toRGB(cell.style >> 12, bgF);
				var fgStyle = style.color == undefined ? toRGB(0x7, fgF) : toRGB(cell.style >>  8, fgF);
				// draw bg
				ctx.fillStyle = style.inverted ? fgStyle : bgStyle;
				ctx.fillRect(x * cw, y * ch, cw, ch);
				// draw fg
				ctx.fillStyle = style.inverted ? bgStyle : fgStyle;
				BlitChar(ctx, cell.glyph, x * cw, y * ch);
			}
		}
		// cursor
		blink++;
		if(blink > 20) blink = 0;
		if(blink < 10 && grid.cursor != -1) {
			var cursorx = grid.cursor % grid.width;
			var cursory = Math.floor(grid.cursor / grid.width);
			ctx.fillRect(cursorx * cw, cursory * ch, cw, ch);
			// cursor contains inverted copy of the letter it is occluding
			ctx.fillStyle = style.inverted ? fgStyle : bgStyle;
			BlitChar(ctx, grid.cells[grid.cursor].glyph, cursorx * cw, cursory * ch);
		}
	}, 1000 / 60);
}
