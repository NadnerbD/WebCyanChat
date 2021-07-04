class Cell {
	constructor(cell) {
		this.elem = cell;
		this._style = blank_style;
	}
	set glyph(g) {
		this.elem.firstChild.data = g;
	}
	get glyph() {
		return this.elem.firstChild.data;
	}
	set style(v) {
		this._style = v;
		var hasCursor = this.elem.classList.contains('cursor');
		this.elem.className = '';
		this.elem.style.color = '';
		this.elem.style.backgroundColor = '';
		var style = unpackStyle(v);
		for(var s in style) {
			if(style[s] === 1) {
				if(style[s]) this.elem.classList.add(s);
			}
		}
		if(style.fgColorMode == 1) {
			this.elem.style.color = style.color;
		}else if(style.color) {
			this.elem.classList.add('color-' + style.color);
		}
		if(style.bgColorMode == 1) {
			this.elem.style.backgroundColor = style.backg;
		}else if(style.backg) {
			this.elem.classList.add('backg-' + style.backg);
		}
		if(hasCursor) {
			this.elem.classList.add('cursor');
		}
	}
	get style() {
		return this._style;
	}
}

class Grid {
	constructor(width, height) {
		this.width = width;
		this.height = height;
		this.cells = new Array();
		this.cursor_cell = undefined;
		// construct the grid html
		var container = document.getElementById("grid");
		while(container.childNodes.length)
			container.removeChild(container.firstChild);
		var list = document.createElement("ul");
		for(var y = 0; y < height; y++) {
			var line = document.createElement("li");
			for(var x = 0; x < width; x++) {
				var cell = document.createElement("span");
				var char = document.createTextNode(" ");
				cell.appendChild(char);
				line.appendChild(cell);
				this.cells.push(new Cell(cell));
			}
			list.appendChild(line);
		}
		container.appendChild(list);
	}
	set cursor(index) {
		if(this.cursor_cell) {
			this.cursor_cell.elem.classList.remove("cursor");
			this.cursor_cell = undefined;
		}
		if(index != -1) {
			this.cursor_cell = this.cells[index];
			this.cursor_cell.elem.classList.add("cursor");
		}
	}
	set inverted(value) {
		document.body.className = value ? "inverted" : "";
	}
	get inverted() {
		return document.body.className == "inverted";
	}
}

function setTheme(theme) {
	document.getElementById("theme").href = "console-" + theme + ".css";
	document.getElementById("themeSelect").value = theme;
	localStorage.setItem("consoleTheme", theme);
}

function sizeToWindow() {
	var charRect = document.querySelector("#grid span").getBoundingClientRect();
	reqResize(
		Math.floor(window.innerWidth / charRect.width),
		Math.floor(window.innerHeight / charRect.height)
	);
}

