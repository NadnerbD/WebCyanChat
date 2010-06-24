// the control script goes here
var styles = ['', 'cyane', 'server', 'client', 'guest', 'client'];

var version = "0.13";
var client_name = "js_cc version " + version + " (NadCC)";
var welcome_message = "Welcome to " + client_name;
var connection;
var connected = 0;
var name_reg = 0;
var userstring = [];
var currentName = "";
var lastAttemptedName = "";
var lastSessionName = "";
var pmwindows = [];
var pingtimer = 0;
var flashstate = 0;
var title = "[CyanChat]WebCC";
var ignoreList = [];
var level = 0;
var authKey = "";
var lastPMWindowOpenUser = "";
var imgurls = [];
var players = [];
var imgtiles = [];
var maxDragDist = 100;

function init() {
	textin = document.getElementById("input");
	textout = document.getElementById("output");
	wholist = document.getElementById("wholistid");
	cyanlist = document.getElementById("cyanlistid");
	connectstatus = document.getElementById("connectstatusid");
	timestamps = document.getElementById("timestampsid");
	palette = document.getElementById("imgpalette");
	// check for a name cookie
	if(document.cookie.split("ccname=").length > 1) {
		lastSessionName = unescape(document.cookie.split("ccname=")[1].split(";")[0]);
	}else{
		lastSessionName = "";
	}
	try {
		// standards compliant
		window.addEventListener("focus", disableFlash, false);
		window.addEventListener("blur", enableFlash, false);
		window.addEventListener("unload", killPMWindows, false);
		window.addEventListener("mousedown", handleMouse, false);
	}catch(exception){
		// this is only for IE
		window.attachEvent("onfocus", disableFlash);
		window.attachEvent("onblur", enableFlash);
		window.attachEvent("onunload", killPMWindows);
		window.attachEvent("onmousedown", handleMouse);
	}
	setTimeout(flashTitle, 1000);
	// all set, let's do this
	connect();
}

var intervalID = 0;
function connect() {
	// update status
	connectstatus.innerHTML = "Connecting...";
	connectstatus.style.color = "#ff0000";
	addTextOut("ChatClient", 5, welcome_message, "1");
	if(window.WebSocket) {
		connection = new WebSocket("ws://" + window.location.host + "/web-socket", "cyanchat");
	}else{
		connection = new XmlHttpSock("/chat-data", "cyanchat");
	}
	connection.onopen = function () {
		// update the notifications
		connected = 1;
		connectstatus.innerHTML = "Connected";
		connectstatus.style.color = "#00ff00";
		send_cc("40|1");
	};
	connection.onclose = function () {
		// clear stuff and recreate the socket
		connected = 0;
		name_reg = 0;
		lastAttemptedName = "";
		recv_cc("13|0");
		addTextOut("ChatClient", 5, "Reconnecting...", "1");
		connect();
	};
	connection.onmessage = function (messageEvent) {
		recv_cc(messageEvent.data.split("\r\n")[0]);
	};
	// start the ping timer
	var pingInterval = 30;
	if(intervalID) {
		clearInterval(intervalID);
	}
	intervalID = setInterval(pingCount, pingInterval * 1000);
}

function send_cc(data) {
	data += "\r\n"
	connection.send(data);
}

function pingCount() {
	// if the server reports us missing, this will cause a reconnect
	if(name_reg) {
		send_cc("20||^1ping");
	}else if(!name_reg && lastAttemptedName != '') {
		// we might be waiting for a name to free up
		send_cc("10|" + lastAttemptedName);
	}
}

function handleMouse(event) {
	//console.log(event.target + " " + event.clientX + " " + event.clientY);
	if(event.target.className == "mapimg")
		dragElem = document.getElementById("tilemap");
	else if(event.target.className == "chartoken")
		dragElem = event.target;
	else
		return;
	dragElem.startTop = dragElem.style.top?parseInt(dragElem.style.top):0;
	dragElem.startLeft = dragElem.style.left?parseInt(dragElem.style.left):0;
	dragElem.startX = event.clientX;
	dragElem.startY = event.clientY;
	event.preventDefault();
	window.addEventListener("mousemove", handleMove, false);
	window.addEventListener("mouseup", handleUp, false);
	return false;
}

