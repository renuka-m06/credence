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

import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, Optional

import httpx

from config import settings
from credence.resolve.cache import CacheStore, cache_store
from credence.resolve.matcher import CandidatePaper, MatchResult, compute_title_similarity, score_candidate
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
        offline_mode: Optional[bool] = None,
    ):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.cache = cache or cache_store
        if offline_mode is not None:
            self.offline_mode = offline_mode
        else:
            self.offline_mode = os.getenv("CREDENCE_OFFLINE", "").lower() in ("1", "true", "yes")

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

        # 2. Check offline mode: if offline, do NOT initiate live network request
        is_offline = self.offline_mode or (os.getenv("CREDENCE_OFFLINE", "").lower() in ("1", "true", "yes"))
        if is_offline:
            self.cache.log_search(
                reference_raw=reference_raw,
                source=self.name,
                status="offline_miss",
                query_string=cache_key,
                details={"offline_mode": True}
            )
            return None

        # 3. Live network request with timeout + retry/backoff
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

                    # Other non-retryable client error
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


def _parse_crossref_message(msg: dict[str, Any], default_doi: Optional[str] = None) -> CandidatePaper:
    """Parse Crossref API work message into a CandidatePaper with integrity metadata."""
    title = msg.get("title", [""])[0] if msg.get("title") else ""
    raw_doi = msg.get("DOI") or default_doi or ""
    clean_doi = extract_doi(raw_doi) or raw_doi or None

    issued = msg.get("issued", {}).get("date-parts", [[None]])
    year = None
    if issued and issued[0] and issued[0][0]:
        try:
            year = int(issued[0][0])
        except (ValueError, TypeError):
            pass

    authors = []
    for a in msg.get("author", []):
        family = a.get("family", "")
        given = a.get("given", "")
        if family:
            authors.append(f"{family}, {given}".strip(" ,"))

    journal = msg.get("container-title", [""])[0] if msg.get("container-title") else None

    # Retraction and correction detection from Crossref metadata
    is_retracted = False
    is_corrected = False
    retraction_details: dict[str, Any] = {}
    correction_details: dict[str, Any] = {}

    for upd in msg.get("update-to", []):
        upd_type = str(upd.get("type", "")).lower()
        if upd_type in ("retraction", "removal", "withdrawal"):
            is_retracted = True
            retraction_details = upd
        elif upd_type in ("correction", "erratum", "corrigendum", "expression_of_concern"):
            is_corrected = True
            correction_details = upd

    rel = msg.get("relation", {})
    if "is-retracted-by" in rel:
        is_retracted = True
        retraction_details["relation"] = rel["is-retracted-by"]
    if "is-corrected-by" in rel:
        is_corrected = True
        correction_details["relation"] = rel["is-corrected-by"]

    for assertion in msg.get("assertion", []):
        name = str(assertion.get("name", "")).lower()
        val = str(assertion.get("value", "")).lower()
        if "retract" in name or "retract" in val:
            is_retracted = True
            retraction_details["assertion"] = assertion
        elif "correct" in name or "errat" in name:
            is_corrected = True
            correction_details["assertion"] = assertion

    if re.match(r'^(?:retracted|retraction):', title.strip(), re.IGNORECASE):
        is_retracted = True
        retraction_details["title_flag"] = True

    # Publication type & review detection
    raw_type = str(msg.get("type", "journal-article")).lower()
    title_lower = title.lower()
    review_pattern = re.compile(r'\b(review|systematic review|meta-analysis|survey|overview of|literature review)\b', re.IGNORECASE)
    if raw_type in ("review-article", "review", "survey") or review_pattern.search(title_lower):
        publication_type = "review"
    else:
        publication_type = raw_type

    # Extract cited references for 1-hop traversal
    refs: list[dict[str, Any]] = []
    for r in msg.get("reference", []):
        ref_doi = extract_doi(r.get("DOI", ""))
        ref_title = r.get("article-title") or r.get("unstructured") or ""
        ref_author = r.get("author") or ""
        ref_year = None
        if r.get("year"):
            try:
                ref_year = int(re.search(r'\b(19\d{2}|20\d{2})\b', str(r["year"])).group(1))
            except Exception:
                pass
        refs.append({
            "key": r.get("key"),
            "doi": ref_doi,
            "title": ref_title,
            "author": ref_author,
            "year": ref_year,
            "unstructured": r.get("unstructured", ""),
        })

    cand = CandidatePaper(
        source="crossref",
        title=title,
        doi=clean_doi,
        authors=authors,
        year=year,
        journal=journal,
        is_retracted=is_retracted,
        is_corrected=is_corrected,
        retraction_details=retraction_details,
        correction_details=correction_details,
        publication_type=publication_type,
        references=refs,
        raw_payload=msg,
    )
    from credence.resolve.publication_status import check_publication_status
    check_publication_status(cand)
    return cand


