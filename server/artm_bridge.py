import numpy as np
import pickle
import json
import zmq

MODEL_PATH = "hartm.mdl"
ZMQ_PORT = 2411

EDGE_THRESHOLD = 0.05
TOP_N_WORDS = 3

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

# Create topic names
for lid, phi in enumerate(phis):
    names = phi.index[phi.values.argsort(axis=0)[-TOP_N_WORDS:][::-1].T]
    for tid, top_words in zip(phi.columns, names):
        topics[t(lid, tid)] = {
            "level_id": lid,
            "top_words": list(top_words),
            "parents": [],
            "children": [],
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
socket.bind("tcp://127.0.0.1:%d" % ZMQ_PORT)

print("Start serving ZeroMQ queries on port", ZMQ_PORT)

while True:
    # Wait for next request from client
    message = json.loads(socket.recv().decode("utf-8"))
    response = None

    # Process query
    if message["act"] == "get_topics":
        response = topics
    elif message["act"] == "recommend_docs":
        pass
    else:
        response = "Unknown query"

    socket.send_string(json.dumps({"act": message["act"], "data": response}))
