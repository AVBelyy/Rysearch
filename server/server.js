const path = require("path");

const express = require("express");
const multer  = require("multer");
const zmq = require("zmq");
const uuidV4 = require("uuid/v4");
const bodyParser = require("body-parser");

// Initialize common data structures

// TODO: think about using TTL (time-to-live) later
var routingQueue = {};

// Initialize zmq
var sock = zmq.socket("dealer");

function sendToSock (res, msg) {
    if (typeof msg !== "object" || msg === null) {
        return false;
    }
    var uuid = uuidV4();
    routingQueue[uuid] = res;
    msg["id"] = uuid;
    return sock.send(JSON.stringify(msg)) === 0;
}

sock.connect("tcp://localhost:2411");

var artmTopics = null;
sock.on("message", function (reply) {
    reply = JSON.parse(reply);
    if (reply.act == "get_topics") {
        artmTopics = reply.data;
    } else if (reply.act == "recommend_docs" || reply.act == "get_documents" ||
               reply.act == "get_document" || reply.act == "transform_doc" ||
               reply.act == "get_next_assessment" || reply.act == "assess_document") {
        var res = routingQueue[reply.id];
        delete routingQueue[reply.id];
        res.send(reply.data);
    }
});

sock.send(JSON.stringify({"act": "get_topics"}));

// Initialize express
const app = express();
app.use(express.static("static"));
app.use(bodyParser.urlencoded({ extended: true }));

// TODO: temporary upload path! change later in production
var UPLOAD_PATH = path.join(__dirname, "uploads/")
var upload = multer({dest: UPLOAD_PATH})

app.get("/get-topics", function (req, res) {
    if (artmTopics) {
        res.send(artmTopics);
    } else {
        // TODO: error handling
        res.send("error -- data not ready");
    }
});

app.get("/get-documents", function (req, res) {
    var topicId = req.query.topic_id;
    sendToSock(res, { "act": "get_documents", "topic_id": topicId });
});

app.get("/get-document", function (req, res) {
    var docId = req.query.doc_id;
    sendToSock(res, { "act": "get_document", "doc_id": docId });
});

app.get("/recommend-docs", function (req, res) {
    var docId = req.query.doc_id;
    sendToSock(res, { "act": "recommend_docs", "doc_id": docId });
});

app.post("/transform-doc", upload.single("doc"), function (req, res, next) {
    var fileObj = req.file;

    if (fileObj.mimetype != "text/plain") {
        errorMsg = "unknown filetype -- " + fileObj.mimetype;
        res.send(errorMsg);
        return;
    }

    // Make request to ARTM_bridge
    sendToSock(res, { "act": "transform_doc", "doc_path": fileObj.path });
});

app.get("/get-next-assessment", function (req, res) {
    var assessorId = parseInt(req.query.assessor_id);
    var assessorsCnt = parseInt(req.query.assessors_cnt);
    var collectionName = req.query.collection_name;
    sendToSock(res, {"act": "get_next_assessment",
                     "collection_name": collectionName,
                     "assessor_id": assessorId,
                     "assessors_cnt": assessorsCnt});
});

app.post("/assess-document", function (req, res) {
    var docId = req.body.doc_id;
    var isRelevant = req.body.is_relevant === "true";
    sendToSock(res, {"act": "assess_document",
                     "doc_id": docId,
                     "is_relevant": isRelevant});
});

var server = app.listen(3000, function () {
    var host = server.address().address;
    var port = server.address().port;

    console.log("Example app listening at http://%s:%s", host, port);
});
