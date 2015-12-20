// the control script goes here
var styles = ['normal', 'cyan', 'server', 'client', 'guest', 'client'];

var version = "0.14";
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
var bounceKey = "";
var bounceBursting = 0;
var lastPMWindowOpenUser = "";

function init() {
	// get all the global things
	namein = document.getElementById("nameinput");
	textin = document.getElementById("input");
	textout = document.getElementById("output");
	wholist = document.getElementById("wholistid");
	cyanlist = document.getElementById("cyanlistid");
	linkbutton = document.getElementById("linkbutton");
	connectstatus = document.getElementById("connectstatusid");
	timestamps = document.getElementById("timestampsid");
	bounceEnable = document.getElementById("bounceid");
	// disable the buttons
	whoSelChanged();
	// fetch previous settings
	lastSessionName = getCookie("ccname");
	bounceKey = getCookie("bouncekey");
	title = document.title;
	try {
		// standards compliant
		window.addEventListener("focus", disableFlash, false);
		window.addEventListener("blur", enableFlash, false);
		window.addEventListener("unload", killPMWindows, false);
	}catch(exception){
		// this is only for IE
		window.attachEvent("onfocus", disableFlash);
		window.attachEvent("onblur", enableFlash);
		window.attachEvent("onunload", killPMWindows);
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
		if(bounceKey) {
			// if we have a bounce-reconnect cookie
			bounceEnable.checked = true;
			send_cc("102|" + bounceKey);
		}else{
			send_cc("40|1");
			// we push our font now
			send_cc("201|" + localStorage.getItem("font_image") || "");
		}
	};
	connection.onclose = function () {
		// clear stuff and recreate the socket
		connected = 0;
		name_reg = 0;
		lastAttemptedName = "";
		recv_cc("13|0");
		addTextOut("ChatClient", 5, "Reconnecting...", "1");
		// wait a few seconds before reconnecting to avoid the DOS attack style reconnect
		setTimeout(connect, 3000);
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
	data += "\r\n";
	connection.send(data);
}

function pingCount() {
	// if the server reports us missing, this will cause a reconnect
	if(name_reg) {
		//send_cc("20||^1ping");
	}else if(lastAttemptedName != '') {
		// we might be waiting for a name to free up
		setname(lastAttemptedName);
	}
}

function recv_cc(line) {
	if(line.length > 0) {
		command = line.split("|")[0];
		pipelist = line.split("|");
		switch(command) {
			case "31":
				if(!isUserIgnored(pipelist[1])) {
					userdata = pipelist[1].split(",")
					user = userdata[0]
					userid = userdata.length == 3 ? userdata[2] : "0";
					nickflag = user.substring(0, 1);
					nick = user.substring(1, user.length);
					message = line.substring(pipelist[0].length + pipelist[1].length + 2, line.length);
					messageflag = message.substring(1, 2);
					message = message.substring(2, message.length);
					addTextOut(nick, nickflag, message, messageflag, userid);
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
				}
			break;
			case "35":
				userstring = line.substring(3, line.length).split("|");
				refreshGUIUserList(userstring);
				whoSelChanged();
			break;
			case "40":
				addTextOut("ChatServer", 2, line.substring(4, line.length), "1");
				// now if there was a name cookie, we can use it
				if((lastSessionName)&&(name_reg == 0)) {
					// prevents multiple attempts to register name (one for each 40)
					if(lastAttemptedName != lastSessionName) {
						setname(lastSessionName);
					}
				}
			break;
			case "11":
				// name accepted message
				name_reg = 1;
				linkbutton.value = 'Leave';
				document.getElementById("join_floater").style.display = "none";
				currentName = lastAttemptedName;
				// in case the user gets disconnected this session
				lastSessionName = currentName;
				// on a successful name set, we set the name cookie so we can autoname ourselves on the next visit
				// store the cookie for a week
				setCookie("ccname", currentName);
			break;
			case "10":
				// name rejected message
				addTextOut("ChatClient", 3, "Server Rejected Name", "1");
				if(!name_reg)
					namein.disabled = false;
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
			break;
			case "101":
				// bounce key response
				// store the cookie for a week
				bounceKey = pipelist[1];
				setCookie("bouncekey", bounceKey);
			break;
			case "102":
				// bounce connect reject
				send_cc("100"); // bounce key request
				send_cc("40|1"); // log in normally
				// we should delete the cookie so that we don't try to use it again later
				deleteCookie("bouncekey");
				bounceKey = "";
			break;
			case "103":
				// bounce connect accept
				bounceBursting = 1;
				currentName = pipelist[1].substring(1);
				// refresh the cookies so they don't expire
				setCookie("ccname", currentName);
				setCookie("bouncekey", bounceKey);
				lastSessionName = currentName;
				namein.value = currentName;
				namein.disabled = true;
				name_reg = true;
				linkbutton.value = 'Leave';
				document.getElementById("join_floater").style.display = "none";
				textin.focus();
			break;
			case "104":
				// bounce burst end
				bounceBursting = 0;
			break;
			case "200":
				// fonts for all users
				var sheet = document.getElementById("cursive-data-style").sheet;
				while(pipelist.length > 3) {
					var av = pipelist.pop();
					var ft = pipelist.pop();
					var id = pipelist.pop();
					sheet.insertRule(".l-uid-" + id + " .l { background-image: url(" + ft + "); }", 0);
					sheet.insertRule(".l-uid-" + id + " .a { background-image: url(" + av + "); }", 0);
				}
			case "201":
				// set a font for a user
				changeRule(".l-uid-" + pipelist[1] + " .l", "background-image", "url(" + pipelist[2] + ")");
			break;
			case "202":
				// set avatar for a user
				changeRule(".l-uid-" + pipelist[1] + " .a", "background-image", "url(" + pipelist[2] + ")");
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
				return;
			}
		}
	}
	// if we get here, we failed to find a rule to change, so we need to add a rule
	document.getElementById("cursive-data-style").sheet.insertRule(name + " {" + property + ": " + value + "; }", 0);
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
		child.appendChild(createString(childtext.replace(/ /g, '\u00a0')));
	}
	child.className = childclass;
	if(parent) {
		parent.appendChild(child);
		return parent;
	}else{
		return child;
	}
}

