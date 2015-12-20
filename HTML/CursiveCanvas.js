var gridSize = [12, 8];

function initCanvas() {
	var c = document.getElementById("grid_canvas");
	var ct = c.getContext("2d");
	ct.fillStyle = "rgb(255, 255, 255)";
	r = c.getClientRects();
	ct.fillRect(0, 0, r[0].width, r[0].height);
	var xSpacing = (r[0].width / gridSize[0]);
	var ySpacing = (r[0].height / gridSize[1]);
	ct.fillStyle = "rgb(196, 196, 196)";
	for(y = 0; y < gridSize[1]; y++) {
		ct.fillRect(0, y * ySpacing + ySpacing * 0.25, r[0].width, 1);
		ct.fillRect(0, y * ySpacing + ySpacing * 0.75, r[0].width, 1);
	}
	ct.textBaseline = "top";
	ct.font = ySpacing / 6 + "px monospace";
	var char = 32;
	for(y = 0; y < gridSize[1]; y++) {
		for(x = 0; x < gridSize[0]; x++) {
			ct.fillText(String.fromCharCode(char++), x * xSpacing + 1, y * ySpacing + 1);
		}
	}
	ct.fillStyle = "rgb(127, 127, 127)";
	for(x = 1; x < gridSize[0]; x++) {
		ct.fillRect(x * xSpacing, 0, 1, r[0].height);
	}
	for(y = 1; y < gridSize[1]; y++) {
		ct.fillRect(0, y * ySpacing, r[0].width, 1);
	}
	// set up the styles for font rendering
	var ts = 0.25;
	var style = document.createElement("style");
	style.id = "cursive-data-style";
	document.head.appendChild(style);
	style.sheet.insertRule(".l { display: inline-block; background-size: " + r[0].width * ts + "px; height: " + (ySpacing * ts) + "px; width: " + (xSpacing * ts) + "px; }", 0);
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
	fct.font = ySpacing + "px monospace";
	char = 32;
	for(y = 0; y < gridSize[1]; y++) {
		for(x = 0; x < gridSize[0]; x++) {
			fct.fillText(String.fromCharCode(char++), x * xSpacing, y * ySpacing);
		}
	}
	style.sheet.insertRule(".l-uid-0 .l { background-image: url(" + fc.toDataURL() + "); }", 0);
	// clear the system font and insert the saved user font, if present
	fct.clearRect(0, 0, r[0].width, r[0].height);
	var lastImage = localStorage.getItem("font_image");
	if(lastImage) {
		var img = new Image();
		img.onload = function () { fct.drawImage(img, 0, 0); };
		img.src = lastImage;
	}
	// set up painting events on the font canvas
	// pressure is obvious, sysX and sysY are page coords with sub-pixel resolution
	var penAPI = document.getElementById("wtPlugin").penAPI || {isWacom: false};
	function getPos(e) {
		// tablet-provided offset coordinates, using the event coordinates only to subtract the element's screen position
		//return penAPI.isWacom ? [penAPI.sysX - (e.screenX - e.offsetX), penAPI.sysY - (e.screenY - e.offsetY), penAPI.pressure] : [e.offsetX, e.offsetY, 0.5];
		// this corrects for screen coordinates that are not on the primary monitor, but does not correct coordinate scaling, so other monitors must have the same dimensions
		return penAPI.isWacom ? [penAPI.sysX - (e.screenX - screen.left - e.offsetX), penAPI.sysY - (e.screenY - screen.top - e.offsetY), penAPI.pressure] : [e.offsetX, e.offsetY, 0.5];
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
	var undoList = [];
	function paintStart(e) {
		// save last state for undo
		undoList.push(fct.getImageData(0, 0, r[0].width, r[0].height));
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
	fc.addEventListener("mousedown", paintStart, false);
	function paintEnd(e) {
		fc.removeEventListener("mousemove", paintLine, false);
		fct.restore(); // this removes the clipping mask
	}
	fc.addEventListener("mouseout", paintEnd, false);
	fc.addEventListener("mouseup", paintEnd, false);
	// compositing modes for draw and erase
	var erase = false;
	var letterMask = true;
	document.body.addEventListener("keypress", function(e) {
		// Chrome support, because why not I guess
		if(!e.key) e.key = String.fromCharCode(e.charCode);
		if(e.key == "e") {
			// toggle eraser mode
			erase = !erase;
			fct.globalCompositeOperation = erase ? "destination-out" : "source-over";
		}else if(e.key == "z" && e.ctrlKey == true) {
			// undo last stroke
			if(undoList.length > 0) {
				fct.putImageData(undoList.pop(), 0, 0);
			}
		}else if(e.key == "m") {
			// toggle letter mask
			letterMask = !letterMask;
		}else if(e.key == "s" && e.ctrlKey == true) {
			var img = fc.toDataURL();
			send_cc("201|" + img);
			localStorage.setItem("font_image", img);
			e.preventDefault();
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