function detectTileCollision(element, position) {
	var collision = 0;
	var points = [[0, 0], [0, 1], [1, 0], [1, 1]];
	for(var point in points) {
		collision |= imgtiles.get(
			[
				position[0] + points[point][0] * element.width, 
				position[1] + points[point][1] * element.height
			]
		).solid;
	}
	return collision;
}

function handleMove(event) {
	var deltaX = (event.clientX - dragElem.startX);
	var deltaY = (event.clientY - dragElem.startY);
	if(dragElem.className == "chartoken") {
		// check for collision
		var startPos = [parseInt(dragElem.startLeft), parseInt(dragElem.startTop)]
		var targetPos = [parseInt(dragElem.startLeft + deltaX), parseInt(dragElem.startTop + deltaY)];
		var targetTile = imgtiles.get(targetPos);
		var elemPos = [startPos[0], startPos[1]];
		// only if we're starting from a nonsolid tile should we apply collision
		if(!imgtiles.get(startPos).solid) {
			// step in each direction until we hit something (not efficient)
			var axesFinished = [0, 0];
			while(!(axesFinished[0] && axesFinished[1])) {
				axesFinished = [0, 0];
				for(var axis = 0; axis < 2; axis++) {
					var move = 0;
					if(elemPos[axis] < targetPos[axis]) {
						elemPos[axis] += move = 1;
					}else if(elemPos[axis] > targetPos[axis]) {
						elemPos[axis] += move = -1;
					}
					if(detectTileCollision(dragElem, elemPos) || vecMag(vecSub(elemPos, startPos)) > maxDragDist) {
						elemPos[axis] -= move;
						axesFinished[axis] |= 1;
					}
					axesFinished[axis] |= elemPos[axis] == targetPos[axis];
				}
			}
			// generate new deltas
			deltaX = elemPos[0] - dragElem.startLeft;
			deltaY = elemPos[1] - dragElem.startTop;
		}
	}
	dragElem.style.left = dragElem.startLeft + deltaX;
	dragElem.style.top = dragElem.startTop + deltaY;
}

function handleUp(event) {
	window.removeEventListener("mousemove", handleMove, false);
	window.removeEventListener("mouseup", handleUp, false);
	if(dragElem.className == "chartoken") {
		sendchat("playerMove|" + dragElem.playerName + "|" + writeVector(dragElem.pos()) + "|" + dragElem.playerLight);
		if(dragElem.playerName.substring(1) == currentName) {
			// then this is us we are digging
			document.cookie = "currentPos=" + writeVector(dragElem.pos()) + ";";
		}
	}else if(parseInt(dragElem.style.top) == parseInt(dragElem.startTop) && parseInt(dragElem.style.left) == parseInt(dragElem.startLeft)) {
		// if we didn't move process a click event
		sendchat("setTile|" + writeVector(event.target.tileCoord) + "|" + palette.value);
	}
}

function findPlayerByName(name) {
	for(player in players) {
		if(players[player].playerName == name)
			return players[player];
	}
	return null;
}

function writeVector(list) {
	return list[0] + "|" + list[1] + "|" + list[2];
}

function vecMag(vec) {
	return Math.sqrt(vec[0] * vec[0] + vec[1] * vec[1]);
}

function vecAdd(vec1, vec2) {
	return [vec1[0] + vec2[0], vec1[1] + vec2[1]];
}

function vecSub(vec1, vec2) {
	return [vec1[0] - vec2[0], vec1[1] - vec2[1]];
}

function readVector(list) {
	var out = new Array(3);
	out[0] = parseInt(list.shift());
	out[1] = parseInt(list.shift());
	out[2] = parseInt(list.shift());
	return out;
}

