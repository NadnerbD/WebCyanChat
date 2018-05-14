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
	var charRect = document.querySelector("span#char").getBoundingClientRect();
	reqResize(
		Math.floor(window.innerWidth / charRect.width),
		Math.floor(window.innerHeight / charRect.height)
	);
}

function startDisplay() {
	var canvas = document.querySelector("canvas#grid");
	var ctx = canvas.getContext("2d");
	var span = document.querySelector("span#char").getBoundingClientRect();
	var ch = span.height;
	var cw = span.width;
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
				ctx.fillText(cell.glyph, x * cw, y * ch);
			}
		}
		// cursor
		if(grid.cursor != -1) {
			var cursorx = grid.cursor % grid.width;
			var cursory = Math.floor(grid.cursor / grid.width);
			ctx.fillRect(cursorx * cw, cursory * ch, cw, ch);
			// cursor contains inverted copy of the letter it is occluding
			ctx.fillStyle = "rgb(0, 0, 0)";
			ctx.fillText(grid.cells[grid.cursor].glyph, cursorx * cw, cursory * ch);
		}
	}, 1000 / 60);
}
