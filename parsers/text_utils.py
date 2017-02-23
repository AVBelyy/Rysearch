import re

from collections import Counter
from pymystem3 import Mystem
from sklearn.pipeline import Pipeline


default_modalities = [
    "text",     # Preprocessed tokens of a document's contents.
    "flat_tag", # Flat tags associated manually with a document.
]


# ----------------------------
# Generic interfaces
# ----------------------------

class BaseProcessor(object):
    """Root interface class, which describes abstract transformation."""
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

class Document(object):
    """Class for storing documents of any collection."""

    def __init__(self, title, modalities):
        self.title = title
        self.modalities = modalities

class Splitter(BaseProcessor):
    def __init__(self, token_pattern):
        self.token_regexp = re.compile(token_pattern)

    def transform(self, text):
        return self.token_regexp.findall(text)

class DictionaryFilterer(BaseProcessor):
    def __init__(self, stop_words=None):
        if stop_words is None:
            self.stop_words = {}
        else:
            self.stop_words = set(stop_words)

    def transform(self, tokens):
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

    def transform(self, tokens):
        return list(filter(lambda t: t not in self.stop_words, tokens))

class Lemmatizer(BaseProcessor):
    def __init__(self):
        self.m = Mystem()

    def transform(self, tokens):
        lemm_str = " ".join(tokens)
        return list(filter(lambda s: s.strip(), self.m.lemmatize(lemm_str)))

class DefaultTextProcessor(TextProcessor):
    def __init__(self, token_pattern="(?u)\\b\\w\\w+\\b", stop_words=None):
        splitter = Splitter(token_pattern)
        filterer = DictionaryFilterer(stop_words)

        self.pipeline = Pipeline([
            ("split-text",    splitter),
            ("filter-tokens", filterer),
        ])

    def transform(self, raw_text):
        return self.pipeline.fit_transform(raw_text)

class DefaultDocumentProcessor(DocumentProcessor):
    def __init__(self, min_df=None, max_df=None, stop_lemmas=None):
        lemmatizer    = Lemmatizer()
        dict_filterer = DictionaryFilterer(stop_lemmas)
        freq_filterer = FrequencyFilterer(min_df, max_df)

        self.text_pipeline = Pipeline([
            ("lemmatize-tokens",     lemmatizer),
            ("filter-by-dictionary", dict_filterer),
            ("filter-by-frequency",  freq_filterer),
        ])

    def transform(self, tokens):
        modalities = dict.fromkeys(default_modalities, [])
        modalities["text"] = self.text_pipeline.fit_transform(tokens)
        return modalities