function showChatMap(event, value) {
	if(event.target.id != 'current') {
		document.getElementById('current').id = null;
		event.target.id = 'current';
	}
	changeRule('.showchat', 'display', value?'block':'none');
	changeRule('.showmap', 'display', value?'none':'block');
}

function handleGridClientCommand(nick, nickflag, message, messageflag) {
	var args = message.split("|");
	while(command = args.shift()) { 
		// allow the chaining of commands in one message 
		// (this should only be used by the server for init messages, 
		// as the server does not currently have the ability to parse chained messages)
		switch(command) {
			case "setGrid":
				// this, very simply, creates a giant table full of images
				if(nickflag > 0) {
					// <dimensions>, <tilesize>, ambient, <playerSpawn>, [tiles]
					mapsize = readVector(args);
					// tilesize
					tilesize = readVector(args);
					changeRule("img.mapimg", "width", tilesize[0] + "px");
					changeRule("img.mapimg", "height", tilesize[1] + "px");
					// light
					ambLight = parseInt(args.shift());
					// player locations are by pixel, not by tile
					spawn = readVector(args);
					var map = document.getElementById("tilemap");
					var child = 0;
					while(map.childNodes.length > players.length) {
						if(map.childNodes[child].className == "chartoken") {
							child++;
						}else{
							map.removeChild(map.childNodes[child]);
						}
					}
					var imgIndex = 0;
					imgtiles = [];
					imgtiles.get = function(pos) {
						// gets a tile object from world coordinates
						var xCo = Math.floor(pos[0] / tilesize[0]);
						var yCo = Math.floor(pos[1] / tilesize[1]);
						if(xCo < mapsize[0] && yCo < mapsize[1] && xCo >= 0 && yCo >= 0) {
							return this[yCo * mapsize[0] + xCo];
						}else{
							return { "solid": 1, "tileCoord": [xCo, yCo, 0] };
						}
					}
					for(var z = 0; z < mapsize[2]; z++) {
						var layer = document.createElement("div");
						layer.id = "maplayer" + z;
						layer.className = "maplayer";
						if(z != spawn[2])
							layer.style.visibility = "hidden";
						for(var y = 0; y < mapsize[1]; y++) {
							for(var x = 0; x < mapsize[0]; x++) {
								var img = document.createElement("img");
								// we use real images because that's the only way we can scale them
								img.imgIndex = parseInt(args.shift());
								img.src = imgurls[img.imgIndex];
								img.className = "mapimg";
								img.tileCoord = [x, y, z];
								img.style.left = x * tilesize[0];
								img.style.top = y * tilesize[1];
								img.solid = img.imgIndex == 17;
								imgtiles.push(img);
								layer.appendChild(img);
							}
						}
						map.appendChild(layer);
					}
					addTextOut("ChatClient", "3", "finished setGrid command", "1");
				}
				break;
			case "setTile":
				if(nickflag > 0) {
					// <coord>, imgindex, solid, transp
					var coord = readVector(args);
					try {
						var img = imgtiles[coord[0] + coord[1] * mapsize[1] + coord[2] * mapsize[1] * mapsize[2]];
						img.src = imgurls[parseInt(args.shift())];
						// we'll deal with those other properties later. <.<
						addTextOut("ChatClient", "3", "finished setTile command", "1");
					} catch(e) {
						addTextOut("ChatClient", "3", "error in setTile command", "1");
					}
				}
				break;
			case "tileImgList":
				if(nickflag > 0) {
					// count, [imgs]
					// ordered list of tiles, indicies operate in this domain
					// message is sent after a file upload
					var imgCount = parseInt(args.shift());
					imgurls = new Array();
					while(palette.childNodes.length > 0)
						palette.removeChild(palette.childNodes[0]);
					for(var i = 0; i < imgCount; i++) {
						// add to the master list
						imgurls.push(args.shift());
						// add to the palette
						var option = document.createElement("option");
						option.value = i;
						var tile = document.createElement("img");
						tile.src = imgurls[i];
						tile.className = "mapimg";
						tile.style.position = "static";
						option.appendChild(tile);
						palette.appendChild(option);
					}
					// add the images to the palette
					addTextOut("ChatClient", "3", "finished tileImgList command", "1");
				}
			case "moveElement":
				// element { imgindex, <position>, light }
				break;
			case "deleteElement":
				// index
				break;
			case "youArePlayer":
				// username
				break;
			case "playerImage":
				// sent and received by the client, logged by the server
				// imageIndex
				break;
			case "players":
				// broadcast to players immediately after logging in
				// image changes are handled over chat
				// total, [username, imgindex, <pos>, light]
				var container = document.getElementById("tilemap");
				while(players.length > 0) {
					container.removeChild(players.shift());
				}
				var total = parseInt(args.shift());
				for(var i = 0; i < total; i++) {
					var playerName = args.shift();
					var imgIndex = args.shift();
					var playerPos = readVector(args);
					var light = args.shift();
					var newPlayer = document.createElement("img");
					newPlayer.move = function (vec) {
						this.style.left = vec[0];
						this.style.top = vec[1];
						this.depth = vec[2];
					}
					newPlayer.pos = function () {
						return [
							this.style.left?parseInt(this.style.left):0, 
							this.style.top?parseInt(this.style.top):0, 
							this.depth
						];
					}
					newPlayer.src = imgurls[imgIndex];
					newPlayer.style.position = "absolute";
					newPlayer.className = "chartoken";
					newPlayer.move(playerPos);
					newPlayer.playerName = playerName;
					newPlayer.playerLight = light;
					players.push(newPlayer);
					container.appendChild(newPlayer);
				}
				refreshGUIUserList(userstring);
				break;
			case "playerMove":
				// name, <pos>, light
				var playerName = args.shift();
				var player = findPlayerByName(playerName);
				if(player) {
					player.move(readVector(args));
					player.playerLight = args.shift();
				}else{
					//console.log("could not find player: " + playerName);
				}
				/*
				if(playerName == currentName) {
					updateGridVisibility(player);
				}
				updateElementVisibility(player);
				*/
				break;
			case "setTurn":
				// time, turn, maxMoveDist
				//maxMoveDist = parseInt(args.shift());
				break;
		}
	}
}

