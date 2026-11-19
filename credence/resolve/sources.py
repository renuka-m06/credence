"""Academic database retrieval clients with cache-first architecture, timeout, and backoff.

Sources:
- Crossref
- OpenAlex
- Semantic Scholar
- Unpaywall
- arXiv
- PubMed Central (PMC)

Rules (AGENTS.md):
- No HTTP call bypasses resolve/cache.py (cache-first) with timeout + retry/backoff.
- "Not found in databases" != fabricated. Report what was searched and where.
"""

from __future__ import annotations

import time
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, Optional

import httpx

from config import settings
from credence.resolve.cache import CacheStore, cache_store
from credence.resolve.matcher import CandidatePaper, MatchResult, score_candidate
from credence.resolve.reference import Reference, extract_doi


class BaseClient:
    """Base HTTP client ensuring cache-first execution, timeout, and exponential backoff."""

    def __init__(
        self,
        name: str,
        base_url: str,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        cache: Optional[CacheStore] = None,
    ):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.cache = cache or cache_store

    def _get(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        reference_raw: str = "",
    ) -> Optional[dict[str, Any]]:
        """Cache-first HTTP GET with retry and exponential backoff."""
        clean_endpoint = endpoint.lstrip("/")
        query_str = urllib.parse.urlencode(sorted(params.items())) if params else ""
        cache_key = f"{clean_endpoint}?{query_str}" if query_str else clean_endpoint
        full_url = f"{self.base_url}/{clean_endpoint}"

        # 1. Cache-first lookup
        cached = self.cache.get(self.name, cache_key)
        if cached is not None:
            self.cache.log_search(
                reference_raw=reference_raw,
                source=self.name,
                status="cached",
                query_string=cache_key,
                details={"cached": True}
            )
            return cached

        # 2. Network request with timeout + retry/backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.get(full_url, params=params, headers=headers)

                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                        except Exception:
                            data = {"text": resp.text}

                        self.cache.set(self.name, cache_key, data, http_status=200)
                        self.cache.log_search(
                            reference_raw=reference_raw,
                            source=self.name,
                            status="hit",
                            query_string=cache_key,
                        )
                        return data

                    if resp.status_code == 404:
                        # Negative cache for 24h
                        self.cache.set(self.name, cache_key, {}, http_status=404, ttl_seconds=86400)
                        self.cache.log_search(
                            reference_raw=reference_raw,
                            source=self.name,
                            status="not_found",
                            query_string=cache_key,
                            details={"status_code": 404}
                        )
                        return None

                    if resp.status_code in (429, 500, 502, 503, 504):
                        time.sleep(self.backoff_factor * (2 ** attempt))
                        continue

                    # Other client error
                    break

            except (httpx.TimeoutException, httpx.NetworkError, Exception) as exc:
                last_error = exc
                time.sleep(self.backoff_factor * (2 ** attempt))

        self.cache.log_search(
            reference_raw=reference_raw,
            source=self.name,
            status="error",
            query_string=cache_key,
            details={"error": str(last_error)}
        )
        return None


class CrossrefClient(BaseClient):
    """Client for Crossref metadata API."""

    def __init__(self, cache: Optional[CacheStore] = None):
        super().__init__(
            name="crossref",
            base_url="https://api.crossref.org",
            cache=cache,
        )

    def get_by_doi(self, doi: str, reference_raw: str = "") -> Optional[CandidatePaper]:
        clean_doi = extract_doi(doi) or doi
        headers = {"User-Agent": f"Credence/0.1.0 (mailto:{settings.crossref_mailto})"}
        data = self._get(f"works/{clean_doi}", headers=headers, reference_raw=reference_raw)
        if not data or "message" not in data:
            return None

        msg = data["message"]
        title = msg.get("title", [""])[0] if msg.get("title") else ""
        year = None
        issued = msg.get("issued", {}).get("date-parts", [[None]])
        if issued and issued[0] and issued[0][0]:
            try:
                year = int(issued[0][0])
            except ValueError:
                pass

        authors = []
        for a in msg.get("author", []):
            family = a.get("family", "")
            given = a.get("given", "")
            if family:
                authors.append(f"{family}, {given}".strip(" ,"))

        journal = msg.get("container-title", [""])[0] if msg.get("container-title") else None

        return CandidatePaper(
            source="crossref",
            title=title,
            doi=clean_doi,
            authors=authors,
            year=year,
            journal=journal,
            raw_payload=msg,
        )

    def search_by_title(self, title: str, reference_raw: str = "") -> list[CandidatePaper]:
        headers = {"User-Agent": f"Credence/0.1.0 (mailto:{settings.crossref_mailto})"}
        params = {"query.bibliographic": title, "rows": 3}
        data = self._get("works", params=params, headers=headers, reference_raw=reference_raw)
        if not data or "message" not in data or "items" not in data["message"]:
            return []

        results = []
        for msg in data["message"]["items"]:
            t = msg.get("title", [""])[0] if msg.get("title") else ""
            issued = msg.get("issued", {}).get("date-parts", [[None]])
            year = int(issued[0][0]) if issued and issued[0] and issued[0][0] else None
            authors = [f"{a.get('family', '')}, {a.get('given', '')}".strip(" ,") for a in msg.get("author", []) if a.get("family")]
            results.append(CandidatePaper(
                source="crossref",
                title=t,
                doi=msg.get("DOI"),
                authors=authors,
                year=year,
                journal=msg.get("container-title", [""])[0] if msg.get("container-title") else None,
                raw_payload=msg,
            ))
        return results