class CrossrefClient(BaseClient):
    """Client for Crossref metadata API."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(
            name="crossref",
            base_url="https://api.crossref.org",
            *args,
            **kwargs,
        )

    def get_by_doi(self, doi: str, reference_raw: str = "") -> Optional[CandidatePaper]:
        clean_doi = extract_doi(doi) or doi
        headers = {"User-Agent": f"Credence/0.1.0 (mailto:{settings.crossref_mailto})"}
        data = self._get(f"works/{clean_doi}", headers=headers, reference_raw=reference_raw)
        if not data or "message" not in data:
            return None
        return _parse_crossref_message(data["message"], default_doi=clean_doi)

    def search_by_title(self, title: str, reference_raw: str = "") -> list[CandidatePaper]:
        headers = {"User-Agent": f"Credence/0.1.0 (mailto:{settings.crossref_mailto})"}
        params = {"query.bibliographic": title, "rows": 3}
        data = self._get("works", params=params, headers=headers, reference_raw=reference_raw)
        if not data or "message" not in data or "items" not in data["message"]:
            return []

        return [_parse_crossref_message(msg) for msg in data["message"]["items"]]


def _parse_openalex_work(data: dict[str, Any], default_doi: Optional[str] = None) -> CandidatePaper:
    """Parse OpenAlex work record into a CandidatePaper with integrity metadata."""
    raw_doi = data.get("doi", "") or default_doi or ""
    clean_doi = extract_doi(raw_doi) or (raw_doi.replace("https://doi.org/", "") if raw_doi else None)
    title = data.get("title") or ""
    year = data.get("publication_year")
    authors = [a.get("author", {}).get("display_name", "") for a in data.get("authorships", []) if a.get("author")]
    oa_url = data.get("open_access", {}).get("oa_url")

    # Retraction and correction detection from OpenAlex metadata
    is_retracted = bool(data.get("is_retracted", False))
    is_corrected = False
    retraction_details: dict[str, Any] = {}
    correction_details: dict[str, Any] = {}

    work_type = str(data.get("type", "")).lower()
    if work_type == "retraction" or re.match(r'^(?:retracted|retraction):', title.strip(), re.IGNORECASE):
        is_retracted = True
        retraction_details["type"] = "retraction"
    elif work_type in ("erratum", "paratext"):
        is_corrected = True
        correction_details["type"] = work_type

    if is_retracted and not retraction_details:
        retraction_details["is_retracted"] = True

    # Secondary source (review/survey) detection
    type_crossref = str(data.get("type_crossref", "")).lower()
    genre = str(data.get("genre", "")).lower()
    review_pattern = re.compile(r'\b(review|systematic review|meta-analysis|survey|overview of|literature review)\b', re.IGNORECASE)
    if (
        work_type in ("review", "survey")
        or type_crossref == "review-article"
        or genre == "review"
        or review_pattern.search(title)
    ):
        publication_type = "review"
    else:
        publication_type = work_type or "journal-article"

    refs: list[dict[str, Any]] = []
    for ref_item in data.get("referenced_works", []):
        if isinstance(ref_item, str):
            refs.append({"openalex_id": ref_item})
        elif isinstance(ref_item, dict):
            refs.append(ref_item)

    cand = CandidatePaper(
        source="openalex",
        title=title,
        doi=clean_doi,
        authors=authors,
        year=year,
        journal=data.get("primary_location", {}).get("source", {}).get("display_name") if data.get("primary_location") else None,
        open_access_pdf_url=oa_url,
        is_retracted=is_retracted,
        is_corrected=is_corrected,
        retraction_details=retraction_details,
        correction_details=correction_details,
        publication_type=publication_type,
        references=refs,
        raw_payload=data,
    )
    from credence.resolve.publication_status import check_publication_status
    check_publication_status(cand)
    return cand


class OpenAlexClient(BaseClient):
    """Client for OpenAlex academic graph API."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(
            name="openalex",
            base_url="https://api.openalex.org",
            *args,
            **kwargs,
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
        return _parse_openalex_work(data, default_doi=clean_doi)

    def search_by_title(self, title: str, reference_raw: str = "") -> list[CandidatePaper]:
        params = {"search": title, "per-page": 3, "mailto": settings.crossref_mailto}
        if settings.openalex_api_key:
            params["api_key"] = settings.openalex_api_key
        data = self._get("works", params=params, reference_raw=reference_raw)
        if not data or "results" not in data:
            return []

        return [_parse_openalex_work(w) for w in data.get("results", [])]


