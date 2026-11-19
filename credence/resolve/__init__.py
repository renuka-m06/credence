"""Resolve subpackage: Paper retrieval across academic databases with cache-first ledger."""

from credence.resolve.cache import CacheStore, cache_store
from credence.resolve.matcher import CandidatePaper, MatchResult, check_doi_mismatch, score_candidate
from credence.resolve.reference import Reference, extract_doi, parse_reference
from credence.resolve.sources import (
    ArxivClient,
    CrossrefClient,
    OpenAlexClient,
    PmcClient,
    SemanticScholarClient,
    UnifiedResolver,
    UnpaywallClient,
)

__all__ = [
    "CacheStore",
    "cache_store",
    "Reference",
    "extract_doi",
    "parse_reference",
    "CandidatePaper",
    "MatchResult",
    "score_candidate",
    "check_doi_mismatch",
    "CrossrefClient",
    "OpenAlexClient",
    "SemanticScholarClient",
    "UnpaywallClient",
    "ArxivClient",
    "PmcClient",
    "UnifiedResolver",
]
