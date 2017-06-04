import numpy as np
import pandas as pd
import random
import pickle
import json
import zmq
import regex
import os

from sklearn.metrics.pairwise import pairwise_distances
from pymongo import MongoClient
from scipy.linalg import norm
from datetime import datetime

import artm
from experiments import hierarchy_utils

from parsers import arbitrary, text_utils

MODEL_PATH = "hartm"
THETA_MODEL_PATH = "hartm.mdl"
TRANSFORM_PATH = "uploads/transform.txt"
BATCH_PATH = "uploads/transform_batches/"

ZMQ_BACKEND_PORT = 2511

EMPTY, UP = b"", b"UP"

EDGE_THRESHOLD = 0.05
DOC_THRESHOLD = 0.25
TOP_N_WORDS = 3
TOP_N_REC_DOCS = 5
TOP_N_REC_TAGS = 5
TOP_N_TOPIC_DOCS = 20

# List of all doc_id prefixes
prefix_to_col_map = {"pn": "postnauka", "habr": "habrahabr"}

def hellinger_dist(p, q):
    return norm(np.sqrt(p) - np.sqrt(q))

def from_artm_tid(artm_tid):
    # This is due to hARTM bug
    if artm_tid.startswith("level_0_"):
        return (0, artm_tid[8:])
    else:
        lid, tid = artm_tid[5:].split("_", 1)
        lid = int(lid)
        return (lid, tid)

def to_artm_tid(lid, tid):
    if lid < 0 or lid > len(Ts) or tid < 0 or tid >= sum(Ts):
        return None

    # This is due to hARTM bug
    if lid == 0:
        return "level_%d_topic_%d" % (lid, tid)
    else:
        return "level%d_topic_%d" % (lid, tid)

def get_documents_by_ids(docs_ids, with_texts=True, with_modalities=False):
    fields = {"title": 1, "authors_names" : 1}
    if with_texts:
        fields["markdown"] = 1
    if with_modalities:
        fields["modalities"] = 1
    queries = {}
    for doc_id in docs_ids:
        prefix = doc_id.split("_", 1)[0]
        col_name = prefix_to_col_map[prefix]
        if col_name not in queries:
            queries[col_name] = []
        queries[col_name].append(doc_id)
    result = []
    for col_name, col_docs_ids in queries.items():
        dataset = db["datasets"][col_name]
        result += dataset.find({"_id": {"$in": col_docs_ids}}, fields)
    result_map = dict(map(lambda v: (v["_id"], v), result))
    response = []
    for doc_id in docs_ids:
        if doc_id not in result_map:
            continue
        doc = result_map[doc_id]
        res = {
            "doc_id":        doc["_id"],
            "title":         doc["title"],
            "authors_names": doc["authors_names"],
        }
        if with_texts:
            res["markdown"] = doc["markdown"]
        if with_modalities:
            res["modalities"] = doc["modalities"]
        response.append(res)
    return response

# Initialize MongoDB
db = MongoClient()

# Initialize ARTM data
artm_extra_info = pickle.load(open(MODEL_PATH + "/extra_info.dump", "rb"))
artm_model = hierarchy_utils.hARTM(theta_columns_naming="title",
                                   cache_theta=True,
                                   class_ids=artm_extra_info["class_ids"])
artm_model.load(MODEL_PATH)

# Extract Phi, Psi and Theta matrices
phis = []
psis = []
theta = artm_extra_info["theta"]
# theta = pickle.load(open(THETA_MODEL_PATH, "rb"))["theta"]
for level_idx, artm_level in enumerate(artm_model._levels):
    phis.append(artm_level.get_phi(class_ids="flat_tag"))
    if level_idx > 0:
        psis.append(artm_level.get_psi())

topics = {}
T = lambda lid, tid: "level_%d_%s" % (lid, tid)
unT = lambda t: list(map(int, t[6:].split("_topic_")))

# Change this constants if model changes
Ts = [20, 77]
all_topics = theta.index
rec_lid = 0
rec_topics = list(filter(lambda t: regex.match("level_0_topic_*", t), all_topics))
rec_theta = theta.T[rec_topics].sort_index()

# Create subject topic names
for lid, phi in enumerate(phis):
    names = phi.index[phi.values.argsort(axis=0)[-2 * TOP_N_WORDS:][::-1].T]
    for tid, top_words in zip(phi.columns, names):
        # subject topic names are "topic_X", where X = 0, 1, ...
        # background topic names are "background_X", where X = 0, 1, ...
        if regex.match("^topic_\d+$", tid):
            topics[T(lid, tid)] = {
                "level_id":  lid,
                "top_words": list(top_words),
                "parents":   [],
                "children":  [],
                "weight":    0,
            }