function recv_cc(line) {
	if(line.length > 0) {
		command = line.substring(0, 2);
		pipelist = line.split("|");
		switch(command) {
			case "31":
				if(!isUserIgnored(pipelist[1])) {
					user = pipelist[1].split(",")[0]
					nickflag = user.substring(0, 1);
					nick = user.substring(1, user.length);
					message = line.substring(pipelist[0].length + pipelist[1].length + 2, line.length);
					messageflag = message.substring(1, 2);
					message = message.substring(2, message.length);
					addTextOut(nick, nickflag, message, messageflag);
					handleGridClientCommand(nick, nickflag, message, messageflag);
				}
			break;
			case "21":
				if(!isUserIgnored(pipelist[1])) {
					user = pipelist[1].split(",")[0]
					nickflag = user.substring(0, 1);
					nick = user.substring(1, user.length);
					message = line.substring(pipelist[0].length + pipelist[1].length + 2, line.length);
					messageflag = message.substring(1, 2);
					message = message.substring(2, message.length);
					if(message == "!version") {
						versionReply(user);
					}else{
						foundwindow = 0;
						for(j = 0; j < pmwindows.length; j++) {
							if(pmwindows[j]) {
								if(user == pmwindows[j].user) {
									if(messageflag == "0") {
										messageflag = 1;
									}
									pmwindows[j].addTextOut(nick, nickflag, message, messageflag);
									foundwindow = 1;
								}
							}
						}
						if(foundwindow == 0) {
							addTextOut(nick, nickflag, message, messageflag);
						}
					}
					handleGridClientCommand(nick, nickflag, message, messageflag);
				}
			break;
			case "35":
				userstring = line.substring(3, line.length).split("|");
				refreshGUIUserList(userstring);
			break;
			case "40":
				addTextOut("ChatServer", 2, line.substring(4, line.length), "1");
				// now if there was a name cookie, we can use it
				if((lastSessionName)&&(name_reg == 0)) {
					if(lastAttemptedName != lastSessionName) {
						lastAttemptedName = lastSessionName;
						// this used to be a setTimeout with a time of 1000ms, this doesn't really change anything
						// to protect against some obscure error where the browser is frozen by this command
						// I shouldn't have to do this, but I have no idea what the hell firefox is thinking
						setname(lastSessionName);
					}
				}
			break;
			case "11":
				// name accepted message
				name_reg = 1;
				currentName = lastAttemptedName;
				// in case the user gets disconnected this session
				lastSessionName = currentName;
				// on a successful name set, we set the name cookie so we can autoname ourselves on the next visit
				today = new Date();
				// store the cookie for a week
				expire_date = new Date(today.getTime() + (7 * 1000 * 60 * 60 * 24));
				expire_string = expire_date.toGMTString();
				document.cookie = "ccname=" + escape(currentName) + ";path=/;expires=" + expire_string;
				// now set our position if we are able
				if(document.cookie.split("currentPos=").length > 1) {
					console.log("about to try to set playerpos from cookie");
					var lastPos = unescape(document.cookie.split("currentPos=")[1].split(";")[0]);
					console.log("sending setchat");
					// note that this defaults the player's light to 0, this might need to be fixed so BIG NOTE HERE
					// also assumes that player is level 0, which is an unsafe assumption. not sure how to get around it right now
					sendchat("playerMove|0" + currentName + "|" + lastPos + "|0");
					console.log("sent chat");
				}
			break;
			case "10":
				// name rejected message
				addTextOut("ChatClient", 3, "Server Rejected Name", "1");
			break;
			case "70":
				// append the ignoring user to the ignore lsit
				ignoreList[ignoreList.length] = pipelist[1];
			break;
			case "13":
				// the auth acceptance message
				level = parseInt(pipelist[1]);
				authKey = pipelist[2];
				if(level > 1) {
					changeRule(".admin", "visibility", "visible");
					changeRule(".op", "visibility", "visible");
				}else if(level > 0) {
					changeRule(".admin", "visibility", "hidden");
					changeRule(".op", "visibility", "visible");
				}else{
					changeRule(".admin", "visibility", "hidden");
					changeRule(".op", "visibility", "hidden");
				}
				refreshGUIUserList(userstring);
				document.getElementById("uploadForm").action = "/file-upload?authkey=" + authKey;
			break;
			default:
				addTextOut("ChatServer", 2, line, "1");
		}
	}
}

