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
		ctx.fillStyle = "rgb(0, 255, 0)"
		for(var y = 0; y < grid.height; y++) {
			var line = grid.cells.slice(grid.width * y, grid.width * y + grid.width).map(c => c.glyph).join('');
			ctx.fillText(line, 0, ch * y);
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