class OpenAlexClient(BaseClient):
    """Client for OpenAlex academic graph API."""

    def __init__(self, cache: Optional[CacheStore] = None):
        super().__init__(
            name="openalex",
            base_url="https://api.openalex.org",
            cache=cache,
        )

    def get_by_doi(self, doi: str, reference_raw: str = "") -> Optional[CandidatePaper]:
        clean_doi = extract_doi(doi) or doi
        params = {}
        if settings.openalex_api_key:
            params["api_key"] = settings.openalex_api_key
        params["mailto"] = settings.crossref_mailto

        data = self._get(f"works/https://doi.org/{clean_doi}", params=params, reference_raw=reference_raw)
        if not data or "id" not in data:
            return None

        title = data.get("title") or ""
        year = data.get("publication_year")
        authors = [a.get("author", {}).get("display_name", "") for a in data.get("authorships", []) if a.get("author")]
        oa_url = data.get("open_access", {}).get("oa_url")
        retracted = bool(data.get("is_retracted", False))

        return CandidatePaper(
            source="openalex",
            title=title,
            doi=clean_doi,
            authors=authors,
            year=year,
            journal=data.get("primary_location", {}).get("source", {}).get("display_name") if data.get("primary_location") else None,
            open_access_pdf_url=oa_url,
            is_retracted=retracted,
            raw_payload=data,
        )

    def search_by_title(self, title: str, reference_raw: str = "") -> list[CandidatePaper]:
        params = {"search": title, "per-page": 3, "mailto": settings.crossref_mailto}
        if settings.openalex_api_key:
            params["api_key"] = settings.openalex_api_key
        data = self._get("works", params=params, reference_raw=reference_raw)
        if not data or "results" not in data:
            return []

        candidates = []
        for w in data.get("results", []):
            doi = w.get("doi", "").replace("https://doi.org/", "") if w.get("doi") else None
            authors = [a.get("author", {}).get("display_name", "") for a in w.get("authorships", []) if a.get("author")]
            candidates.append(CandidatePaper(
                source="openalex",
                title=w.get("title") or "",
                doi=doi,
                authors=authors,
                year=w.get("publication_year"),
                open_access_pdf_url=w.get("open_access", {}).get("oa_url"),
                is_retracted=bool(w.get("is_retracted", False)),
                raw_payload=w,
            ))
        return candidates


class SemanticScholarClient(BaseClient):
    """Client for Semantic Scholar Academic Graph API."""

    def __init__(self, cache: Optional[CacheStore] = None):
        super().__init__(
            name="semanticscholar",
            base_url="https://api.semanticscholar.org/graph/v1",
            cache=cache,
        )

    def get_by_doi(self, doi: str, reference_raw: str = "") -> Optional[CandidatePaper]:
        clean_doi = extract_doi(doi) or doi
        headers = {}
        if settings.semantic_scholar_api_key:
            headers["x-api-key"] = settings.semantic_scholar_api_key
        params = {"fields": "title,authors,year,abstract,openAccessPdf"}

        data = self._get(f"paper/DOI:{clean_doi}", params=params, headers=headers, reference_raw=reference_raw)
        if not data or "title" not in data:
            return None

        authors = [a.get("name", "") for a in data.get("authors", [])]
        pdf_url = data.get("openAccessPdf", {}).get("url") if data.get("openAccessPdf") else None

        return CandidatePaper(
            source="semanticscholar",
            title=data.get("title") or "",
            doi=clean_doi,
            authors=authors,
            year=data.get("year"),
            abstract=data.get("abstract"),
            open_access_pdf_url=pdf_url,
            raw_payload=data,
        )


