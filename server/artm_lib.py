import numpy as np
import pandas as pd
import pickle
import regex
import os
import operator

import hierarchy_utils
from pymongo import MongoClient
from scipy.linalg import norm
from sklearn.metrics.pairwise import pairwise_distances

import artm


# List of all doc_id prefixes
# TODO: move to config file
prefix_to_col_map = {"pn": "postnauka", "habr": "habrahabr",
                     "elem": "elementy"}


def hellinger_dist(p, q):
    return norm(np.sqrt(p) - np.sqrt(q))


class ArtmModel:
    def __init__(self, model_path, topic_naming_n_words=3, psi_edge_threshold=0.05):
        # Load ARTM model and model extra info
        self._extra_info = pickle.load(open(os.path.join(model_path, "extra_info.dump"), "rb"))
        self._model = hierarchy_utils.hARTM(theta_columns_naming="title",
                                            cache_theta=True,
                                            class_ids=self._extra_info["class_ids"])
        self._model.load(model_path)

        # Extract Φ, Ψ, Ɵ matrices from model
        self._phis = []
        self._psis = []
        self._theta = self._extra_info["theta"]
        for level_idx, artm_level in enumerate(self._model):
            self._phis.append(artm_level.get_phi(class_ids="flat_tag"))
            if level_idx > 0:
                self._psis.append(artm_level.get_psi())

        # Construct topic name mappings
        self._from_artm_tid_map = {}
        self._to_artm_tid_map = {}
        self._from_lid_tid_map = {}
        self._to_lid_tid_map = {}
        theta_new_index = []
        for artm_tid in self._theta.index:
            if artm_tid.startswith("level_0_"):
                lid, tid = 0, artm_tid[8:]
            else:
                lid, tid = artm_tid[5:].split("_", 1)
                lid = int(lid)
            topic_id = "level_%d_%s" % (lid, tid) # internal project-consistent topic name
            if tid.startswith("topic_"):
                self._from_artm_tid_map[artm_tid] = topic_id
                self._to_artm_tid_map[topic_id] = artm_tid
                self._from_lid_tid_map[lid, tid] = topic_id
                self._to_lid_tid_map[topic_id] = (lid, tid)
            theta_new_index.append(topic_id)
        self._theta.index = theta_new_index

        # Construct spectrums map
        #spectrum_map = {}
        #for spectrum in self._extra_info["spectrums"]:
        #    for i, topic_id in enumerate(spectrum):
        #        spectrum_map[topic_id] = i

        # Construct topics infos
        # TODO: make topic maning an external procedure
        self._topics = {}
        for lid, phi in enumerate(self._phis):
            names = phi.index[phi.values.argsort(axis=0)[-2 * topic_naming_n_words:][::-1].T]
            for tid, top_words in zip(phi.columns, names):
                # subject topic names are "topic_X", where X = 0, 1, ...
                # background topic names are "background_X", where X = 0, 1, ...
                if regex.match("^topic_\d+$", tid):
                    topic_id = self._from_lid_tid_map[lid, tid]
                    self._topics[topic_id] = {
                        "level_id":    lid,
                        "top_words":   list(top_words),
                        "parents":     [],
                        "children":    [],
                        "weight":      0,
                        #"spectrum_id": spectrum_map.get(topic_id)
                    }

        # Define parent-child relationship for topics
        for lid, psi in enumerate(self._psis):
            psi = (psi >= psi_edge_threshold)
            for tid1 in psi.columns:
                if regex.match("^topic_\d+$", tid1):
                    for tid2 in psi.index:
                        if regex.match("^topic_\d+$", tid2) and psi.loc[tid2, tid1]:
                            topic_id_parent = self._from_lid_tid_map[lid, tid1]
                            topic_id_child = self._from_lid_tid_map[lid + 1, tid2]
                            self._topics[topic_id_parent]["children"].append(topic_id_child)
                            self._topics[topic_id_child]["parents"].append(topic_id_parent)

        # Assign top words to child topics
        # TODO: make topic maning an external procedure
        for topic_id, topic in self._topics.items():
            used_top_words = sum(map(lambda tid: self._topics[tid]["top_words"][:topic_naming_n_words],
                                     topic["parents"]), [])
            topic["top_words"] = list(filter(lambda tw: tw not in used_top_words,
                                             topic["top_words"]))[:topic_naming_n_words]

        # Define parent-child relationship for topics and documents
        last_lid = self.num_levels - 1
        doc_topics = self.get_topics_ids_by_level(last_lid)
        self._doc_theta = self._theta.loc[doc_topics]
        self._doc_thresholds = self._doc_theta.max(axis=0) / np.sqrt(2)

        # Define topic weight as:
        # For last-level topic, weight = number of documents that belong to it
        # For a higher-level topic, weight = sum(weight) of topic's child topics
        docs_count = self._doc_theta.apply(lambda s: sum(s >= self._doc_thresholds), axis=1)
        lids_tids = list(self._from_lid_tid_map.keys())
        lids_tids = sorted(lids_tids, reverse=True)
        for lid, tid in lids_tids:
            topic_id = self._from_lid_tid_map[lid, tid]
            if lid == last_lid:
                w = int(docs_count[topic_id])
            else:
                w = 0
                for child_topic_id in self._topics[topic_id]["children"]:
                    w += self._topics[child_topic_id]["weight"]
            self._topics[topic_id]["weight"] = w

    def get_topics_ids_by_level(self, level_id):
        if level_id < 0 or level_id >= self.num_levels:
            raise ValueError("Unknown level_id: %d" % level_id)

        topics_ids = []
        for (lid, tid), topic_id in self._from_lid_tid_map.items():
            if lid == level_id:
                topics_ids.append(topic_id)
        return topics_ids

    def get_docs_ids_by_topic(self, topic_id):
        if topic_id not in self._doc_theta.index:
            raise ValueError("Unknown document topic id: '%s'" % topic_id)

        ptd = self._doc_theta.loc[topic_id]
        sorted_ptd = ptd[ptd >= self._doc_thresholds].sort_values(ascending=False)
        return sorted_ptd


    def get_topics_by_docs_ids_old_format(self, docs_ids):
        topics_for_docs = []
        for doc in docs_ids:
            if doc["doc_id"] not in self._doc_thresholds.index:
                continue
            topics_for_doc = {}
            doc_id = doc["doc_id"]
            topics_for_doc["doc_id"] = doc_id
            comparsion = self._doc_theta[doc_id] > self._doc_thresholds[doc_id]
            last_level_topics = list(comparsion[comparsion == True].index)
            levels_count = self._to_lid_tid_map[last_level_topics[0]][0] + 1
            topics_for_doc["level_%d"%(levels_count-1)] = last_level_topics
            for lid in range(1, levels_count)[::-1]:
                current_level = topics_for_doc["level_%d"%(lid)]
                higher_level = []
                for topic in current_level:
                    higher_level += self._topics[topic]["parents"]
                topics_for_doc["level_%d"%(lid-1)] = higher_level
            topics_for_docs.append(topics_for_doc)
        return topics_for_docs

    def get_topics_by_docs_ids(self, docs_ids):
        theta = self.theta
        doc_theta = self._doc_theta
        thresholds = self._doc_thresholds
        topics = self.topics
        tid_lid = self._to_lid_tid_map

        lowest_level_counter = pd.Series(np.zeros(len(doc_theta.index)), index = doc_theta.index)

        for doc in docs_ids:
            if doc["doc_id"] not in thresholds.index:
                continue
            topics_for_doc = {}
            lowest_level_counter += (doc_theta[doc["doc_id"]] > thresholds[doc["doc_id"]]).map(lambda x: 1 if x else 0)

        levels_count = tid_lid[lowest_level_counter.index[0]][0] + 1
            
        answer = pd.Series(np.zeros(len(theta.index)), index = theta.index)
        answer[lowest_level_counter.index] = lowest_level_counter

        for lid in range(0, levels_count-1)[::-1]:
            curr_level_topics = list(filter(lambda x: x.startswith("level_%d_t"%(lid)), answer.index))
            for topic in curr_level_topics:
                for child in topics[topic]["children"]:
                    answer[topic] += answer[child]

        for lid in range(0, levels_count)[::-1]:
            curr_level_topics = list(filter(lambda x: x.startswith("level_%d_t"%(lid)), answer.index))
            total_docs_in_this_level = sum(answer[curr_level_topics])
            if total_docs_in_this_level != 0:
                answer[curr_level_topics] /= total_docs_in_this_level

        return dict(answer)


    def transform_one(self, vw_path, batch_path):
        transform_batch = artm.BatchVectorizer(data_format="vowpal_wabbit",
                                               data_path=vw_path,
                                               batch_size=1,
                                               target_folder=batch_path)
        transform_theta = self._model.transform(transform_batch)
        response = {}
        for artm_tid, pdt in transform_theta["upload"].items():
            if artm_tid in self._from_artm_tid_map:
                topic_id = self._from_artm_tid_map[artm_tid]
                response[topic_id] = float(pdt)
        return response


    @property
    def theta(self):
        return self._theta

    @property
    def topics(self):
        return self._topics

    @property
    def num_levels(self):
        return self._model.num_levels

    @property
    def topics_ids(self):
        return self._theta.index

    def get_phi(self, level_id):
        return self._phis[level_id]

    def get_psi(self, level_id):
        return self._psis[level_id]

    def to_topic_id(self, lid, tid):
        return self._from_lid_tid_map[lid, tid]

    def from_topic_id(self, topic_id):
        return self._to_lid_tid_map[topic_id]


