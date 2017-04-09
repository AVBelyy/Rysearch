import numpy as np
import pandas as pd
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
DOC_THRESHOLD = 0.25
TOP_N_WORDS = 3
TOP_N_REC_DOCS = 5
TOP_N_TOPIC_DOCS = 20

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
all_topics = artm_model["theta"].index
rec_topics = list(filter(lambda t: re.match("level1_topic_*", t), all_topics))
rec_theta = artm_model["theta"].T[rec_topics].sort_index()

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

# Assign integer weights to topics
topics_weights = (artm_model["theta"] > DOC_THRESHOLD).sum(axis=1)
for tid, w in topics_weights.iteritems():
    # This is due to hARTM bug
    if tid.startswith("level_0_"):
        lid = 0
        tid = tid[8:]
    else:
        lid, tid = tid[5:].split("_", 1)
        lid = int(lid)
    if tid.startswith("topic_"):
        topics[T(lid, tid)]["weight"] = int(w)

# Initialize doc thresholds
doc_topics = list(filter(lambda t: re.match("level1_topic_*", t), all_topics))
doc_theta = artm_model["theta"].loc[doc_topics]
doc_thresholds = doc_theta.max(axis=0) / np.sqrt(2)

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

def get_documents_by_ids(docs_ids, with_texts=True, with_modalities=False):
    fields = {"title": 1}
    prefix_to_col_map = {"pn": "postnauka", "habr": "habrahabr"}
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
        result += db[col_name].find({"_id": {"$in": col_docs_ids}}, fields)
    result_map = dict(map(lambda v: (v["_id"], v), result))
    response = []
    for doc_id in docs_ids:
        if doc_id not in result_map:
            continue
        doc = result_map[doc_id]
        res = {
            "doc_id":        doc["_id"],
            "title":         doc["title"],
        }
        if with_texts:
            res["markdown"] = doc["markdown"]
        if with_modalities:
            res["modalities"] = doc["modalities"]
        response.append(res)
    return response

print("Start serving ZeroMQ queries on port", ZMQ_PORT)

while True:
    # Wait for next request from client
    message = json.loads(socket.recv().decode("utf-8"))
    response = None

    # Process query
    if message["act"] == "get_topics":
        response = {}

        level_0_topics = list(filter(lambda t: re.match("level_0_topic_*", t), all_topics))
        level_0_theta = artm_model["theta"].T[level_0_topics].sort_index()
        level_0_distances = pairwise_distances(level_0_theta.T, metric='correlation').tolist()
        response["distances"] = pairwise_distances(artm_model["theta"], metric='correlation').tolist()
        response["topics"] = topics
        import pickle
        with open("../datasets/topics_distances.dump", "wb") as file:
            pickle.dump(level_0_distances, file);

    elif message["act"] == "get_documents":
        lid, tid = unT(message["topic_id"])
        artm_tid = get_artm_tid(lid, tid)
        if artm_tid is None:
            response = "Incorrect `topic_id`"
        else:
            ptd = doc_theta.loc[artm_tid]
            sorted_ptd = ptd[ptd >= doc_thresholds].sort_values()[-TOP_N_TOPIC_DOCS:][::-1]
            docs_ids = sorted_ptd.index
            # TODO: fix when we have authors_names in Habrahabr
            docs = get_documents_by_ids(docs_ids, with_texts=False, with_modalities=True)
            weights = {d: float(w) for d, w in sorted_ptd.items()}
            response = {"docs": docs, "weights": weights}
    elif message["act"] == "get_document":
        docs_ids = [message["doc_id"]]
        docs = get_documents_by_ids(docs_ids, with_modalities=True)
        response = docs[0] if len(docs) > 0 else None
    elif message["act"] == "get_recommendations":
        doc_id = message["doc_id"]
        if doc_id not in rec_theta.index:
            response = "Unknown `doc_id`"
        else:
            dist = pairwise_distances([rec_theta.loc[doc_id]], rec_theta, hellinger_dist)[0]
            dist_series = pd.Series(data=dist, index=rec_theta.index)
            sim_docs_ids = dist_series.sort_values().index[1:TOP_N_REC_DOCS + 1]
            # TODO: fix when we have authors_names in Habrahabr
            response = get_documents_by_ids(sim_docs_ids, with_texts=False, with_modalities=True)
    elif message["act"] == "get_topics_distances":
        from scipy.stats import pearsonr
        theta = artm_model["theta"]
        response = pairwise_distances(theta, metric='correlation').tolist()
    else:
        response = "Unknown query"

    socket.send_string(json.dumps({
        "act":  message["act"],
        "id":   message.get("id"),
        "data": response
    }))
