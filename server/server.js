const path = require("path");

const express = require("express");
const multer  = require("multer");
const zmq = require("zmq");
const uuidV4 = require("uuid/v4");

// Initialize common data structures

// TODO: think about using TTL (time-to-live) later
var routing_queue = {};

// Initialize zmq
var sock = zmq.socket("dealer");

sock.connect("tcp://localhost:2411");

var artm_topics = null;
sock.on("message", function (reply) {
    reply = JSON.parse(reply);
    if (reply.act == "get_topics") {
        artm_topics = reply.data;
    } else if (reply.act == "get_recommendations" || reply.act == "get_documents" ||
               reply.act == "get_document" || reply.act == "transform_doc") {
        var res = routing_queue[reply.id];
        delete routing_queue[reply.id];
        res.send(reply.data);
    }
});

sock.send(JSON.stringify({"act": "get_topics"}));

// Initialize express
const app = express();
app.use(express.static("static"));

// TODO: temporary upload path! change later in production
var UPLOAD_PATH = path.join(__dirname, "uploads/")
var upload = multer({dest: UPLOAD_PATH})

app.get("/get-topics", function (req, res) {
    if (artm_topics) {
        res.send(artm_topics);
    } else {
        // TODO: error handling
        res.send("error -- data not ready");
    }
});

app.get("/get-documents", function (req, res) {
    var topic_id = req.query.topic_id;
    var uuid = uuidV4();
    routing_queue[uuid] = res;
    sock.send(JSON.stringify({
        "act": "get_documents",
        "topic_id": topic_id,
        "id": uuid,
    }));
});

app.get("/get-document", function (req, res) {
    var doc_id = req.query.doc_id;
    var uuid = uuidV4();
    routing_queue[uuid] = res;
    sock.send(JSON.stringify({
        "act": "get_document",
        "doc_id": doc_id,
        "id": uuid,
    }));
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

app.post("/transform-doc", upload.single("doc"), function (req, res, next) {
    var fileObj = req.file;

    if (fileObj.mimetype != "text/plain") {
        errorMsg = "unknown filetype -- " + fileObj.mimetype;
        res.send(errorMsg);
        return;
    }

    // Make request to ARTM_bridge
    var uuid = uuidV4();
    routing_queue[uuid] = res;
    sock.send(JSON.stringify({
        "act": "transform_doc",
        "doc_path": fileObj.path,
        "id": uuid,
    }));
});

var server = app.listen(3000, function () {
    var host = server.address().address;
    var port = server.address().port;

    console.log("Example app listening at http://%s:%s", host, port);
});