class SemanticScholarClient(BaseClient):
    """Client for Semantic Scholar Academic Graph API."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(
            name="semanticscholar",
            base_url="https://api.semanticscholar.org/graph/v1",
            *args,
            **kwargs,
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

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(
            name="unpaywall",
            base_url="https://api.unpaywall.org/v2",
            *args,
            **kwargs,
        )

    def get_oa_info(self, doi: str, reference_raw: str = "") -> Optional[dict[str, Any]]:
        clean_doi = extract_doi(doi) or doi
        params = {"email": settings.unpaywall_email}
        data = self._get(clean_doi, params=params, reference_raw=reference_raw)
        return data


class ArxivClient(BaseClient):
    """Client for arXiv API."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(
            name="arxiv",
            base_url="http://export.arxiv.org/api",
            *args,
            **kwargs,
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

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(
            name="pmc",
            base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
            *args,
            **kwargs,
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

    def __init__(
        self,
        cache: Optional[CacheStore] = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        offline_mode: Optional[bool] = None,
    ):
        self.cache = cache or cache_store
        self.offline_mode = offline_mode if offline_mode is not None else (os.getenv("CREDENCE_OFFLINE", "").lower() in ("1", "true", "yes"))
        self.crossref = CrossrefClient(cache=self.cache, timeout=timeout, max_retries=max_retries, backoff_factor=backoff_factor, offline_mode=self.offline_mode)
        self.openalex = OpenAlexClient(cache=self.cache, timeout=timeout, max_retries=max_retries, backoff_factor=backoff_factor, offline_mode=self.offline_mode)
        self.semanticscholar = SemanticScholarClient(cache=self.cache, timeout=timeout, max_retries=max_retries, backoff_factor=backoff_factor, offline_mode=self.offline_mode)
        self.unpaywall = UnpaywallClient(cache=self.cache, timeout=timeout, max_retries=max_retries, backoff_factor=backoff_factor, offline_mode=self.offline_mode)
        self.arxiv = ArxivClient(cache=self.cache, timeout=timeout, max_retries=max_retries, backoff_factor=backoff_factor, offline_mode=self.offline_mode)
        self.pmc = PmcClient(cache=self.cache, timeout=timeout, max_retries=max_retries, backoff_factor=backoff_factor, offline_mode=self.offline_mode)

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
                # Distinguish 404 (doi does not exist) from network error / offline miss
                logs = self.cache.get_search_logs(reference_raw=raw_ref)
                recent_statuses = [l["status"] for l in logs[-3:]] if logs else []
                is_net_err = any(s in ("error", "offline_miss") for s in recent_statuses)
                if is_net_err:
                    return score_candidate(reference, candidate=None, network_error=True)
                else:
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
            logs = self.cache.get_search_logs(reference_raw=raw_ref)
            recent_statuses = [l["status"] for l in logs[-3:]] if logs else []
            is_net_err = any(s in ("error", "offline_miss") for s in recent_statuses)
            return score_candidate(reference, candidate=None, network_error=is_net_err)

        # 3. Score all candidates and pick highest scoring result
        scored_results = [score_candidate(reference, c) for c in candidates]
        best_result = max(scored_results, key=lambda r: r.score)
        return best_result

    def follow_citation_hop(
        self,
        candidate: CandidatePaper,
        query_or_claim: str = "",
    ) -> Optional[CandidatePaper]:
        """Follow ONE citation hop from a secondary review/survey to the primary source.

        Args:
            candidate: The cited candidate paper identified as a review or survey.
            query_or_claim: The claim text or topic to match among cited references.

        Returns:
            The resolved primary CandidatePaper, or None if no valid hop was found.
        """
        if not candidate or not candidate.references:
            return None

        clean_query = query_or_claim.lower().strip()
        claim_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', clean_query))

        best_ref = None
        best_score = -1.0

        for ref_dict in candidate.references:
            ref_doi = ref_dict.get("doi")
            ref_title = ref_dict.get("title") or ref_dict.get("unstructured") or ""
            ref_openalex_id = ref_dict.get("openalex_id")

            # Score relevance to query
            ref_title_lower = ref_title.lower()
            if ref_title:
                t_score = compute_title_similarity(clean_query, ref_title)
                r_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', ref_title_lower))
                overlap = len(claim_words & r_words) / max(len(claim_words), 1)
                combined = 0.5 * t_score + 0.5 * overlap
            elif ref_doi:
                combined = 0.5
            elif ref_openalex_id:
                combined = 0.4
            else:
                combined = 0.0

            if combined > best_score:
                best_score = combined
                best_ref = ref_dict

        if not best_ref:
            return None

        hop_doi = best_ref.get("doi")
        hop_title = best_ref.get("title")
        hop_oa = best_ref.get("openalex_id")

        # Fast path: If the reference payload already contains rich title and abstract (e.g. pre-cached or fixture)
        if hop_title and best_ref.get("abstract"):
            return CandidatePaper(
                source="citation_hop",
                title=hop_title,
                doi=hop_doi,
                authors=[best_ref.get("author")] if best_ref.get("author") else [],
                year=best_ref.get("year"),
                abstract=best_ref.get("abstract"),
            )

        # Resolve the selected reference via DOI, title, or OpenAlex ID
        if hop_doi:
            primary = self.crossref.get_by_doi(hop_doi)
            if not primary:
                primary = self.openalex.get_by_doi(hop_doi)
            if not primary:
                primary = self.semanticscholar.get_by_doi(hop_doi)
            if primary:
                return primary

        if hop_title and len(hop_title.strip()) > 10:
            cands = self.crossref.search_by_title(hop_title)
            if not cands:
                cands = self.openalex.search_by_title(hop_title)
            if cands:
                return cands[0]

        if hop_oa:
            clean_id = str(hop_oa).split("/")[-1]
            params = {}
            if settings.openalex_api_key:
                params["api_key"] = settings.openalex_api_key
            data = self.openalex._get(f"works/{clean_id}", params=params)
            if data and "id" in data:
                return _parse_openalex_work(data)

        # If payload already contained mock/direct fields for offline fixtures
        if hop_title:
            return CandidatePaper(
                source="citation_hop",
                title=hop_title,
                doi=hop_doi,
                authors=[best_ref.get("author")] if best_ref.get("author") else [],
                year=best_ref.get("year"),
                abstract=best_ref.get("abstract"),
            )

        return None
