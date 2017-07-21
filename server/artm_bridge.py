import numpy as np
import pandas as pd
import random
import pickle
import json
import zmq
import regex
import os

from parsers import arbitrary, text_utils
from datetime import datetime

import artm
import artm_lib


MODEL_PATH = "hartm"
TRANSFORM_PATH = "uploads/transform.txt"
BATCH_PATH = "uploads/transform_batches/"

ZMQ_BACKEND_PORT = 2511

EMPTY, UP = b"", b"UP"


# Initialize ARTM bridge
artm_bridge = artm_lib.ArtmBridge(MODEL_PATH)

def process_msg(message):
    if message["act"] == "get_topics":
        response = artm_bridge.model.topics
    elif message["act"] == "get_documents":
        topic_id = message["topic_id"]
        docs, weights = artm_bridge.get_documents_by_topic(topic_id, limit=20)
        response = {"docs": docs, "weights": weights}
    elif message["act"] == "get_document":
        doc_id = message["doc_id"]
        docs = artm_bridge.data_source.get_documents_by_ids([doc_id], with_modalities=True)
        if len(docs) > 0:
            doc = docs[0]
            if message["recommend_tags"]:
                doc["recommended_tags"] = artm_bridge.recommend_tags_by_doc(doc)
            response = doc
        else:
            response = None
    elif message["act"] == "recommend_docs":
        doc_id = message["doc_id"]
        sim_docs_ids = artm_bridge.recommend_docs_by_doc(doc_id)
        response = artm_bridge.data_source.get_documents_by_ids(sim_docs_ids, with_texts=False)
    elif message["act"] == "transform_doc":
        doc_path = message["doc_path"]
        with open(doc_path) as doc_file:
            # Parse uploaded file
            doc = pipeline.fit_transform(doc_file)
            vw_file = open(TRANSFORM_PATH, "w")
            # Save to Vowpal Wabbit file
            text_utils.VowpalWabbitSink(vw_file, lambda x: "upload") \
                      .fit_transform([doc])
            # Create batch and transform it into Theta vector
            # TODO: rewrite using data_format="bow_n_wd"
            transform_batch = artm.BatchVectorizer(data_format="vowpal_wabbit",
                                                   data_path=TRANSFORM_PATH,
                                                   batch_size=1,
                                                   target_folder=BATCH_PATH)
            transform_theta = artm_bridge.model.transform(transform_batch)
            # Make a response
            response = {"theta": {}}
            for artm_tid, pdt in transform_theta["upload"].items():
                try:
                    topic_id = artm_bridge.model.from_artm_tid(artm_tid)
                    response["theta"][topic_id] = float(pdt)
                except Exception as e:
                    pass
        # Delete uploaded file
        os.remove(doc_path)
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
        response = "Unknown query"

    return response

try:
    # Initialize arbitrary pipeline
    pipeline = arbitrary.get_pipeline()

    # Initialize ZeroMQ
    context = zmq.Context()
    socket = context.socket(zmq.DEALER)
    # TODO: maybe set socket identity for persistence?
    socket.connect("tcp://localhost:%d" % ZMQ_BACKEND_PORT)

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
        response = process_msg(message)

        socket.send_multipart([
            client,
            json.dumps({
                "act":  message["act"],
                "id":   message.get("id"),
                "data": response
            }).encode("utf-8")
        ])
except Exception as e:
    import traceback
    traceback.print_exc()
    print("Shutting down ARTM_bridge...")
finally:
    # Clean up
    socket.close()
    context.term()
