// this uses long-polling to simulate a WebSocket if one is not available

function XmlHttpSock(server_url) {
	var sid = "0"; // session id, identifies us to the server
	var xmlhttp_recv; // always held open, occasionally pinged
	var xmlhttp_send; // only used when sending messages
	var self = this;
	// constants
	this.CONNECTING = 0;
	this.OPEN = 1;
	this.CLOSED = 2;
	// public vars
	this.readyState = 0;
	this.bufferedAmount = 0;
	// handler functions
	this.onopen = function () {};
	this.onmessage = function () {};
	this.onclose = function () {};
	// member functions
	this.send = send_xml;
	this.disconnect = function () {};
	
	// initialize the connection
	send_xml("");
	
	function send_xml_recv(data) {
		sdata = data;
		if(window.XMLHttpRequest) {
			xmlhttp_recv = new XMLHttpRequest();
		}else if(window.ActiveXObject) {
			xmlhttp_recv = new ActiveXObject("Microsoft.XMLHTTP");
		}else{
			self.readyState = self.CLOSED;
			self.onclose();
		}
		xmlhttp_recv.onreadystatechange = recv_xml;
		xmlhttp_recv.open("POST", server_url + "?sid=" + sid + "&action=recv", true);
		xmlhttp_recv.send(sdata);
	}
	
	function send_xml(data) {
		sdata = data;
		if(window.XMLHttpRequest) {
			xmlhttp_send = new XMLHttpRequest();
		}else if(window.ActiveXObject) {
			xmlhttp_send = new ActiveXObject("Microsoft.XMLHTTP");
		}else{
			self.readyState = self.CLOSED;
			self.onclose();
		}
		xmlhttp_send.onreadystatechange = recv_ack;
		xmlhttp_send.open("POST", server_url + "?sid=" + sid + "&action=send", true);
		xmlhttp_send.send(sdata);
	}
	
	function recv_xml() {
		if(xmlhttp_recv.readyState == 4) { //it's loaded
			if(xmlhttp_recv.status == "200") { //http success
				if(xmlhttp_recv.responseText != "") {
					var data = xmlhttp_recv.responseText.split("\r\n");
					var recv_sid = data[0];
					if(data[1] != "PING") {
						// we have useful data
						for(var i = 1; i < data.length; i++) {
							self.onmessage({ "data": data[i] });
						}
					}
					send_xml_recv("PONG"); // after a receive, return a pong
				}
			}else if(xmlhttp_recv.status == 404) {
				// our sid wasn't found, the connection has been lost
				self.readyState = self.CLOSED;
				self.onclose();
			}
		}
	}
	
	function recv_ack() {
		if(xmlhttp_send.readyState == 4) { //it's loaded
			if(xmlhttp_send.status == "200") { //http success
				var ack_sid = xmlhttp_send.responseText;
				if(sid == "0") { // first connect, success!
					sid = ack_sid;
					self.readyState = self.OPEN;
					self.onopen();
					// start the receiving line
					send_xml_recv("PONG");
				}
			}else if(xmlhttp_send.status == 404) {
				// our sid wasn't found, the connection has been lost
				self.readyState = self.CLOSED;
				self.onclose();
			}
		}
	}
}
