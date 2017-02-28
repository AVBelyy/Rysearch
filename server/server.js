var express = require("express");
var zmq = require("zmq");
var uuidV4 = require("uuid/v4");

// Initialize common data structures

// TODO: think about using TTL (time-to-live) later
var routing_queue = {};

// Initialize zmq
var sock = zmq.socket("req");

sock.connect("tcp://127.0.0.1:2411");

var artm_topics = null;
sock.on("message", function (reply) {
    reply = JSON.parse(reply);
    if (reply.act == "get_topics") {
        artm_topics = reply.data;
    } else if (reply.act == "get_recommendations") {
        var res = routing_queue[reply.id];
        delete routing_queue[reply.id];
        res.send(reply.data);
    }
});

sock.send(JSON.stringify({"act": "get_topics"}));

// Initialize express
var app = express();
app.use(express.static("static"));

app.get("/get-topics", function (req, res) {
    if (artm_topics) {
        res.send(artm_topics);
    } else {
        // TODO: error handling
        res.send("error -- data not ready");
    }
});

app.get("/get-recommendations", function (req, res) {
    var doc_id = req.query.doc_id;
    var uuid = uuidV4();
    routing_queue[uuid] = res;
    sock.send(JSON.stringify({
        "act": "get_recommendations",
        "doc_id": doc_id,
        "id": uuid,
    }));
});

var server = app.listen(3000, function () {
    var host = server.address().address;
    var port = server.address().port;

    console.log("Example app listening at http://%s:%s", host, port);
});