class ArtmDataSource:
    def __init__(self):
        self._db = MongoClient()
        # Прости за эти константы, предзабитые в код ^_^
        # надо мержить коллекции, чтоб этого говна не было
        self._collections = ["habrahabr", "postnauka"]

        # Потенциально долго
        for collection in [self._db.datasets[col] for col in self._collections]:
            if not ("markdown_text" in collection.index_information().keys()):
                collection.create_index([("markdown", "text")], default_language='russian')

    def get_documents_by_ids(self, docs_ids, with_texts=True, with_modalities=False):
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
            dataset = self._db["datasets"][col_name]
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
                "authors_names": doc.get("authors_names", [])
            }
            if with_texts:
                res["markdown"] = doc["markdown"]
            if with_modalities:
                res["modalities"] = doc["modalities"]
            response.append(res)
        return response

    def search_query_in_all_docs(self, query, limit=10):
        db = self._db
        all_results = []
        for collection in self._collections:
            col_results = db.datasets[collection].find(
                                {'$text': {'$search': query}},
                                {'score': {'$meta'  : 'textScore' }}).sort(
                                [('score', {'$meta': 'textScore'})]).limit(limit)
            for row in col_results:
                all_results.append({
                    'doc_id'    : row['_id'],
                    'score'     : row['score'],
                    })

        return sorted(all_results, key = lambda x: x["score"])[:limit]

    def search_query_in_models_docs(self, query, limit=10):
        db = self._db
        col_results = db.model.all_docs.find(
                                {'$text': {'$search': query}},
                                {'score': {'$meta'  : 'textScore' }}).sort(
                                [('score', {'$meta': 'textScore'})]).limit(limit)
        results = []
        for row in col_results:
            results.append({
                    'doc_id'    : row['_id'],
                    'score'     : row['score'],
                    })

        return sorted(results, key = lambda x: x["score"])

