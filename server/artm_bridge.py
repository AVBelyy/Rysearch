import numpy as np
import pickle
import json
import zmq
import re

from sklearn.metrics.pairwise import pairwise_distances
from pymongo import MongoClient
from scipy.linalg import norm

MODEL_PATH = "hartm.mdl"
ZMQ_PORT = 2411

EDGE_THRESHOLD = 0.05
TOP_N_WORDS = 3
TOP_N_REC_DOCS = 5
TOP_N_TOPIC_DOCS = 10

# Initialize MongoDB
mongo_client = MongoClient()
db = mongo_client["datasets"]

# Initialize ARTM data
artm_model = pickle.load(open(MODEL_PATH, "rb"))
psis = []
phis = []
for k, v in artm_model.items():
    if k.startswith("psi_"):
        psis.append((int(k[4:]), v))
    if k.startswith("phi_"):
        phis.append((int(k[4:]), v))
psis = list(map(lambda p: p[1], sorted(psis)))
phis = list(map(lambda p: p[1], sorted(phis)))
topics = {}
T = lambda lid, tid: "level_%d_%s" % (lid, tid)
unT = lambda t: list(map(int, t[6:].split("_topic_")))

# Change this constants if model changes
Ts = [20, 77]
# TODO: index sorting may not be neccessary when we support multiple collections
rec_theta = artm_model["theta"][:Ts[0]].T.sort_index()

# Create subject topic names
for lid, phi in enumerate(phis):
    names = phi.index[phi.values.argsort(axis=0)[-TOP_N_WORDS:][::-1].T]
    for tid, top_words in zip(phi.columns, names):
        # subject topic names are "topic_X", where X = 0, 1, ...
        # background topic names are "background_X", where X = 0, 1, ...
        if re.match("^topic_\d+$", tid):
            topics[T(lid, tid)] = {
                "level_id":  lid,
                "top_words": list(top_words),
                "parents":   [],
                "children":  [],
            }

# Collect topic edges
for lid, psi in enumerate(psis):
    density = 0
    psi = psi > EDGE_THRESHOLD
    for tid1 in psi.columns:
        if re.match("^topic_\d+$", tid1):
            for tid2 in psi.index:
                if re.match("^topic_\d+$", tid2) and psi.loc[tid2, tid1]:
                    density += 1
                    topics[T(lid, tid1)]["children"].append(T(lid + 1, tid2))
                    topics[T(lid + 1, tid2)]["parents"].append(T(lid, tid1))
    print("Level", lid, "density:", density, "/", psi.shape[0] * psi.shape[1])

# Initialize ZeroMQ
context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:%d" % ZMQ_PORT)

def hellinger_dist(p, q):
    return norm(np.sqrt(p) - np.sqrt(q))

def get_artm_tid(lid, tid):
    if lid < 0 or lid > len(Ts) or tid < 0 or tid >= sum(Ts):
        return None

    # This is due to hARTM bug
    if lid == 0:
        return "level_%d_topic_%d" % (lid, tid)
    else:
        return "level%d_topic_%d" % (lid, tid)

def get_documents_by_ids(docs_ids):
    fields = {"title": 1, "markdown": 1}
    result = db.postnauka.find({"_id": {"$in": docs_ids}}, fields)
    result_map = dict(map(lambda v: (v["_id"], v), result))
    response = []
    for doc_id in docs_ids:
        doc = result_map[doc_id]
        response.append({
            "doc_id":   doc["_id"],
            "title":    doc["title"],
            "markdown": doc["markdown"]
        })
    return response

print("Start serving ZeroMQ queries on port", ZMQ_PORT)

while True:
    # Wait for next request from client
    message = json.loads(socket.recv().decode("utf-8"))
    response = None

    # Process query
    if message["act"] == "get_topics":
        response = topics
    elif message["act"] == "get_documents":
        lid, tid = unT(message["topic_id"])
        artm_tid = get_artm_tid(lid, tid)
        if artm_tid is None:
            response = "Incorrect `topic_id`"
        else:
            ptd = artm_model["theta"].loc[artm_tid]
            indices = ptd.sort_values()[-TOP_N_TOPIC_DOCS:].index
            # TODO: fix when we support multiple collections
            docs_ids = list(map(lambda doc_id: "pn_%d" % doc_id, indices))
            response = get_documents_by_ids(docs_ids)
    elif message["act"] == "get_recommendations":
        # TODO: this only works with a single collection of documents (Postnauka) now
        # TODO: make appropriate fixes when we support multiple collections
        doc_id = int(message["doc_id"])
        if doc_id not in rec_theta.index:
            response = "Unknown `doc_id`"
        else:
            dist = pairwise_distances([rec_theta.loc[doc_id]], rec_theta, hellinger_dist)[0]
            indices = np.argsort(dist)[1:TOP_N_REC_DOCS + 1]
            # TODO: fix when we support multiple collections
            sim_docs_ids = list(map(lambda doc_id: "pn_%d" % (doc_id + 1), indices))
            response = get_documents_by_ids(sim_docs_ids)
    else:
        response = "Unknown query"

    socket.send_string(json.dumps({
        "act":  message["act"],
        "id":   message.get("id"),
        "data": response
    }))
