"""Pure-Python deterministic verification checks for scientific claims and quotes.

Golden Rules (AGENTS.md):
1. LLM judges MEANING only. Python decides every deterministic fact: quote existence,
   number/unit equality, hedge words. The LLM can NEVER override a code check.
2. If a returned quote is not found in the source after normalization -> discard that
   slot -> "Needs review". Log it so the benchmark counts caught hallucinations.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CheckResult:
    """Result of a deterministic verification check."""
    passed: bool
    reason: str
    details: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        """Allow CheckResult to be evaluated in boolean contexts."""
        return self.passed

    def __eq__(self, other: object) -> bool:
        """Support direct equality checks with booleans (e.g. res == False)."""
        if isinstance(other, bool):
            return self.passed == other
        return super().__eq__(other)


# ---------------------------------------------------------------------------
# Quote Normalization and Existence Check
# ---------------------------------------------------------------------------

QUOTE_CHARS = {'"', "'", '“', '”', '‘', '’', '«', '»', '„', '‟', '`'}


def strip_outer_quotes(s: str) -> str:
    """Strip leading/trailing quotation marks or apostrophes (ASCII or Unicode)."""
    s = s.strip()
    while len(s) >= 2 and (s[0] in QUOTE_CHARS and s[-1] in QUOTE_CHARS):
        s = s[1:-1].strip()
    return s


def normalize_text(text: str, dehyphenate: bool = True) -> str:
    """Normalize text by standardizing unicode, punctuation, linebreaks, and spaces."""
    if not text:
        return ""

    # Unicode NFKC normalization
    text = unicodedata.normalize("NFKC", text)

    # Standardize quotation marks
    text = re.sub(r'[\u201C\u201D\u201E\u201F\u00AB\u00BB]', '"', text)
    text = re.sub(r'[\u2018\u2019\u201A\u201B\u2032\u2035]', "'", text)

    # Standardize dashes and hyphens
    text = re.sub(r'[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]', "-", text)

    # Standardize linebreaks to \n
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    if dehyphenate:
        # Normalize hyphenated word breaks at end of line (e.g. "treatment-\n  associated" -> "treatment-associated")
        text = re.sub(r'(\b\w+)-\s*\n\s*(\w+\b)', r'\1-\2', text)

    # Replace all whitespace sequences (newlines, tabs, multiple spaces) with a single space
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def quote_check(quote: str, source_text: str) -> CheckResult:
    """Deterministically check if quote verbatim exists in the source text.

    Args:
        quote: The verbatim quote candidate returned by LLM or extraction.
        source_text: The full source paper or section text.

    Returns:
        CheckResult indicating whether the quote exists after normalization.
    """
    if not quote or not quote.strip():
        return CheckResult(
            passed=False,
            reason="Empty quote provided",
            details={"error": "empty_quote"}
        )

    if not source_text or not source_text.strip():
        return CheckResult(
            passed=False,
            reason="Empty source text provided",
            details={"error": "empty_source_text"}
        )

    # Strip outer quotes first
    cleaned_quote = strip_outer_quotes(quote.strip())
    norm_quote = normalize_text(cleaned_quote)
    norm_quote = strip_outer_quotes(norm_quote)

    if not norm_quote:
        return CheckResult(
            passed=False,
            reason="Quote is empty after normalization",
            details={"error": "empty_normalized_quote"}
        )

    # Generate source variants for robust matching:
    # 1. Hyphens preserved across line breaks (e.g. treatment-associated)
    source_hyphen_preserved = normalize_text(source_text, dehyphenate=True)

    # 2. Syllable-break hyphens removed (e.g. evalu-\n ation -> evaluation)
    source_syllable_joined = re.sub(r'(\b\w+)-\s*(\w+\b)', r'\1\2', source_hyphen_preserved)

    # 3. Raw whitespace normalized
    source_raw = normalize_text(source_text, dehyphenate=False)

    variants = [
        ("exact_normalized_hyphen", source_hyphen_preserved),
        ("exact_normalized_syllable_joined", source_syllable_joined),
        ("exact_normalized_raw", source_raw),
    ]

    for match_type, src in variants:
        pos = src.find(norm_quote)
        if pos != -1:
            return CheckResult(
                passed=True,
                reason="Quote found in source text after normalization",
                details={
                    "match_type": match_type,
                    "span": (pos, pos + len(norm_quote)),
                    "quote_length": len(norm_quote),
                }
            )

    # Case-insensitive fallback
    norm_quote_lower = norm_quote.lower()
    for match_type, src in variants:
        pos = src.lower().find(norm_quote_lower)
        if pos != -1:
            return CheckResult(
                passed=True,
                reason="Quote found in source text (case-insensitive match)",
                details={
                    "match_type": f"{match_type}_case_insensitive",
                    "span": (pos, pos + len(norm_quote)),
                    "quote_length": len(norm_quote),
                    "case_mismatch": True,
                }
            )

    # Quote was NOT found -> Rejected (caught hallucination)
    return CheckResult(
        passed=False,
        reason="Fabricated quote: quote not found in source text after normalization",
        details={
            "match_type": "not_found",
            "quote_tested": norm_quote,
        }
    )


# ---------------------------------------------------------------------------
# Number & Unit Check
# ---------------------------------------------------------------------------

@dataclass
class NumberToken:
    """Representation of an extracted number with its unit/type."""
    raw: str
    value: float
    unit: str  # 'percent', 'percentage_points', 'day', 'dimensionless', etc.
    span: tuple[int, int]


# Regex patterns for numbers and units
_NUM_PATTERN = re.compile(
    r'(?<![A-Za-z0-9_])'
    r'([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)'
    r'\s*'
    r'(percentage\s*points?|percentage-points?|percent|per\s*cent|%|pp\b|p\.p\.|-(?:day|year|month|week|fold|arm|phase)\b)?',
    re.IGNORECASE
)

PERCENT_UNITS = {"percent", "percentage_points"}


def _canonicalize_unit(raw_unit: Optional[str]) -> str:
    """Map raw unit string to standard canonical representation."""
    if not raw_unit:
        return "dimensionless"
    unit_clean = raw_unit.lower().strip()
    if unit_clean.startswith("-"):
        return unit_clean[1:]  # e.g., "-day" -> "day"
    unit_clean = unit_clean.replace("-", " ")
    if unit_clean in ("%", "percent", "per cent"):
        return "percent"
    if unit_clean in ("percentage point", "percentage points", "pp", "p.p."):
        return "percentage_points"
    return unit_clean


def extract_numbers(text: str) -> list[NumberToken]:
    """Extract all numbers and their associated percentage/points/units from text."""
    normalized = normalize_text(text)
    tokens: list[NumberToken] = []

    for match in _NUM_PATTERN.finditer(normalized):
        num_str, raw_unit = match.groups()
        try:
            val = float(num_str.replace(",", ""))
        except ValueError:
            continue

        unit = _canonicalize_unit(raw_unit)
        tokens.append(NumberToken(
            raw=match.group(0).strip(),
            value=val,
            unit=unit,
            span=(match.start(), match.end())
        ))

    return tokens


def number_check(
    claim_text: str,
    quote_text: str,
    rel_tol: float = 1e-4,
    abs_tol: float = 1e-4
) -> CheckResult:
    """Deterministic numerical consistency check between claim and evidence quote.

    Flags:
      - 30% vs 12.1% -> numerical value mismatch
      - percent vs percentage points -> unit mismatch
      - numbers in claim missing in quote -> mismatch
    """
    # Strip citation markers (e.g. [1], [4], [1-3]) so citation keys are not treated as numbers
    clean_claim = re.sub(r'\[\s*\d+(?:\s*[-–,]\s*\d+)*\s*\]', '', claim_text)
    claim_numbers = extract_numbers(clean_claim)
    quote_numbers = extract_numbers(quote_text)

    # If the claim makes no numerical assertions, there is no numerical contradiction
    if not claim_numbers:
        return CheckResult(
            passed=True,
            reason="No numerical assertions in claim to verify",
            details={"claim_numbers": [], "quote_numbers": [q.raw for q in quote_numbers]}
        )

    # Claim asserts numbers, but the quote has none
    if not quote_numbers:
        return CheckResult(
            passed=False,
            reason=f"Numerical mismatch: claim asserts numbers ({[c.raw for c in claim_numbers]}) but quote contains no numerical data",
            details={
                "mismatch_type": "missing_quote_numbers",
                "claim_numbers": [c.raw for c in claim_numbers],
                "quote_numbers": [],
            }
        )

    mismatches: list[dict[str, Any]] = []

    for c_num in claim_numbers:
        # Distinguish percentage/points tokens from general/modifier numbers
        if c_num.unit in PERCENT_UNITS:
            # Candidates in quote are quote percentage-domain tokens
            quote_pct_candidates = [q for q in quote_numbers if q.unit in PERCENT_UNITS]
            if not quote_pct_candidates:
                mismatches.append({
                    "type": "missing_quote_percentage",
                    "claim_token": c_num.raw,
                    "claim_value": c_num.value,
                    "claim_unit": c_num.unit,
                    "quote_candidates": [q.raw for q in quote_numbers],
                    "message": f"Claim asserts {c_num.raw} but quote has no percentage or percentage-point data"
                })
                continue

            # Check for exact value match in quote percentage tokens
            value_matches = [
                q for q in quote_pct_candidates
                if math.isclose(c_num.value, q.value, rel_tol=rel_tol, abs_tol=abs_tol)
            ]

            if value_matches:
                # Value matches; verify unit equality (e.g. percent vs percentage-points)
                exact_unit_matches = [q for q in value_matches if q.unit == c_num.unit]
                if not exact_unit_matches:
                    mismatches.append({
                        "type": "unit_mismatch",
                        "claim_token": c_num.raw,
                        "claim_value": c_num.value,
                        "claim_unit": c_num.unit,
                        "quote_candidates": [q.raw for q in value_matches],
                        "quote_units": [q.unit for q in value_matches],
                        "message": f"Unit mismatch: claim specifies '{c_num.unit}' but quote specifies '{value_matches[0].unit}'"
                    })
            else:
                # Value does not match any quote percentage
                mismatches.append({
                    "type": "value_mismatch",
                    "claim_token": c_num.raw,
                    "claim_value": c_num.value,
                    "claim_unit": c_num.unit,
                    "quote_candidates": [q.raw for q in quote_pct_candidates],
                    "message": f"Numerical value mismatch: claim asserts {c_num.raw} but quote reports {[q.raw for q in quote_pct_candidates]}"
                })
        else:
            # General number or modifier (e.g. 30 in 30-day, 1450 patients)
            # Find matching value in quote
            matching_values = [
                q for q in quote_numbers
                if math.isclose(c_num.value, q.value, rel_tol=rel_tol, abs_tol=abs_tol)
            ]
            if not matching_values:
                mismatches.append({
                    "type": "value_mismatch",
                    "claim_token": c_num.raw,
                    "claim_value": c_num.value,
                    "claim_unit": c_num.unit,
                    "quote_candidates": [q.raw for q in quote_numbers],
                    "message": f"Value mismatch: claim asserts {c_num.raw} which was not found in quote"
                })

    if mismatches:
        # Prioritize value mismatch, then unit mismatch
        value_mismatches = [m for m in mismatches if m["type"] == "value_mismatch"]
        unit_mismatches = [m for m in mismatches if m["type"] == "unit_mismatch"]

        if value_mismatches:
            vm = value_mismatches[0]
            reason = f"Numerical value mismatch: claim asserts {vm['claim_token']} which does not match quote numbers"
        elif unit_mismatches:
            um = unit_mismatches[0]
            reason = f"Unit mismatch: claim specifies '{um['claim_token']}' but quote uses '{um['quote_candidates'][0]}'"
        else:
            reason = mismatches[0]["message"]

        return CheckResult(
            passed=False,
            reason=reason,
            details={
                "mismatches": mismatches,
                "claim_numbers": [c.raw for c in claim_numbers],
                "quote_numbers": [q.raw for q in quote_numbers],
            }
        )

    return CheckResult(
        passed=True,
        reason="Numerical assertions in claim are consistent with quote",
        details={
            "claim_numbers": [c.raw for c in claim_numbers],
            "quote_numbers": [q.raw for q in quote_numbers],
        }
    )


# ---------------------------------------------------------------------------
# Hedge & Epistemic Calibration Check
# ---------------------------------------------------------------------------

# Lexicon of epistemic hedges (indicates uncertainty, conditionality, or preliminary scope)
HEDGE_TERMS = {
    "may", "might", "could", "can", "suggest", "suggests", "suggested", "suggesting",
    "indicate", "indicates", "indicated", "indicating", "imply", "implies", "implied",
    "appear", "appears", "appeared", "appearing", "seem", "seems", "seemed", "seeming",
    "possible", "possibly", "potential", "potentially", "preliminary", "tentative",
    "likely", "unlikely", "probable", "probably", "plausible", "plausibly",
    "hypothesize", "hypothesized", "speculate", "speculated", "putative",
    "associated with", "correlated with", "correlation", "association",
    "in mice", "in animal models", "in vitro", "preclinical", "pre-clinical",
    "further research is needed", "further studies are needed", "not proven"
}

# Lexicon of definitive / booster terms (indicates absolute certainty or direct causality)
BOOSTER_TERMS = {
    "proves", "prove", "proven", "proves that", "proving",
    "causes", "cause", "caused", "causing", "causal",
    "conclusive", "conclusively", "definitive", "definitely", "definitively",
    "cures", "cure", "cured", "curing",
    "eradicates", "eradicate", "eradicated", "eradicating",
    "undeniable", "undeniably", "indisputable", "indisputably",
    "guarantees", "guarantee", "guaranteed", "always", "certainly", "certain",
    "unconditionally",
}

# Lexicon of scope-widening terms (indicates universal generalization beyond study cohort)
SCOPE_WIDENING_TERMS = {
    "all human", "all humans", "all patient", "all patients", "all populations",
    "universally", "universal", "all schools", "all cohorts", "across all",
    "every patient", "every case", "without exception", "cure for all", "cures all",
}


def _find_terms(text: str, term_set: set[str]) -> list[str]:
    """Find whole-word or phrase matches of the specified lexicon in text."""
    found: list[str] = []
    text_lower = " " + normalize_text(text).lower() + " "

    for term in sorted(term_set, key=len, reverse=True):
        pattern = r'(?<![A-Za-z0-9_-])' + re.escape(term) + r'(?![A-Za-z0-9_-])'
        if re.search(pattern, text_lower):
            found.append(term)

    return found


def hedge_check(claim: str, quote: str) -> CheckResult:
    """Check epistemic calibration and detect hedge-stripping (overclaiming).

    If the source quote contains epistemic hedges (e.g. 'suggests', 'may', 'potential')
    while the citing claim strips them into definitive causal assertions (e.g. 'proves', 'causes'),
    this check fails.
    """
    quote_hedges = _find_terms(quote, HEDGE_TERMS)
    claim_hedges = _find_terms(claim, HEDGE_TERMS)
    claim_boosters = _find_terms(claim, BOOSTER_TERMS)
    quote_boosters = _find_terms(quote, BOOSTER_TERMS)

    # Case 1: Source quote is hedged, but claim introduces definitive booster words
    if quote_hedges and claim_boosters:
        return CheckResult(
            passed=False,
            reason=(
                f"Hedge mismatch: claim asserts definitive claims ({claim_boosters}) "
                f"while source quote is hedged ({quote_hedges})"
            ),
            details={
                "type": "hedge_stripping_with_boosters",
                "quote_hedges": quote_hedges,
                "claim_boosters": claim_boosters,
            }
        )

    # Case 2: Source quote has tentative correlation / animal / preliminary hedges,
    # but claim strips all hedges and makes a direct unhedged causal statement
    tentative_quote_hedges = [
        h for h in quote_hedges
        if h in {"preliminary", "tentative", "hypothesized", "in mice", "in vitro", "preclinical", "speculated"}
    ]
    if tentative_quote_hedges and not claim_hedges and claim_boosters:
        return CheckResult(
            passed=False,
            reason=(
                f"Hedge mismatch: claim strips preliminary scope ({tentative_quote_hedges}) "
                f"into absolute certainty"
            ),
            details={
                "type": "preliminary_scope_stripped",
                "tentative_hedges": tentative_quote_hedges,
            }
        )

    # Case 3: Scope-widening (universalization beyond study cohort)
    claim_scope_wideners = _find_terms(claim, SCOPE_WIDENING_TERMS)
    quote_scope_wideners = _find_terms(quote, SCOPE_WIDENING_TERMS)
    unbacked_wideners = [w for w in claim_scope_wideners if w not in quote_scope_wideners]
    if unbacked_wideners:
        return CheckResult(
            passed=False,
            reason=(
                f"Scope mismatch: claim asserts unverified universal scope ({unbacked_wideners}) "
                f"without empirical support in quote"
            ),
            details={
                "type": "scope_widening",
                "unbacked_wideners": unbacked_wideners,
            }
        )

    return CheckResult(
        passed=True,
        reason="Epistemic calibration between claim and quote is consistent",
        details={
            "quote_hedges": quote_hedges,
            "claim_hedges": claim_hedges,
            "claim_boosters": claim_boosters,
            "quote_boosters": quote_boosters,
            "scope_wideners": claim_scope_wideners,
        }
    )


# ---------------------------------------------------------------------------
# Polarity & Negation Consistency Check
# ---------------------------------------------------------------------------

NEGATION_TERMS = {
    "failed to", "fails to", "failure to", "did not", "does not", "was not", "were not",
    "no reduction", "no increase", "no effect", "no difference", "no benefit",
    "ineffective", "without effect", "contrary to", "contrary to hypothesis",
    "worsened", "deteriorated", "unsuccessful", "did not improve", "failed to improve",
    "failed to demonstrate", "failed to demonstrate any", "failed to reach",
    "failed to achieve", "failed to exhibit", "failed to detect",
}

POSITIVE_EFFECT_TERMS = {
    "improved", "improves", "increased", "increase", "reduction in mortality",
    "reduced mortality", "beneficial", "benefit", "favorable", "effective",
    "efficacious", "promoted", "enhanced", "accelerated", "superior",
    "demonstrated", "achieved", "achieves", "reached", "reaches", "exhibited",
    "exhibits", "detected", "detects", "resulted in", "confirm", "confirmed",
    "confirms", "presence", "efficien", "efficiency", "yield", "yields",
    "outperform", "state-of-the-art", "fluctuat", "remained between",
    "observed", "superconductivity", "critical temperature",
}

NEGATIVE_EFFECT_TERMS = {
    "failed to improve", "did not improve", "worsened", "deteriorated",
    "increased mortality", "ineffective", "no effect", "no reduction",
    "no benefit", "no significant difference", "no significant effect", "adverse", "inferior",
    "indistinguishable from zero", "statistically indistinguishable from zero",
}


def polarity_check(claim: str, quote: str) -> CheckResult:
    """Check whether claim negates or inverts the empirical direction of the quote.

    Detects:
      - Claim asserts negation/failure when source reports positive benefit
      - Claim asserts positive benefit when source reports failure/adverse outcome
    """
    claim_lower = " " + normalize_text(claim).lower() + " "
    quote_lower = " " + normalize_text(quote).lower() + " "

    # Check for direct negation phrases in claim
    claim_negations = [term for term in sorted(NEGATION_TERMS, key=len, reverse=True) if f" {term} " in claim_lower or f" {term}" in claim_lower]
    quote_negations = [term for term in sorted(NEGATION_TERMS, key=len, reverse=True) if f" {term} " in quote_lower or f" {term}" in quote_lower]
    quote_has_positive = any(term in quote_lower for term in POSITIVE_EFFECT_TERMS)
    quote_has_negative = any(term in quote_lower for term in NEGATIVE_EFFECT_TERMS)

    # If both claim and quote share the null/negated finding (e.g. both observe "no significant effect"):
    if claim_negations and any(term in quote_lower for term in claim_negations):
        return CheckResult(
            passed=True,
            reason="Both claim and quote agree on null/negative empirical finding",
            details={"shared_negation": True}
        )

    # If quote has clear positive finding but claim asserts negation:
    if quote_has_positive and claim_negations and not quote_negations:
        return CheckResult(
            passed=False,
            reason=f"Polarity contradiction: claim asserts negation ({claim_negations}) contrary to positive findings in quote",
            details={
                "type": "negated_positive_finding",
                "claim_negations": claim_negations,
            }
        )

    # Check opposite directional verbs (e.g. claim asserts "increased" while quote says "reduced")
    claim_has_increase = any(w in claim_lower for w in ("increase", "increased", "increasing", "higher", "rose"))
    quote_has_increase = any(w in quote_lower for w in ("increase", "increased", "increasing", "higher", "rose"))
    claim_has_decrease = any(w in claim_lower for w in ("decrease", "decreased", "reduce", "reduced", "reduction", "lower", "drop", "dropped"))
    quote_has_decrease = any(w in quote_lower for w in ("decrease", "decreased", "reduce", "reduced", "reduction", "lower", "drop", "dropped"))

    if (claim_has_increase and quote_has_decrease and not quote_has_increase) or (claim_has_decrease and quote_has_increase and not quote_has_decrease):
        return CheckResult(
            passed=False,
            reason="Polarity contradiction: claim asserts opposite directional effect to quote (increase vs decrease/reduction)",
            details={"type": "opposite_direction"}
        )

    # If claim asserts positive effect but quote reports negative/failed effect:
    claim_has_positive = any(term in claim_lower for term in POSITIVE_EFFECT_TERMS)
    if claim_has_positive and quote_has_negative and not quote_has_positive:
        return CheckResult(
            passed=False,
            reason="Polarity contradiction: claim asserts positive effect while quote reports negative/ineffective outcome",
            details={
                "type": "inverted_direction",
            }
        )

    return CheckResult(
        passed=True,
        reason="Empirical polarity is consistent between claim and quote",
        details={}
    )


# ---------------------------------------------------------------------------
# Reference Integrity Checks (DOI Mismatch, Retraction, Secondary Source)
# ---------------------------------------------------------------------------

REVIEW_KEYWORDS_PATTERN = re.compile(
    r'\b(review|systematic review|meta-analysis|survey|literature review|scoping review|overview of|a review of)\b',
    re.IGNORECASE
)


def doi_mismatch_check(
    reference_title: str,
    candidate_title: str,
    doi: str = "",
    threshold: float = 0.45,
) -> CheckResult:
    """Deterministically check whether a cited DOI resolved to a mismatched paper title.

    Args:
        reference_title: The title specified in the manuscript bibliography/citation.
        candidate_title: The actual title returned by the resolver (Crossref/OpenAlex).
        doi: The identifier that was queried.
        threshold: Minimum similarity threshold below which a mismatch is declared.
    """
    if not reference_title or not candidate_title:
        return CheckResult(
            passed=True,
            reason="Insufficient title metadata to assess DOI mismatch",
            details={"reference_title": reference_title, "candidate_title": candidate_title}
        )

    norm_ref = normalize_text(reference_title).lower()
    norm_cand = normalize_text(candidate_title).lower()

    # Fast path: exact match after normalization
    if norm_ref == norm_cand:
        return CheckResult(
            passed=True,
            reason="DOI resolves to the exact cited paper title",
            details={"similarity": 1.0, "doi": doi}
        )

    # Token overlap similarity
    tokens_ref = set(re.findall(r'\b[a-zA-Z0-9]{3,}\b', norm_ref))
    tokens_cand = set(re.findall(r'\b[a-zA-Z0-9]{3,}\b', norm_cand))

    if not tokens_ref or not tokens_cand:
        sim = 0.0
    else:
        inter = len(tokens_ref & tokens_cand)
        union = len(tokens_ref | tokens_cand)
        overlap = inter / min(len(tokens_ref), len(tokens_cand))
        jaccard = inter / union if union else 0.0
        sim = 0.6 * overlap + 0.4 * jaccard

    if sim < threshold:
        return CheckResult(
            passed=False,
            reason=(
                f"DOI mismatch: DOI '{doi}' resolves to '{candidate_title}' "
                f"which does not match cited title '{reference_title}' (similarity {sim:.2f})"
            ),
            details={
                "mismatch_type": "doi_mismatch",
                "doi": doi,
                "reference_title": reference_title,
                "candidate_title": candidate_title,
                "similarity": round(sim, 4),
            }
        )

    return CheckResult(
        passed=True,
        reason="DOI resolves to a consistent paper title",
        details={"doi": doi, "similarity": round(sim, 4)}
    )


def retraction_check(candidate: Any) -> CheckResult:
    """Check whether a resolved paper has a formal retraction notice."""
    if candidate is None:
        return CheckResult(passed=True, reason="No candidate paper to check for retraction")

    is_retracted = getattr(candidate, "is_retracted", False)
    retraction_details = getattr(candidate, "retraction_details", {}) or {}

    if is_retracted:
        source_name = getattr(candidate, "source", "academic database")
        return CheckResult(
            passed=False,
            reason=f"Paper retraction: cited work has been retracted (reported by {source_name})",
            details={"is_retracted": True, "retraction_details": retraction_details}
        )

    return CheckResult(
        passed=True,
        reason="No retraction notice found for cited paper",
        details={"is_retracted": False}
    )


def correction_check(candidate: Any) -> CheckResult:
    """Check whether a resolved paper has an issued erratum or correction."""
    if candidate is None:
        return CheckResult(passed=True, reason="No candidate paper to check for correction")

    is_corrected = getattr(candidate, "is_corrected", False)
    correction_details = getattr(candidate, "correction_details", {}) or {}

    if is_corrected:
        source_name = getattr(candidate, "source", "academic database")
        return CheckResult(
            passed=False,
            reason=f"Paper correction: cited work has an issued erratum/correction (reported by {source_name})",
            details={"is_corrected": True, "correction_details": correction_details}
        )

    return CheckResult(
        passed=True,
        reason="No correction notice found for cited paper",
        details={"is_corrected": False}
    )


def secondary_source_check(
    candidate: Any = None,
    title: str = "",
    abstract: str = "",
) -> CheckResult:
    """Check whether a cited work is a secondary source (review/survey/meta-analysis).

    If true, the verification engine should flag it and follow one citation hop to the primary source.
    """
    pub_type = getattr(candidate, "publication_type", "") if candidate else ""
    check_title = (getattr(candidate, "title", "") or title or "").strip()
    check_abstract = (getattr(candidate, "abstract", "") or abstract or "").strip()

    is_review = False
    indicators: list[str] = []

    if pub_type in ("review", "survey", "review-article"):
        is_review = True
        indicators.append(f"publication_type={pub_type}")

    if REVIEW_KEYWORDS_PATTERN.search(check_title):
        is_review = True
        indicators.append(f"title_keyword={REVIEW_KEYWORDS_PATTERN.search(check_title).group(0)}")

    if check_abstract and REVIEW_KEYWORDS_PATTERN.search(check_abstract[:200]):
        is_review = True
        indicators.append("abstract_keyword")

    if is_review:
        return CheckResult(
            passed=False,
            reason=(
                f"Secondary source detected: cited work is a review/survey ({', '.join(indicators)}). "
                "One citation hop required to verify original primary empirical source."
            ),
            details={
                "is_secondary_source": True,
                "publication_type": pub_type,
                "indicators": indicators,
                "hops_required": 1,
            }
        )

    return CheckResult(
        passed=True,
        reason="Primary empirical source: paper is not a secondary review or survey",
        details={"is_secondary_source": False}
    )