# Collect topic edges
for lid, psi in enumerate(psis):
    density = 0
    psi = psi > EDGE_THRESHOLD
    for tid1 in psi.columns:
        if regex.match("^topic_\d+$", tid1):
            for tid2 in psi.index:
                if regex.match("^topic_\d+$", tid2) and psi.loc[tid2, tid1]:
                    density += 1
                    topics[T(lid, tid1)]["children"].append(T(lid + 1, tid2))
                    topics[T(lid + 1, tid2)]["parents"].append(T(lid, tid1))

# Assign top words to child topics
for topic_id, topic in topics.items():
    used_top_words = sum(map(lambda tid: topics[tid]["top_words"][:TOP_N_WORDS],
                             topic["parents"]), [])
    topic["top_words"] = list(filter(lambda tw: tw not in used_top_words,
                                     topic["top_words"]))[:TOP_N_WORDS]

# Initialize doc thresholds
doc_topics = list(filter(lambda t: regex.match("level1_topic_*", t), all_topics))
doc_theta = theta.loc[doc_topics]
doc_thresholds = doc_theta.max(axis=0) / np.sqrt(2)

# Assign integer weights to topics
topic_docs_count = doc_theta.apply(lambda s: sum(s >= doc_thresholds), axis=1)
for artm_tid in doc_topics:
    topic_id = T(*from_artm_tid(artm_tid))
    w = int(topic_docs_count[artm_tid])
    topics[topic_id]["weight"] = w
for topic_id in topics:
    if "weight" not in topics[topic_id]:
        # TODO: fix when we have number of levels > 2
        topics[topic_id]["weight"] = 0
        for child_topic_id in topics[topic_id]["children"]:
            topics[topic_id]["weight"] += topics[child_topic_id]["weight"]

def process_msg(message):
    if message["act"] == "get_topics":
        response = topics
    elif message["act"] == "get_documents":
        lid, tid = unT(message["topic_id"])
        artm_tid = to_artm_tid(lid, tid)
        if artm_tid is None:
            response = "Incorrect `topic_id`"
        else:
            ptd = doc_theta.loc[artm_tid]
            sorted_ptd = ptd[ptd >= doc_thresholds].sort_values()
            sorted_ptd = sorted_ptd[-TOP_N_TOPIC_DOCS:][::-1]
            docs_ids = sorted_ptd.index
            docs = get_documents_by_ids(docs_ids, with_texts=False)
            weights = {k: float(v) for k, v in sorted_ptd.items()}
            response = {"docs": docs, "weights": weights}
    elif message["act"] == "get_document":
        doc_id = message["doc_id"]
        docs = get_documents_by_ids([doc_id], with_modalities=True)
        # Display tag recommendations
        if len(docs) > 0:
            doc = docs[0]
            own_tags = set(doc["modalities"]["flat_tag"])
            ptd = rec_theta.loc[doc_id]
            topics_ids = list(map(lambda tid: from_artm_tid(tid)[1],
                                  ptd.index))
            weighted_tags = phis[rec_lid][topics_ids].mul(ptd.values)
            rec_tags = {}
            for _, pwt in weighted_tags.iteritems():
                top_tags = pwt.nlargest(len(own_tags) + TOP_N_REC_TAGS)
                for tag, w in top_tags.iteritems():
                    tag = regex.sub("_", " ", tag)
                    if tag not in own_tags:
                        rec_tags[tag] = max(rec_tags.get(tag, 0), w)
            rec_tags = list(map(lambda p: (p[1], p[0]), rec_tags.items()))
            rec_tags.sort(reverse=True)
            rec_tags = list(map(lambda x: x[1], rec_tags[:TOP_N_REC_TAGS]))
            doc["recommended_tags"] = rec_tags
            response = doc
        else:
            response = None
    elif message["act"] == "recommend_docs":
        doc_id = message["doc_id"]
        if doc_id not in rec_theta.index:
            response = "Unknown `doc_id`"
        else:
            doc = rec_theta.loc[doc_id]
            dist = pairwise_distances([doc], rec_theta, hellinger_dist)[0]
            dist_series = pd.Series(data=dist, index=rec_theta.index)
            sim_docs_ids = dist_series.sort_values().index
            sim_docs_ids = sim_docs_ids[1:TOP_N_REC_DOCS + 1]
            response = get_documents_by_ids(sim_docs_ids, with_texts=False)
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
            transform_theta = artm_model.transform(transform_batch)
            # Make a response
            response = {"theta": {}}
            for artm_tid, prob in transform_theta["upload"].items():
                topic_id = T(*from_artm_tid(artm_tid))
                response["theta"][topic_id] = float(prob)
        # Delete uploaded file
        os.remove(doc_path)
    elif message["act"] == "get_next_assessment":
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
    elif message["act"] == "assess_document":
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
