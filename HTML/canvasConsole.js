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
}

function startDisplay() {
	var canvas = document.querySelector("canvas");
	// fill loop
	var ctx = canvas.getContext("2d");
	var width = canvas.width;
	var height = canvas.height;
	ctx.textBaseline = "top";
	var ch = 24;
	ctx.font = ch + "px monospace";
	var cw = ctx.measureText("0").width;
	setInterval(function() {
		// instead of clearing fade
		ctx.fillStyle = "rgba(0, 0, 0, 0.1)";
		ctx.fillRect(0, 0, width, height);
		// then add our data
		ctx.fillStyle = "rgb(0, 255, 0)"
		for(var y = 0; y < grid.height; y++) {
			var line = grid.cells.slice(grid.width * y, grid.width * y + grid.width).map(c => c.glyph).join('');
			ctx.fillText(line, 0, ch * y);
		}
		// cursor
		var cursorx = grid.cursor % grid.width;
		var cursory = Math.floor(grid.cursor / grid.width);
		ctx.fillRect(cursorx * cw, cursory * ch, cw, ch);
		// cursor contains inverted copy of the letter it is occluding
		if(grid.cursor != -1) {
			ctx.fillStyle = "rgb(0, 0, 0)";
			ctx.fillText(grid.cells[grid.cursor].glyph, cursorx * cw, cursory * ch);
		}
	}, 1000 / 60);
}