function addTextOut(nick, nickflag, message, messageflag, userid) {
	// int for list access
	nickflag = parseInt(nickflag);
	now = new Date();
	// start from the beginning
	newline = addElement(0, "p", "", userid ? "l-uid-" + userid : "l-uid-0", 0);
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
	// check if we'll need to autoscroll
	var autoscroll = textout.scrollTop == textout.scrollTopMax;
	textout.appendChild(newline);
	if(autoscroll) {
		textout.scrollTop = textout.scrollTopMax;
	}
	startFlash();
}

function setCookie(name, value) {
	// cookies are set to expire in one week
	var today = new Date();
	expire_date = new Date(today.getTime() + (7 * 1000 * 60 * 60 * 24));
	expire_string = expire_date.toGMTString();
	document.cookie = name + "=" + escape(value) + ";path=/;expires=" + expire_string;
}

function getCookie(name) {
	// first check if the cookie exists
	if(document.cookie.split(name + "=").length > 1) {
		// if so, extract it
		return unescape(document.cookie.split(name + "=")[1].split(";")[0]);
	}else{
		// otherwise return an empty string
		return "";
	}
}

function deleteCookie(name) {
	// we delete cookies by setting their expiry date to the past
	today = new Date();
	expire_string = new Date(today.getTime() - 1).toGMTString();
	document.cookie = name + "=;path=/;expires=" + expire_string
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
		namein.value = name;
		namein.disabled = true;
		textin.focus();
	}else{
		addTextOut("ChatClient", 3, "Name Not Specified", "1");
	}
}

function sendprivate(target, message) {
	if(target.length > 0) {
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
	if(!bounceBursting) {
		send_cc("20|" + target + "|^1" + client_name);
		send_cc("20|" + target + "|^1" + navigator.userAgent || "unknown browser");
		//send_cc("20|" + target + "|^1Connection is a " + connection.constructor.toString().match(/function\s*(\w+)/)[1]);
		// safari doesn't return anything useful for the constructor name
		if(window.WebSocket) {
			send_cc("20|" + target + "|^1Connection is a WebSocket");
		}else{
			send_cc("20|" + target + "|^1Connection is a XmlHttpSock");
		}
	}
	addTextOut("ChatClient", 3, "[" + target.substring(1, target.length) + "] Requested version info", "1")
}

function disconnect() {
	send_cc("15");
	name_reg = 0;
	linkbutton.value = 'Join';
	namein.disabled = false;
	// this will prevent the client from logging us back in
	lastAttemptedName = '';
}

function whoSelChanged() {
	var disabled = wholist.value.length == 0;
	document.getElementById("spbtn").disabled = disabled;
	document.getElementById("pcbtn").disabled = disabled;
	document.getElementById("ibtn").disabled = disabled;
}

function nameenter(event) {
	if((event.which == 13)||(event.charCode == 13)||(event.keyCode == 13)) {
		if(!name_reg)
			setname(namein.value);
	}
}

function chatenter(event) {
	if((event.which == 13)||(event.charCode == 13)||(event.keyCode == 13)) {
		if(textin.value.substring(0, 5) == "/auth") {
			send_cc("12|" + textin.value.split(" ")[1]);
		}else if(textin.value.substring(0, 3) == "/me") {
			sendchat("*" + textin.value.substring(4, textin.value.length) + "*");
		}else if(textin.value.substring(0, 5) == "/nick") {
			setname(textin.value.substring(6, textin.value.length));
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

function reload() {
	send_cc("90");
}

function toggletimes() {
	if(timestamps.checked) {
		vis = "inline";
	}else{
		vis = "none";
	}
	changeRule(".timestamp", "display", vis);
}

function togglebounce() {
	if(bounceEnable.checked) {
		send_cc("100"); // bounce key request
	}else{
		bounceKey = "";
		deleteCookie("bouncekey");
		send_cc("104"); // disable bounce request
	}
}