function changeRule(name, property, value) {
	var rules = new Array();
	for(sheet = 0; sheet < document.styleSheets.length; sheet++) {
		try {
			if(document.styleSheets[sheet].cssRules) {
				rules = document.styleSheets[sheet].cssRules;
			}else if(document.styleSheets[sheet].rules) {
				rules = document.styleSheets[sheet].rules;
			}
		}catch(exception){
			continue;
		}
		for(rule = 0; rule < rules.length; rule++) {
			if(rules[rule].selectorText == name) {
				rules[rule].style.setProperty(property, value, null);
			}
		}
	}
}

function escHTML(string) {
	return string.split("&").join("&amp;").split("<").join("&lt;").split(">").join("&gt;");
}

function addElement(parent, childtype, childtext, childclass, href) {
	child = document.createElement(childtype);
	if(href) {
		child.href = href;
		child.target = "_blank"; // this makes the link open in a new window
	}
	if(childtype != "br") {
		child.appendChild(document.createTextNode(childtext.replace(/ /g, '\u00a0')));
	}
	child.className = childclass;
	if(parent) {
		parent.appendChild(child);
		return parent;
	}else{
		return child;
	}
}

function addTextOut(nick, nickflag, message, messageflag) {
	// int for list access
	nickflag = parseInt(nickflag);
	now = new Date();
	// start from the beginning
	newline = addElement(0, "span", "", "", 0);
	newline = addElement(newline, "span", "[" + intPlaces(now.getHours(), 2) + ":" + intPlaces(now.getMinutes(), 2) + "] ", "timestamp", 0);
	if(messageflag == "0") {
		newline = addElement(newline, "span", "Private message from ", "pretext", 0);
	}else if(messageflag == "2") {
		newline = addElement(newline, "span", "\\\\\\\\\\", "server", 0);
	}else if(messageflag == "3") {
		newline = addElement(newline, "span", "/////", "server", 0);
	}
	newline = addElement(newline, "span", "[" + nick + "] ", styles[nickflag], 0);
	if((message.substring(0, 1) == "*")&&(message.substring(message.length - 1, message.length) == "*")) {
		msgclass = 'action';
	}else{
		msgclass = 'msg';
	}
	var wordlist = message.split(' ');
	var wordline = "";
	for(var i = 0; i < wordlist.length; i++) {
		if((wordlist[i].substring(0, 7) == "http://")
		||(wordlist[i].substring(0, 8) == "https://")
		||(wordlist[i].substring(0, 6) == "ftp://")) {
			if(wordline != "") {
				newline = addElement(newline, "span", wordline, msgclass, 0);
				wordline = "";
			}
			newline = addElement(newline, "a", wordlist[i], msgclass, wordlist[i]);
			wordline += " ";
		}else{
			wordline += wordlist[i] + " ";
		}
	}
	newline = addElement(newline, "span", wordline.substring(0, wordline.length - 1), msgclass, 0);
	if(messageflag == "2") {
		newline = addElement(newline, "span", "/////", "server", 0);
	}else if(messageflag == "3") {
		newline = addElement(newline, "span", "\\\\\\\\\\", "server", 0);
	}
	newline = addElement(newline, "br", "", "", 0);
	textout.insertBefore(newline, textout.childNodes[0]);
	startFlash();
}