class ArtmBridge:
    def __init__(self, model_path):
        self._data_source = ArtmDataSource()
        self._model = ArtmModel(model_path)

        # Select topics which will be used for recommendation
        self._rec_lid = 0
        rec_topics = self._model.get_topics_ids_by_level(self._rec_lid)
        self._rec_tids = list(map(lambda t: self._model.from_topic_id(t)[1], rec_topics))
        self._rec_theta = self._model.theta.T[rec_topics].sort_index()

    def get_documents_by_topic(self, topic_id, offset=0, limit=None, with_weights=True):
        sorted_ptd = self._model.get_docs_ids_by_topic(topic_id)
        if limit is None:
            limit = len(sorted_ptd)

        sorted_ptd = sorted_ptd[offset:offset + limit]
        docs_ids = sorted_ptd.index
        docs = self._data_source.get_documents_by_ids(docs_ids, with_texts=False)
        weights = {k: float(v) for k, v in sorted_ptd.items()}

        if with_weights:
            return docs, weights
        else:
            return docs

    def recommend_tags_by_doc(self, doc, rec_tags_count=5):
        own_tags = set(doc["modalities"]["flat_tag"])
        ptd = self._rec_theta.loc[doc["doc_id"]]
        weighted_tags = self._model.get_phi(self._rec_lid)[self._rec_tids].mul(ptd.values)
        rec_tags = {}
        for _, pwt in weighted_tags.iteritems():
            top_tags = pwt.nlargest(len(own_tags) + rec_tags_count)
            for tag, w in top_tags.iteritems():
                tag = regex.sub("_", " ", tag)
                if tag not in own_tags:
                    rec_tags[tag] = max(rec_tags.get(tag, 0), w)
        rec_tags = list(map(lambda p: (p[1], p[0]), rec_tags.items()))
        rec_tags.sort(reverse=True)
        rec_tags = list(map(lambda x: x[1], rec_tags[:rec_tags_count]))
        return rec_tags

    def recommend_docs_by_doc(self, doc_id, rec_docs_count=5, metric=hellinger_dist):
        doc = self._rec_theta.loc[doc_id]
        dist = pairwise_distances([doc], self._rec_theta, hellinger_dist)[0]
        dist_series = pd.Series(data=dist, index=self._rec_theta.index)
        sim_docs_ids = dist_series.nsmallest(rec_docs_count + 1).index
        return sim_docs2_ids[1:] # Not counting the `doc` itself.

    def search_documents(self, query, limit=10):
        search_results = self._data_source.search_query_in_models_docs(query, limit)
        return self._model.get_topics_by_docs_ids(search_results)

    @property
    def data_source(self):
        return self._data_source

    @property
    def model(self):
        return self._model