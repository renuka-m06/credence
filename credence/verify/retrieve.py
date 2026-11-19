"""Evidence passage retriever combining BM25, semantic embeddings, and number-regex reranking.

Rules (AGENTS.md):
- Python decides every deterministic fact.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class RetrievedPassage:
    """An evidence passage retrieved from the source paper."""
    text: str
    passage_id: int
    span: tuple[int, int]
    bm25_score: float = 0.0
    semantic_score: float = 0.0
    number_score: float = 0.0
    final_score: float = 0.0
    extracted_numbers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Passage Segmentation
# ---------------------------------------------------------------------------

def segment_passages(source_text: str, window_size: int = 2, step: int = 1) -> list[RetrievedPassage]:
    """Segment source text into overlapping multi-sentence passages with span tracking.
    
    Prevents splitting on decimal points within numbers (e.g. 12.1%).
    """
    passages: list[RetrievedPassage] = []
    if not source_text or not source_text.strip():
        return passages

    # Match sentences without splitting on decimal points between digits
    pattern = re.compile(r'.*?(?:(?<!\d)[.!?](?:\s+|$|\n)|\n{2,}|\Z)', re.DOTALL)
    sentences: list[tuple[str, int, int]] = []
    for m in pattern.finditer(source_text):
        txt = m.group(0).strip()
        if txt:
            sentences.append((txt, m.start(), m.end()))

    if not sentences:
        # Fallback to paragraph splitting
        paragraphs = source_text.split("\n\n")
        pos = 0
        for idx, p in enumerate(paragraphs):
            p_clean = p.strip()
            if p_clean:
                start = source_text.find(p_clean, pos)
                end = start + len(p_clean)
                passages.append(RetrievedPassage(
                    text=p_clean,
                    passage_id=idx,
                    span=(start, end)
                ))
                pos = end
        return passages

    # Build sliding windows
    passage_id = 0
    for i in range(0, len(sentences), step):
        window = sentences[i : i + window_size]
        if not window:
            break
        text = " ".join(s[0] for s in window).strip()
        span_start = window[0][1]
        span_end = window[-1][2]
        passages.append(RetrievedPassage(
            text=text,
            passage_id=passage_id,
            span=(span_start, span_end)
        ))
        passage_id += 1
        if i + window_size >= len(sentences):
            break

    return passages


# ---------------------------------------------------------------------------
# BM25 Okapi Pure-Python Engine
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Simple alphanumeric tokenizer."""
    return re.findall(r'\b[a-zA-Z0-9_%.-]+\b', text.lower())


class BM25Engine:
    """Pure-Python BM25 Okapi implementation."""

    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_tokens = [_tokenize(doc) for doc in corpus]
        self.doc_lens = [len(tokens) for tokens in self.doc_tokens]
        self.avg_doc_len = sum(self.doc_lens) / self.corpus_size if self.corpus_size else 1.0

        # Term frequencies and document frequencies
        self.doc_freqs: dict[str, int] = {}
        for tokens in self.doc_tokens:
            seen = set(tokens)
            for token in seen:
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1

        # Inverse document frequency
        self.idf: dict[str, float] = {}
        for term, freq in self.doc_freqs.items():
            self.idf[term] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)

    def score(self, query: str) -> list[float]:
        """Compute BM25 scores for all corpus documents against query."""
        q_tokens = _tokenize(query)
        scores = [0.0] * self.corpus_size

        for term in q_tokens:
            if term not in self.idf:
                continue
            idf_val = self.idf[term]

            for doc_idx, tokens in enumerate(self.doc_tokens):
                tf = tokens.count(term)
                if tf == 0:
                    continue
                doc_len = self.doc_lens[doc_idx]
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                scores[doc_idx] += idf_val * (numerator / denominator)

        # Normalize to [0.0, 1.0]
        max_score = max(scores) if scores else 0.0
        if max_score > 0.0:
            return [round(s / max_score, 4) for s in scores]
        return scores


