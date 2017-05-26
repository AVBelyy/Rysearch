# Парсер произвольного документа

import regex
import unicodedata

from sklearn.pipeline import Pipeline
from pathlib import Path

from parsers.text_utils import BaseSource, BaseProcessor, BaseSink
from parsers.text_utils import DefaultTextProcessor, DefaultDocumentProcessor, DefaultCollectionProcessor
from parsers.text_utils import VowpalWabbitSink, MongoDbSink

class ArbitraryFileSource(BaseSource):
    def fit(self, iter_source, *args):
        self.iter_source = iter_source
        return self

class ArbitraryFileProcessor(BaseProcessor):
    def __init__(self, stop_words):
        self.doc_pipeline = Pipeline([
            ("text-processor",     DefaultTextProcessor(token_pattern="(?u)\\b\\p{L}+\\b")),
            ("document-processor", DefaultDocumentProcessor(stop_lemmas=stop_words)),
        ])

    @staticmethod
    def strip_accents(s):
        unused_char = '\U00037b84'
        s = s.replace("й", unused_char)
        return "".join((c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")).replace(unused_char, "й")

    def transform(self, src, *args):
        # Parse text file
        text = src.iter_source.read()
        # Get rid of accent marks
        text = ArbitraryFileProcessor.strip_accents(text)
        # Run inner pipeline to form modalities
        modalities = self.doc_pipeline.fit_transform(text)
        # Finally, make a document and return it
        doc = {}
        doc["modalities"] = modalities
        doc["markdown"] = text
        return doc

def get_pipeline():
    root_path = Path("../datasets/arbitrary")
    stop_words = (root_path / "stopwords.txt").open().read().split()
    return Pipeline([
        ("file-source", ArbitraryFileSource()),
        ("file-processor", ArbitraryFileProcessor(stop_words)),
    ])

if __name__ == "__main__":
    import argparse
    pipeline = get_pipeline()
    argparser = argparse.ArgumentParser()
    argparser.add_argument("source_file")
    # argparser.add_argument("target_file")
    args = argparser.parse_args()
    with open(args.source_file) as src:
        doc = pipeline.fit_transform(src)
        print(doc)