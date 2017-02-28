import re
import copy

from pymystem3 import Mystem
from pymongo import MongoClient
from collections import Counter
from sklearn.pipeline import Pipeline
from bson.objectid import ObjectId


default_modalities = [
    "text",     # Preprocessed tokens of a document's contents.
    "flat_tag", # Flat tags associated manually with a document.
]


# ----------------------------
# Generic interfaces
# ----------------------------

class BaseTransformable():
    """
    Root interface class, which describes abstract transformation of data.
    """

    def fit(self, *args):
        pass

    def transform(self, *args):
        pass

    def fit_transform(self, *args):
        return self.fit(*args).transform(*args)

class BaseSource(BaseTransformable):
    """
    Root interface class, which describes the starting point of processing.
    Purpose: accumulate some input, do a preparatory job, and pass
             an accumulated state further over pipeline.
    Input:   arbitrary data.
    Output:  pointer to self (default case), but may be re-defined.
    """

    def transform(self, *args):
        return self

class BaseProcessor(BaseTransformable):
    """
    Root interface class, which describes an intermediate step of processing.
    Purpose: take some input from previous steps, modify it and pass it over
             next processors on the pipeline.
    Input:   arbitrary data.
    Output:  arbitrary (modified) data.
    """

    def fit(self, *args):
        return self

class BaseSink(BaseTransformable):
    """
    Root interface class, which describes the terminate point of processing.
    Purpose: perform some action over processed data and serve as a
             terminal element on the pipeline.
    Input:   arbitrary data.
    Output:  None.
    """

    def fit(self, *args):
        return self

    def transform(self, *args):
        return None

class TextProcessor(BaseProcessor):
    """Interface class, which describes raw text processing."""
    pass

class DocumentProcessor(BaseProcessor):
    """Interface class, which describes document processing."""
    pass

class CollectionProcessor(BaseProcessor):
    """Interface class, which describes collection processing."""
    pass


# ----------------------------
# Specific classes
# ----------------------------

# TODO: Document all processors

class Splitter(BaseProcessor):
    def __init__(self, token_pattern):
        self.token_regexp = re.compile(token_pattern)

    def transform(self, text, *args):
        return self.token_regexp.findall(text)

class DictionaryFilterer(BaseProcessor):
    def __init__(self, stop_words=None):
        if stop_words is None:
            self.stop_words = {}
        else:
            self.stop_words = set(stop_words)

    def transform(self, tokens, *args):
        return list(filter(lambda t: t not in self.stop_words, tokens))

class FrequencyFilterer(BaseProcessor):
    def __init__(self, min_df=None, max_df=None):
        min_df = 0  if min_df is None else min_df
        max_df = 1. if max_df is None else max_df
        if not isinstance(min_df, int) and not isinstance(min_df, float):
            raise ValueError("min_df is neither int nor float")
        if not isinstance(max_df, int) and not isinstance(max_df, float):
            raise ValueError("max_df is neither int nor float")
        self.min_df = min_df
        self.max_df = max_df

    def fit(self, tokens, *args):
        freq = Counter(tokens)
        min_df = self.min_df if isinstance(self.min_df, int) else self.min_df * len(tokens)
        max_df = self.max_df if isinstance(self.max_df, int) else self.max_df * len(tokens)
        self.stop_words = set(map(lambda p: p[0], filter(lambda p: p[1] < min_df or p[1] > max_df, freq.items())))
        return self

    def transform(self, tokens, *args):
        return list(filter(lambda t: t not in self.stop_words, tokens))

class LengthFilterer(BaseProcessor):
    def __init__(self, min_len=0, len_func=None):
        self.min_len = min_len
        self.len_func = len if len_func is None else len_func

    def transform(self, tokens, *args):
        return list(filter(lambda t: self.len_func(t) >= self.min_len, tokens))

class Lemmatizer(BaseProcessor):
    def __init__(self):
        self.m = Mystem()

    def transform(self, tokens, *args):
        lemm_str = " ".join(tokens)
        return list(filter(lambda s: s.strip(), self.m.lemmatize(lemm_str)))