# ---------------------------------------------------------------------------
# Semantic / Token Similarity Engine
# ---------------------------------------------------------------------------

def compute_semantic_similarity(query: str, passage: str) -> float:
    """Compute semantic token overlap and character n-gram cosine similarity."""
    q_tokens = set(_tokenize(query))
    p_tokens = set(_tokenize(passage))
    if not q_tokens or not p_tokens:
        return 0.0

    # Jaccard + Overlap
    common = q_tokens & p_tokens
    overlap = len(common) / min(len(q_tokens), len(p_tokens))
    jaccard = len(common) / len(q_tokens | p_tokens)

    # Bigram character similarity
    def get_bigrams(s: str) -> set[str]:
        s_clean = s.lower()
        return {s_clean[i:i+2] for i in range(len(s_clean)-1)}

    q_bigrams = get_bigrams(query)
    p_bigrams = get_bigrams(passage)
    bigram_sim = len(q_bigrams & p_bigrams) / max(len(q_bigrams | p_bigrams), 1)

    score = 0.5 * overlap + 0.3 * jaccard + 0.2 * bigram_sim
    return round(min(1.0, max(0.0, score)), 4)


# ---------------------------------------------------------------------------
# Number-Regex Pass
# ---------------------------------------------------------------------------

NUMBER_PATTERN = re.compile(
    r'\b(\d+(?:\.\d+)?\s*(?:%|percent|percentage\s*points?|pp|fold|patients?|students?|subjects?|cohort)?)\b',
    re.IGNORECASE
)


def score_number_pass(query: str, passage: str) -> tuple[float, list[str]]:
    """Scan passage for numerical entities and boost passages with empirical statistics."""
    query_numbers = [m.group(0).lower().strip() for m in NUMBER_PATTERN.finditer(query)]
    passage_numbers = [m.group(0).lower().strip() for m in NUMBER_PATTERN.finditer(passage)]

    if not passage_numbers:
        return 0.0, []

    # Check for direct numerical match
    has_exact_match = False
    for qn in query_numbers:
        for pn in passage_numbers:
            # Check numbers match (e.g. "12.1%" or "40")
            q_digits = re.findall(r'\d+(?:\.\d+)?', qn)
            p_digits = re.findall(r'\d+(?:\.\d+)?', pn)
            if q_digits and p_digits and q_digits[0] == p_digits[0]:
                has_exact_match = True
                break

    if has_exact_match:
        score = 1.0
    elif query_numbers and passage_numbers:
        # Passage has numbers while query also looks for statistical numbers
        score = 0.7
    else:
        # Passage has empirical numbers
        score = 0.4

    return score, passage_numbers


# ---------------------------------------------------------------------------
# Hybrid Reranking Retrieval Pipeline
# ---------------------------------------------------------------------------

def retrieve_evidence_passages(
    query: str,
    source_text: str,
    top_k: int = 5,
    w_bm25: float = 0.40,
    w_semantic: float = 0.30,
    w_number: float = 0.30,
) -> list[RetrievedPassage]:
    """Retrieve and rerank candidate evidence passages from source paper.

    Combines:
      - BM25 lexical relevance
      - Semantic token similarity
      - Number-regex statistical boost
    """
    passages = segment_passages(source_text)
    if not passages:
        return []

    # 1. BM25 scoring
    bm25_engine = BM25Engine([p.text for p in passages])
    bm25_scores = bm25_engine.score(query)

    # 2. Semantic & Number scoring
    for idx, p in enumerate(passages):
        p.bm25_score = bm25_scores[idx]
        p.semantic_score = compute_semantic_similarity(query, p.text)
        p.number_score, p.extracted_numbers = score_number_pass(query, p.text)

        # Weighted reranking fusion
        p.final_score = round(
            w_bm25 * p.bm25_score + w_semantic * p.semantic_score + w_number * p.number_score,
            4
        )

    # Sort descending by final fused score
    passages.sort(key=lambda x: x.final_score, reverse=True)
    return passages[:top_k]
