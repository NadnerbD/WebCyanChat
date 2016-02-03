// user and parentWindow will be defined by the main client
// we need an on-close method that will notify the main client if the window is closed
// (as well as an inverse to close pm windows when the client is removed
styles = ['normal', 'cyan', 'server', 'client', 'guest', 'client'];
flashstate = 0;
enableflash = 0;
shutdown = 0;
flashloop = 0;
user = "";

function init() {
	textin = document.getElementById("input");
	textout = document.getElementById("output");
	try {
		// standards compliant
		window.addEventListener("focus", disableFlash, false);
		window.addEventListener("blur", enableFlash, false);
		window.addEventListener("unload", removePMEntry, false);
	}catch(exception){
		// IE is stupid
		window.attachEvent("onunload", removePMEntry);
		window.attachEvent("onfocus", disableFlash);
		window.attachEvent("onblur", enableFlash);
	}
	if(window.opener) {
		parentWindow = window.opener;
		window.opener.windowOpened(window);
	}else{
		window.close()
	}
}

function windowInit(target) {
	user = target;
	document.title = "Private chat with [" + user.substr(1, user.length) + "]";
	title = "Private chat with [" + user.substr(1, user.length) + "]";
	if(flashloop == 0) {
		flashloop = 1;
		setTimeout(flashTitle, 1000);
	}
}

function removePMEntry() {
	if(!shutdown) {
		for(i = 0; i < parentWindow.pmwindows.length; i++) {
			if(parentWindow.pmwindows[i] == window) {
				parentWindow.pmwindows[i] = false;
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
	}
	if(childtype != "br") {
		child.appendChild(document.createTextNode(childtext));
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
	newline = document.createElement("p");
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

function chatenter(event) {
	if((event.which == 13)||(event.charCode == 13)||(event.keyCode == 13)) {
		if(textin.value.substring(0, 3) == "/me")
			textin.value = "*" + textin.value.substring(4, textin.value.length) + "*";
		parentWindow.send_cc("20|" + user + "|^1" + textin.value);
		addTextOut(parentWindow.currentName, 0, textin.value, "1");
		textin.value = "";
	}
}