function intPlaces(integer, places) {
	intstring = String(integer);
	while(intstring.length < places) {
		intstring = "0" + intstring;
	}
	return intstring;
}

function flashTitle() {
	if(flashstate == 1) {
		flashstate = 0;
		document.title = title;
	}else if(flashstate == 0) {
		flashstate = 1;
		document.title = "*" + title + "*";
	}else{
		document.title = title;
	}
	setTimeout(flashTitle, 1000);
}

function startFlash() {
	if(flashstate != -2) {
		flashstate = 1;
	}
}

function disableFlash() {
	flashstate = -2;
}

function enableFlash() {
	flashstate = -1;
}

function refreshGUIUserList(userstring) {
	basestring = "";
	cyanstring = "";
	while(wholist.length > 0) {
		// clear the list
		wholist.remove(0);
	}
	for(var i = 0; i < userstring.length; i++) {
		if(!isUserIgnored(userstring[i])) {
			user = userstring[i].split(",")[0];
			nickflag = parseInt(user.substring(0, 1));
			// we got our data, now we create an element
			var newoption = document.createElement("option");
			newoption.text = escHTML(user.substring(1));
			newoption.value = user;
			newoption.className = styles[nickflag];
			// add the player images, if we have them
			var player = findPlayerByName(user);
			if(player) {
				var newplayerimg = document.createElement("img");
				newplayerimg.src = player.src;
				newoption.appendChild(newplayerimg);
			}
			try {
				// standards compliant
				wholist.add(newoption, null);
			}catch (exception) {
				// IE is stupid
				wholist.add(newoption);
			}
		}
	}
}

function sendchat(message) {
	lines = message.split("\n")
	for(var line = 0; line < lines.length; line++) {
		send_cc("30|^1" + lines[line]);
	}
}

function setname(name) {
	if(name.length > 0) {
		lastAttemptedName = name;
		send_cc("10|" + name);
	}else{
		addTextOut("ChatClient", 3, "Name Not Specified", "1");
	}
}

