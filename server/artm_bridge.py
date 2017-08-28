import numpy as np
import pandas as pd
import random
import pickle
import json
import zmq
import regex
import tempfile
import traceback
import glob
import os

from parsers import arbitrary, text_utils
from datetime import datetime

import artm
import artm_lib


MODEL_PATH = "hartm"

ZMQ_BACKEND_PORT = 2511

EMPTY, UP, DOWN = b"", b"UP", b"DOWN"


class BridgeParamError(ValueError):
    def __init__(self, message):
        self.message = message


def rm_flat_dir(dir_path):
    for file_path in glob.glob(os.path.join(dir_path, "*")):
        os.remove(file_path)
    os.rmdir(dir_path)

def process_msg(message):
    if message["act"] == "get_topics":
        response = artm_bridge.model.topics
    elif message["act"] == "get_documents":
        topic_id = message["topic_id"]
        offset = message["offset"]
        limit = message["limit"]
        if type(topic_id) is not str:
            raise BridgeParamError("incorrect param type: `topic_id`")
        if type(offset) is not int or type(limit) is not int:
            raise BridgeParamError("`limit` and `offset` fields must be integer")
        response = artm_bridge.get_documents_by_topic(topic_id, offset=offset, limit=limit)
    elif message["act"] == "get_document":
        doc_id = message["doc_id"]
        if type(doc_id) is not str:
            raise BridgeParamError("incorrect param type: `doc_id`")
        docs = artm_bridge.data_source.get_documents_by_ids([doc_id], with_modalities=True)
        if len(docs) == 0:
            raise BridgeParamError("document with `doc_id` = '%s' is not found" % doc_id)
        doc = docs[0]
        if message["recommend_tags"]:
            doc["recommended_tags"] = artm_bridge.recommend_tags_by_doc(doc)
        response = doc
    elif message["act"] == "perform_search":
        query = message["query"]
        limit = message["limit"]
        if type(query) is not str:
            raise BridgeParamError("incorrect param type: `query`")
        if type(limit) is not int:
            raise BridgeParamError("incorrect param type: `limit`")
        response = dict(zip(["docs", "theta"],  artm_bridge.search_documents(query, limit=limit)))
    elif message["act"] == "recommend_docs":
        doc_id = message["doc_id"]
        if type(doc_id) is not str:
            raise BridgeParamError("incorrect param type: `doc_id`")
        sim_docs_ids = artm_bridge.recommend_docs_by_doc(doc_id)
        response = artm_bridge.data_source.get_documents_by_ids(sim_docs_ids, with_texts=False)
    elif message["act"] == "transform_doc":
        doc_path = message["doc_path"]
        filename = message["filename"]
        try:
            # Initialize file resources
            doc_file = open(doc_path)
            vw_fd,vw_path = tempfile.mkstemp(prefix="upload", text=True)
            vw_file = os.fdopen(vw_fd, "w")
            batch_path = tempfile.mkdtemp(prefix="batch")
            # Parse uploaded file
            doc = pipeline.fit_transform(doc_file)
            # Save to Vowpal Wabbit file
            text_utils.VowpalWabbitSink(vw_file, lambda x: "upload") \
                      .fit_transform([doc])
            # Transform uploaded document and return its Theta matrix
            response = {}
            response["filename"] = filename
            response["theta"] = artm_bridge.model.transform_one(vw_path, batch_path)
        except:
            raise
        finally:
            # Delete uploaded file
            doc_file.close()
            os.remove(doc_path)
            # Delete temporary files/dirs
            os.remove(vw_path)
            rm_flat_dir(batch_path)
    elif False and message["act"] == "get_next_assessment":
        ass_id = message["assessor_id"]
        ass_cnt = message["assessors_cnt"]
        col_name = message["collection_name"]

        if ass_id >= ass_cnt:
            response = "Incorrent `assessor_id`"
        else:
            docs_count = db["datasets"][col_name].count()
            min_id = int(ass_id * docs_count / ass_cnt)
            max_id = int((ass_id + 1) * docs_count / ass_cnt)
            # May take a long time for large datasets
            docs_ids = db["datasets"][col_name].find({}, {"_id": 1})
            docs_ids = list(map(lambda x: x["_id"],
                                docs_ids.sort([("_id", 1)])))
            ass_docs_ids = docs_ids[min_id:max_id]
            # Get unused documents' ids
            used_docs_ids = db["assessment"][col_name].find({}, {"_id": 1})
            used_docs_ids = list(map(lambda x: x["_id"], used_docs_ids))
            unused_docs_ids = list(set(ass_docs_ids) - set(used_docs_ids))
            # Form response
            random.shuffle(unused_docs_ids)
            # Use batches of 100 docs per request
            response = unused_docs_ids[:100]
    elif False and message["act"] == "assess_document":
        doc_id = message["doc_id"]
        is_relevant = message["is_relevant"]
        col_names = [v for k, v in prefix_to_col_map.items()
                     if doc_id.startswith(k + "_")]
        if len(col_names) != 1:
            response = False
        else:
            col_name = col_names[0]
            dataset = db["assessment"][col_name]
            doc = {
                "is_relevant": is_relevant,
                "assess_time": datetime.now()
            }
            dataset.replace_one({"_id": doc_id}, doc, upsert=True)
            response = True
    else:
        raise BridgeParamError("unknown query")

    return response

try:
    # Initialize arbitrary pipeline
    pipeline = arbitrary.get_pipeline()

    # Initialize BigARTM logging
    artm_log_path = tempfile.mkdtemp(prefix="artmlog")
    lc = artm.messages.ConfigureLoggingArgs()
    lc.log_dir = artm_log_path
    lc.minloglevel = 2
    artm.wrapper.LibArtm(logging_config=lc)

    # Initialize ZeroMQ
    context = zmq.Context()
    socket = context.socket(zmq.DEALER)
    # TODO: maybe set socket identity for persistence?
    socket.connect("tcp://localhost:%d" % ZMQ_BACKEND_PORT)

    # Initialize ARTM bridge
    artm_bridge = artm_lib.ArtmBridge(MODEL_PATH)

    # Notify ARTM_proxy that we're up
    socket.send(UP)

    print("ARTM_bridge: start serving ZeroMQ queries on port",
          ZMQ_BACKEND_PORT)

    while True:
        # Wait for next request from client
        client, request = socket.recv_multipart()
        message = json.loads(request.decode("utf-8"))

        # Debug logging
        # print("> " + json.dumps(message))

        # Process message
        response = {}
        try:
            response["ok"] = process_msg(message)
        except BridgeParamError as e:
            response["error"] = {"message": e.message}
        except BaseException as e:
            response["error"] = {"message": "server error"}
            traceback.print_exc()

        socket.send_multipart([
            client,
            json.dumps({
                "act":  message["act"],
                "id":   message.get("id"),
                "data": response
            }).encode("utf-8")
        ])
except:
    traceback.print_exc()
    print("Shutting down ARTM_bridge...")
finally:
    # Unregister
    socket.send(DOWN)
    # Clean up
    rm_flat_dir(artm_log_path)
    socket.close()
    context.term()
