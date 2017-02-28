import numpy as np
import pickle
import json
import zmq

from sklearn.metrics.pairwise import pairwise_distances
from pymongo import MongoClient
from scipy.linalg import norm

MODEL_PATH = "hartm.mdl"
ZMQ_PORT = 2411

EDGE_THRESHOLD = 0.05
TOP_N_WORDS = 3
TOP_N_REC_DOCS = 10

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
t = lambda lid, tid: "level_%d_%s" % (lid, tid)

# Change this constants if model changes
[T1, T2, T3] = [10, 30, 70]
# TODO: index sorting may not be neccessary when we support multiple collections
rec_theta = artm_model["theta"][:T1].T.sort_index()

# Create topic names
for lid, phi in enumerate(phis):
    names = phi.index[phi.values.argsort(axis=0)[-TOP_N_WORDS:][::-1].T]
    for tid, top_words in zip(phi.columns, names):
        topics[t(lid, tid)] = {
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
        for tid2 in psi.index:
            if psi.loc[tid2, tid1]:
                density += 1
                topics[t(lid, tid1)]["children"].append(t(lid + 1, tid2))
                topics[t(lid + 1, tid2)]["parents"].append(t(lid, tid1))
    print("Level", lid, "density:", density, "/", psi.shape[0] * psi.shape[1])

# Initialize ZeroMQ
context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:%d" % ZMQ_PORT)

def hellinger_dist(p, q):
    return norm(np.sqrt(p) - np.sqrt(q))

print("Start serving ZeroMQ queries on port", ZMQ_PORT)

while True:
    # Wait for next request from client
    message = json.loads(socket.recv().decode("utf-8"))
    response = None

    # Process query
    if message["act"] == "get_topics":
        response = topics
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
            fields = {"title": 1, "markdown": 1}
            result = db.postnauka.find({"_id": {"$in": sim_docs_ids}}, fields)
            result_map = dict(map(lambda v: (v["_id"], v), result))
            response = []
            for sim_doc_id in sim_docs_ids:
                sim_doc = result_map[sim_doc_id]
                response.append({
                    "doc_id":   sim_doc["_id"],
                    "title":    sim_doc["title"],
                    "markdown": sim_doc["markdown"]
                })
    else:
        response = "Unknown query"

    socket.send_string(json.dumps({
        "act":  message["act"],
        "id":   message.get("id"),
        "data": response
    }))
