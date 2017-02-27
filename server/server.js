var express = require("express");
var zmq = require("zmq");

// Initialize zmq
var sock = zmq.socket("req");

sock.connect("tcp://127.0.0.1:2411");

var artm_topics = null;
sock.on("message", function (reply) {
    reply = JSON.parse(reply);
    if (reply.act == "get_topics") {
        artm_topics = reply.data;
    }
});

sock.send("{\"act\":\"get_topics\"}");

// Initialize express
var app = express();
app.use(express.static("static"));

app.get("/get-topics", function(req, res) {
    if (artm_topics) {
        res.send(artm_topics);
    } else {
        // TODO: error handling
        res.send("error -- data not ready");
    }
});

var server = app.listen(3000, function() {
    var host = server.address().address;
    var port = server.address().port;

    console.log("Example app listening at http://%s:%s", host, port);
});
