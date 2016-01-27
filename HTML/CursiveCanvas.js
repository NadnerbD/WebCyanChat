var gridSize = [12, 8];

function initCanvas() {
	var c = document.getElementById("grid_canvas");
	var ct = c.getContext("2d");
	ct.fillStyle = "rgb(255, 255, 255)";
	var rect = c.getBoundingClientRect();
	ct.fillRect(0, 0, rect.width, rect.height);
	var xSpacing = (rect.width / gridSize[0]);
	var ySpacing = (rect.height / gridSize[1]);
	ct.fillStyle = "rgb(196, 196, 196)";
	for(y = 0; y < gridSize[1]; y++) {
		ct.fillRect(0, y * ySpacing + ySpacing * 0.25, rect.width, 1);
		ct.fillRect(0, y * ySpacing + ySpacing * 0.75, rect.width, 1);
	}
	ct.textBaseline = "top";
	ct.font = ySpacing / 4 + "px \"Lucida Console\", Monaco, monospace bold";
	var char = 32;
	for(y = 0; y < gridSize[1]; y++) {
		for(x = 0; x < gridSize[0]; x++) {
			ct.fillText(String.fromCharCode(char++), x * xSpacing + 1, y * ySpacing + 1);
		}
	}
	ct.fillStyle = "rgb(127, 127, 127)";
	for(x = 1; x < gridSize[0]; x++) {
		ct.fillRect(x * xSpacing, 0, 1, rect.height);
	}
	for(y = 1; y < gridSize[1]; y++) {
		ct.fillRect(0, y * ySpacing, rect.width, 1);
	}
	// set up the styles for font rendering
	var ts = 0.25;
	var style = document.createElement("style");
	style.id = "cursive-data-style";
	document.head.appendChild(style);
	style.sheet.insertRule(".l { display: inline-block; background-size: " + rect.width * ts + "px; height: " + (ySpacing * ts) + "px; width: " + (xSpacing * ts) + "px; }", 0);
	var char = 32;
	for(y = 0; y < gridSize[1]; y++) {
		for(x = 0; x < gridSize[0]; x++) {
			// Chrome apparently can't do this right without having terrible rounding error or something
			//style.sheet.insertRule(".l-" + char++ + " { background-position: " + (-x * 100) + "% " + (-y * 100) + "%; }", 0);
			style.sheet.insertRule(".l-" + char++ + " { background-position: " + (-x * xSpacing * ts) + "px " + (-y * ySpacing * ts) + "px; }", 0);
		}
	}
	// TEMP: fill in the font canvas and save a default font
	var fc = document.getElementById("font_canvas");
	var fct = fc.getContext("2d");
	// create the default system font for non-user messages
	fct.textBaseline = "top";
	fct.fillStyle = "rgb(0, 0, 0)";
	fct.font = ySpacing + "px \"Lucida Console\", Monaco, monospace bold";
	char = 32;
	for(y = 0; y < gridSize[1]; y++) {
		for(x = 0; x < gridSize[0]; x++) {
			fct.fillText(String.fromCharCode(char++), x * xSpacing, y * ySpacing);
		}
	}
	style.sheet.insertRule(".l-uid-0 .l { background-image: url(" + fc.toDataURL() + "); }", 0);
	// clear the system font and insert the saved user font, if present
	fct.clearRect(0, 0, rect.width, rect.height);
	var lastImage = localStorage.getItem("font_image");
	if(lastImage) {
		var img = new Image();
		img.onload = function () { fct.drawImage(img, 0, 0); };
		img.src = lastImage;
	}
	// set up painting events on the font canvas
	// pressure is obvious, sysX and sysY are page coords with sub-pixel resolution
	var penAPI = document.getElementById("wtPlugin").penAPI || {isWacom: false};
	var useTabCoords = true;
	function getPos(e) {
		// tablet-provided offset coordinates, using the event coordinates only to subtract the element's screen position
		// this corrects for screen coordinates that are not on the primary monitor, but does not correct coordinate scaling, so other monitors must have the same dimensions
		if(useTabCoords) {
			return penAPI.isWacom ? [penAPI.sysX - (e.screenX - screen.left - e.offsetX), penAPI.sysY - (e.screenY - screen.top - e.offsetY), penAPI.pressure] : [e.offsetX, e.offsetY, 0.5];
		}else{
			return penAPI.isWacom ? [e.offsetX, e.offsetY, penAPI.pressure] : [e.offsetX, e.offsetY, 0.5];
		}
	}
	function paintLine(e) {
		var rad = 4;
		var lc = getPos(e);
		var dist = Math.sqrt(Math.pow(lastPoint[0] - lc[0], 2) + Math.pow(lastPoint[1] - lc[1], 2));
		var dx = (lc[0] - lastPoint[0]) / dist;
		var dy = (lc[1] - lastPoint[1]) / dist;
		var dp = (lc[2] - lastPoint[2]) / dist;
		while(Math.pow(lastPoint[0] - lc[0], 2) + Math.pow(lastPoint[1] - lc[1], 2) > 1) {
			fillCircle(fct, lastPoint[0], lastPoint[1], rad * lastPoint[2]);
			lastPoint[0] += dx;
			lastPoint[1] += dy;
			lastPoint[2] += dp;
		}
	}
	var cont = document.getElementById("canvas_container");
	var canvasScale = 1;
	var canvasOffset = [0, 0];
	function updateCanvasTransform() {
		cont.style.transform = "scale(" + canvasScale + ", " + canvasScale + ") translate(" + canvasOffset[0] + "px, " + canvasOffset[1] + "px)";
	}
	function panCanvas(e) {
		canvasOffset[0] += (e.pageX - lastPos[0]) / canvasScale;
		canvasOffset[1] += (e.pageY - lastPos[1]) / canvasScale;
		lastPos = [e.pageX, e.pageY];
		updateCanvasTransform();
	}
	function scaleCanvas(value) {
		canvasScale *= value;
		updateCanvasTransform();
	}
	function resetCanvas() {
		canvasScale = 1;
		canvasOffset = [0, 0];
		updateCanvasTransform();
	}
	var undoList = [];
	var lastPoint, lastPos;
	function paintStart(e) {
		if(spaceDown) {
			fc.addEventListener("mousemove", panCanvas, false);
			lastPos = [e.pageX, e.pageY];
		}else{
			// save last state for undo
			undoList.push(fct.getImageData(0, 0, rect.width, rect.height));
			fc.addEventListener("mousemove", paintLine, false);
			lastPoint = getPos(e);
			// clip drawing to the letter the stroke started in
			fct.save();
			if(letterMask) {
				fct.beginPath();
				var lx = Math.floor(lastPoint[0] / xSpacing) * xSpacing;
				var ly = Math.floor(lastPoint[1] / ySpacing) * ySpacing;
				fct.moveTo(lx + 1, ly + 1);
				fct.lineTo(lx + xSpacing, ly + 1);
				fct.lineTo(lx + xSpacing, ly + ySpacing);
				fct.lineTo(lx + 1, ly + ySpacing);
				fct.clip();
			}
		}
	}
	fc.addEventListener("mousedown", paintStart, false);
	function paintEnd(e) {
		fc.removeEventListener("mousemove", paintLine, false);
		fc.removeEventListener("mousemove", panCanvas, false);
		fct.restore(); // this removes the clipping mask
	}
	fc.addEventListener("mouseout", paintEnd, false);
	fc.addEventListener("mouseup", paintEnd, false);
	// compositing modes for draw and erase
	var letterMask = true;
	toggleLetterMask = function() {
		// toggle letter mask
		letterMask = !letterMask;
	};
	var erase = false;
	toggleEraseMode = function() {
		// toggle eraser mode
		erase = !erase;
		fct.globalCompositeOperation = erase ? "destination-out" : "source-over";
	};
	saveFontImage = function() {
		var img = fc.toDataURL();
		localStorage.setItem("font_image", img);
		send_cc("201|" + img);
	};
	undoStroke = function() {
		// undo last stroke
		if(undoList.length > 0) {
			fct.putImageData(undoList.pop(), 0, 0);
		}
	};
	setUseTabletCoords = function(use) {
		useTabCoords = use;
	};
	fc.addEventListener("wheel", function(e) {
		if(e.deltaY != 0) scaleCanvas(e.deltaY < 0 ? e.deltaY / -1.5 : 1.5 / e.deltaY);
	}, false);
	document.body.addEventListener("keypress", function(e) {
		// Chrome support, because why not I guess
		if(!e.key) e.key = String.fromCharCode(e.charCode);
		if(e.key == "e" && e.ctrlKey == true) {
			toggleEraseMode();
		}else if(e.key == "z" && e.ctrlKey == true) {
			undoStroke();
		}else if(e.key == "m" && e.ctrlKey == true) {
			toggleLetterMask();
		}else if(e.key == "s" && e.ctrlKey == true) {
			e.preventDefault();
			saveFontImage();
		}else if(e.key == "PageUp") {
			scaleCanvas(2);
		}else if(e.key == "PageDown") {
			scaleCanvas(0.5);
		}else if(e.key == "Home") {
			resetCanvas();
		}
	}, false);
	var spaceDown = false;
	document.body.addEventListener("keydown", function(e) {
		if(e.keyCode == 32) { // Space
			spaceDown = true;
		}
	}, false);
	document.body.addEventListener("keyup", function(e) {
		if(!e.key) e.key = String.fromCharCode(e.charCode);
		if(e.keyCode == 32) { // Space
			spaceDown = false;
		}
	}, false);
	// now we init the chat connection
	init();
}

function fillCircle(ct, x, y, r) {
	ct.beginPath();
	ct.arc(x, y, r, 0, 2 * Math.PI, false);
	// we'll assume fillStyle has been set appropriately already
	ct.fill();
}

function createString(str) {
	var f = document.createDocumentFragment();
	// TODO: add span-words so that wrapping will work correctly
	for(var char in str) {
		var i = document.createElement("span");
		// when I use img tags, mysterious ::before elements appear out of nowhere
		//i.src = "//:0";
		//i.alt = str.charAt(char);
		i.className = "l l-" + str.charCodeAt(char);
		f.appendChild(i);
	}
	return f;
}