function sendprivate(target, message) {
	if(wholist.value.length > 0) {
		lines = message.split("\n")
		for(line = 0; line < lines.length; line++) {
			send_cc("20|" + target + "|^1" + lines[line]);
			addTextOut("ChatClient", 5, "sent private message to: [" + target.substring(1, target.length) + "] " + lines[line], "1");
		}
	}else{
		addTextOut("ChatClient", 3, "Target Not Specified", "1");
	}
}

function openprivate(target) {
	if(target.length > 0) {
		new_window = window.open("PMClient.html");
		pmwindows[pmwindows.length] = new_window;
		lastPMWindowOpenUser = target;
	}else{
		addTextOut("ChatClient", 3, "Target Not Specified", "1");
	}
}

function windowOpened(new_window) {
	new_window.windowInit(lastPMWindowOpenUser);
	lastPMWindowOpenUser = "";
}

function ignoreUser(target) {
	for(user = 0; user < userstring.length; user++) {
		iphash = userstring[user].split(",")[1];
		if(userstring[user].split(",")[0] == target) {
			ignoreList[ignoreList.length] = userstring[user];
			addTextOut("ChatClient", 3, "You are now ignoring [" + target.substring(1, target.length) + "] and all their aliases from address " + iphash, 1);
			refreshGUIUserList(userstring);
			send_cc("70|" + target);
			return;
		}
	}
}

function isUserIgnored(fulluser) {
	if(level < 2) {
		for(ignored = 0; ignored < ignoreList.length; ignored++) {
			if(fulluser.split(",")[1] == ignoreList[ignored].split(",")[1]) {
				return 1;
			}
		}
	}
	return 0;
}

function killPMWindows() {
	for(var i = 0; i < pmwindows.length; i++) {
		if(pmwindows[i]) {
			pmwindows[i].shutdown = 1;
			pmwindows[i].close();
		}
	}
}

function versionReply(target) {
	send_cc("20|" + target + "|^1" + client_name);
	send_cc("20|" + target + "|^1" + navigator.userAgent || "unknown browser");
	addTextOut("ChatClient", 3, "[" + target.substring(1, target.length) + "] Requested version info", "1")
}

function disconnect() {
	send_cc("15");
	name_reg = 0;
}

function chatenter(event) {
	if((event.which == 13)||(event.charCode == 13)||(event.keyCode == 13)) {
		if(textin.value.substring(0, 5) == "/auth") {
			send_cc("12|" + textin.value.split(" ")[1]);
		}else if(textin.value.substring(0, 3) == "/me") {
			sendchat("*" + textin.value.substring(4, textin.value.length) + "*");
		}else if(textin.value.substring(0, 11) == "/creategrid") {
			var args = textin.value.split(" ");
			args.shift();
			// <dimensions>, <tilesize>, ambient, <playerSpawn>, [tiles]
			var x = parseInt(args.shift());
			var y = parseInt(args.shift());
			var z = parseInt(args.shift());
			var outstring = "setGrid|" + writeVector([x, y, z]) + "|64|64|0|1|0|0|0";
			for(var i = 0; i < x * y * z; i++) {
				outstring += "|6"
			}
			sendchat(outstring);
		}else{
			if(name_reg) {
				sendchat(textin.value);
			}else{
				setname(textin.value);
			}
		}
		textin.value = "";
	}
}

function setlevel(user, level) {
	send_cc("50|" + user + "|" + level);
}

function setmylevel(level) {
	send_cc("53|" + level);
}

function kickuser(user) {
	send_cc("51|" + user);
}

function clearbans() {
	send_cc("52");
}

function servmsg(message) {
	send_cc("60|" + message);
}

function shutdown() {
	send_cc("80");
}

function toggletimes() {
	if(timestamps.checked) {
		vis = "inline";
	}else{
		vis = "none";
	}
	changeRule(".timestamp", "display", vis);
}