class DefaultTextProcessor(TextProcessor):
    def __init__(self, token_pattern="(?u)\\b\\w+\\b", stop_words=None):
        splitter = Splitter(token_pattern)
        filterer = DictionaryFilterer(stop_words=stop_words)

        self.text_pipeline = Pipeline([
            ("split-text",    splitter),
            ("filter-tokens", filterer),
        ])

    def transform(self, raw_text, *args):
        return self.text_pipeline.fit_transform(raw_text.lower())

class DefaultDocumentProcessor(DocumentProcessor):
    def __init__(self, min_df=None, max_df=None, stop_lemmas=None):
        lemmatizer    = Lemmatizer()
        dict_filterer = DictionaryFilterer(stop_words=stop_lemmas)
        freq_filterer = FrequencyFilterer(min_df=min_df, max_df=max_df)

        self.doc_pipeline = Pipeline([
            ("lemmatize-tokens",     lemmatizer),
            ("filter-by-dictionary", dict_filterer),
            ("filter-by-frequency",  freq_filterer),
        ])

    def transform(self, tokens, *args):
        modalities = dict.fromkeys(default_modalities, [])
        modalities["text"] = self.doc_pipeline.fit_transform(tokens)
        return modalities

class DefaultCollectionProcessor(CollectionProcessor):
    def __init__(self, min_len=0, min_df=None, max_df=None, len_func=None):
        len_func = (lambda doc: len(doc["modalities"]["text"])) if len_func is None else len_func

        len_filterer = LengthFilterer(min_len=min_len, len_func=len_func)

        self.col_pipeline = Pipeline([
            ("filter-by-length", len_filterer),
        ])

        self.freq_filterer = FrequencyFilterer(min_df=min_df, max_df=max_df)

    def fit(self, docs):
        # TODO: make modality an external parameter
        tokens = sum([doc["modalities"]["text"] for doc in docs], [])
        self.freq_filterer.fit(tokens)
        return self

    def transform(self, docs, *args):
        docs = self.col_pipeline.fit_transform(docs)
        docs_modified = []
        for doc in docs:
            # TODO: make modality an external parameter
            doc["modalities"]["text"] = self.freq_filterer.transform(doc["modalities"]["text"])
            docs_modified.append(doc)
        return docs_modified

class UciBowSink(CollectionProcessor):
    def __init__(self, vocab_file, docword_file):
        self.vocab_file = vocab_file
        self.docword_file = docword_file

    def fit(self, docs):
        Ws = set()
        for doc in docs:
            for k, vs in doc["modalities"].items():
                Ws |= set(map(lambda v: (re.sub("\s", "_", v), k), vs))
        self.Ws = dict(zip(Ws, range(len(Ws))))
        return self

    def transform(self, docs, *args):
        w, d = len(self.Ws), len(docs)
        nnzs = []
        for docID, doc in enumerate(docs):
            bow = []
            for k, vs in doc["modalities"].items():
                bow += map(lambda v: self.Ws.get((re.sub("\s", "_", v), k), -1), vs)
            nnzs += map(lambda p: (docID + 1, p[0] + 1, p[1]), Counter(bow).items())
        docword_header = "%d\n%d\n%d\n" % (d, w, len(nnzs))
        words_list = sorted(self.Ws.items(), key=lambda p: p[1])
        self.vocab_file.write("\n".join(map(lambda k: "%s %s" % k[0], words_list)))
        self.docword_file.write(docword_header + "\n".join(map(lambda v: "%d %d %d" % v, nnzs)))
        self.vocab_file.close()
        self.docword_file.close()

class MongoDbSink(BaseSink):
    def __init__(self, collection_name, id_func=None):
        client = MongoClient()
        self.collection = client["datasets"][collection_name]
        self.id_func = id_func

    def transform(self, docs, *args):
        reqs = copy.deepcopy(docs)
        if self.id_func:
            for req in reqs:
                req["_id"] = self.id_func(req)
        result = self.collection.insert_many(reqs)
        return result.inserted_ids