class UnpaywallClient(BaseClient):
    """Client for Unpaywall open access discovery."""

    def __init__(self, cache: Optional[CacheStore] = None):
        super().__init__(
            name="unpaywall",
            base_url="https://api.unpaywall.org/v2",
            cache=cache,
        )

    def get_oa_info(self, doi: str, reference_raw: str = "") -> Optional[dict[str, Any]]:
        clean_doi = extract_doi(doi) or doi
        params = {"email": settings.unpaywall_email}
        data = self._get(clean_doi, params=params, reference_raw=reference_raw)
        return data


class ArxivClient(BaseClient):
    """Client for arXiv API."""

    def __init__(self, cache: Optional[CacheStore] = None):
        super().__init__(
            name="arxiv",
            base_url="http://export.arxiv.org/api",
            cache=cache,
        )

    def search_by_title(self, title: str, reference_raw: str = "") -> list[CandidatePaper]:
        params = {"search_query": f"ti:{title}", "max_results": 3}
        data = self._get("query", params=params, reference_raw=reference_raw)
        if not data or "text" not in data:
            return []

        candidates = []
        try:
            root = ET.fromstring(data["text"])
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns):
                t = entry.find("atom:title", ns)
                title_text = t.text.strip().replace("\n", " ") if t is not None and t.text else ""
                published = entry.find("atom:published", ns)
                year = int(published.text[:4]) if published is not None and published.text else None
                authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns) if a.find("atom:name", ns) is not None]
                candidates.append(CandidatePaper(
                    source="arxiv",
                    title=title_text,
                    authors=authors,
                    year=year,
                    raw_payload={"xml": ET.tostring(entry, encoding="unicode")},
                ))
        except Exception:
            pass
        return candidates


class PmcClient(BaseClient):
    """Client for PubMed Central E-utilities."""

    def __init__(self, cache: Optional[CacheStore] = None):
        super().__init__(
            name="pmc",
            base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
            cache=cache,
        )

    def search_pmc(self, term: str, reference_raw: str = "") -> list[CandidatePaper]:
        params = {"db": "pmc", "term": term, "retmode": "json", "retmax": 3}
        data = self._get("esearch.fcgi", params=params, reference_raw=reference_raw)
        if not data or "esearchresult" not in data or "idlist" not in data["esearchresult"]:
            return []
        # Return lightweight candidates
        return [CandidatePaper(source="pmc", title=f"PMC Record {pmcid}", url=f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/") for pmcid in data["esearchresult"]["idlist"]]


class UnifiedResolver:
    """Orchestrates multi-source paper retrieval and candidate scoring."""

    def __init__(self, cache: Optional[CacheStore] = None):
        self.cache = cache or cache_store
        self.crossref = CrossrefClient(cache=self.cache)
        self.openalex = OpenAlexClient(cache=self.cache)
        self.semanticscholar = SemanticScholarClient(cache=self.cache)
        self.unpaywall = UnpaywallClient(cache=self.cache)
        self.arxiv = ArxivClient(cache=self.cache)
        self.pmc = PmcClient(cache=self.cache)

    def resolve(self, reference: Reference) -> MatchResult:
        """Resolve a Reference across academic databases and score the best candidate."""
        raw_ref = reference.raw_text

        # 1. If DOI is present, attempt direct DOI lookups first
        if reference.doi:
            cand = self.crossref.get_by_doi(reference.doi, reference_raw=raw_ref)
            if not cand:
                cand = self.openalex.get_by_doi(reference.doi, reference_raw=raw_ref)
            if not cand:
                cand = self.semanticscholar.get_by_doi(reference.doi, reference_raw=raw_ref)

            if cand:
                return score_candidate(reference, cand)
            else:
                # DOI lookup returned 404/no-record across all sources -> fake DOI
                return score_candidate(reference, candidate=None, doi_lookup_failed=True)

        # 2. Search by title across sources
        candidates: list[CandidatePaper] = []
        if reference.title:
            candidates.extend(self.crossref.search_by_title(reference.title, reference_raw=raw_ref))
            if not candidates:
                candidates.extend(self.openalex.search_by_title(reference.title, reference_raw=raw_ref))
            if not candidates:
                candidates.extend(self.arxiv.search_by_title(reference.title, reference_raw=raw_ref))

        if not candidates:
            return score_candidate(reference, candidate=None)

        # 3. Score all candidates and pick highest scoring result
        scored_results = [score_candidate(reference, c) for c in candidates]
        best_result = max(scored_results, key=lambda r: r.score)
        return best_result
