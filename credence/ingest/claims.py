"""Scientific claim extraction and slot atomization via LLM with strict JSON validation.

Rules (AGENTS.md):
- Every LLM call validates against a JSON schema; bad JSON -> 1 retry -> "Needs review", never crash.
- LLM judges MEANING only. Python decides every deterministic fact.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from credence.report.models import Claim, Slot


# Schema definition for validation
CLAIM_EXTRACTION_PROMPT = """You are an academic claim extraction agent.
Read the following manuscript text and extract all empirical, scientific, or factual claims
that are supported by citations (e.g., [1], [4], (Author, Year)).

For each claim:
1. Extract the verbatim claim text.
2. List the associated citation keys (e.g. ["4"] or ["Smith2020"]).
3. Specify the source location (section name and page).
4. Atomize the claim into verifiable slots:
   - "quote": the verbatim proposition expected in the cited source
   - "number": exact numbers or rates asserted (if any)
   - "finding": direction of effect or outcome (e.g. "reduced mortality")

Output MUST be strict JSON in the following format:
[
  {
    "id": "claim-1",
    "text": "Compound-X reduced 30-day mortality by 12.1% [4].",
    "citation_keys": ["4"],
    "source_location": "Results, page 3",
    "slots": [
      {
        "id": "claim-1-slot-1",
        "field_type": "number",
        "expected_value": "12.1%",
        "description": "Reduction in 30-day mortality"
      },
      {
        "id": "claim-1-slot-2",
        "field_type": "quote",
        "expected_value": "demonstrated a 12.1% reduction in 30-day mortality",
        "description": "Verbatim evidence quote"
      }
    ]
  }
]
No other text or markdown, output ONLY the JSON array.
"""


def validate_claims_json(data: Any) -> tuple[bool, Optional[str]]:
    """Validate parsed JSON against expected claim structure."""
    if not isinstance(data, list):
        return False, "Expected JSON array of claims at top level."

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            return False, f"Claim at index {idx} is not a dictionary."
        if "id" not in item or "text" not in item:
            return False, f"Claim at index {idx} missing 'id' or 'text'."
        if "citation_keys" not in item or not isinstance(item["citation_keys"], list):
            return False, f"Claim at index {idx} missing 'citation_keys' list."

        slots = item.get("slots", [])
        if not isinstance(slots, list):
            return False, f"Claim at index {idx} 'slots' must be a list."
        for s_idx, s in enumerate(slots):
            if not isinstance(s, dict) or "id" not in s or "field_type" not in s:
                return False, f"Slot {s_idx} in claim {idx} missing 'id' or 'field_type'."

    return True, None


def deterministic_extract_claims(
    body_text: str,
    section_name: str = "Results",
    include_uncited: bool = True,
) -> list[Claim]:
    """Pure-Python fallback claim extractor: identifies cited and uncited empirical sentences and atomizes slots.

    Used when LLM is unavailable or for offline testing, adhering to the 1-retry fallback rule.
    Identifies empirical claims that lack citations without inventing citations (Requirement 1 & 7).
    """
    claims: list[Claim] = []
    # Normalize whitespace and line breaks within paragraphs
    clean_body = re.sub(r'\s+', ' ', body_text).strip()
    sentences = re.split(r'(?<=[.!?])\s+', clean_body)
    claim_idx = 1

    for sentence in sentences:
        s_clean = sentence.strip()
        # Find citation markers [n] or [n-m]
        citations = re.findall(r'\[(\d+(?:\s*[-–,]\s*\d+)*)\]', s_clean)
        # Author-year citation markers e.g. (Smith et al., 2020)
        author_year_cites = re.findall(r'\(([A-Z][a-zA-Z]+(?:\s+et\s+al\.?)?,\s*(?:19|20)\d{2}[a-z]?)\)', s_clean)

        # Check for empirical or factual assertion words
        has_empirical_cue = bool(re.search(
            r'\b(showed|demonstrated|reduced|reduction|decreased|decrease|increasing|increased|increase|improved|improving|improvement|attenuated|attenuation|observed|found|associated|efficacy|mortality|survival|incidence|toxicity|rate|significant|significantly)\b|%',
            s_clean,
            re.IGNORECASE
        ))

        # Check for numerical or statistical data
        has_numbers = bool(re.search(r'\b\d+(?:\.\d+)?%?', s_clean))

        if not citations and not author_year_cites:
            # Handle empirical claims without citations (Requirement 1 & 7)
            if include_uncited and has_empirical_cue and (has_numbers or len(s_clean.split()) >= 7):
                claim_id = f"claim-{claim_idx}"
                slots: list[Slot] = []
                slot_idx = 1

                # Extract number slots if present
                numbers = re.findall(r'\b\d+(?:\.\d+)?%?', s_clean)
                for num in numbers:
                    slots.append(Slot(
                        id=f"{claim_id}-slot-{slot_idx}",
                        claim_id=claim_id,
                        citation_key="",
                        field_type="number" if "%" in num or "." in num else "quantity",
                        expected_value=num,
                        description=f"Numerical assertion: {num}",
                    ))
                    slot_idx += 1

                slots.append(Slot(
                    id=f"{claim_id}-slot-{slot_idx}",
                    claim_id=claim_id,
                    citation_key="",
                    field_type="quote",
                    expected_value=s_clean,
                    description="Uncited empirical claim requiring citation proof",
                ))

                uncited_reason = "Empirical claim asserted without any supporting in-text citation marker."
                uncited_action = "Provide a peer-reviewed citation supporting this assertion or qualify as an author hypothesis."

                claims.append(Claim(
                    id=claim_id,
                    text=s_clean,
                    citation_keys=[],  # Requirement 7: Never automatically invent or assign citations
                    source_location=section_name,
                    slots=slots,
                    citation_classification="MISSING CITATION",
                    has_missing_citation=True,
                    missing_citation_reason=uncited_reason,
                    recommended_action=uncited_action,
                    citation_audit={
                        "classification": "MISSING CITATION",
                        "reason": uncited_reason,
                        "recommended_action": uncited_action,
                        "missing_citation": True,
                    },
                ))
                claim_idx += 1
            continue

        if has_empirical_cue:
            # Flatten citation keys
            all_keys = []
            for c in citations:
                for part in re.split(r'[,;]', c):
                    part = part.strip()
                    if part.isdigit():
                        all_keys.append(part)

            for ay in author_year_cites:
                m = re.match(r'([A-Z][a-zA-Z]+).*?,\s*((?:19|20)\d{2})', ay)
                if m:
                    all_keys.append(f"{m.group(1)}{m.group(2)}")
                else:
                    all_keys.append(ay)

            claim_id = f"claim-{claim_idx}"
            slots: list[Slot] = []
            slot_idx = 1

            # Extract number slots if present
            numbers = re.findall(r'\b\d+(?:\.\d+)?%?', s_clean)
            for num in numbers:
                slots.append(Slot(
                    id=f"{claim_id}-slot-{slot_idx}",
                    claim_id=claim_id,
                    citation_key=all_keys[0] if all_keys else "",
                    field_type="number" if "%" in num or "." in num else "quantity",
                    expected_value=num,
                    description=f"Numerical assertion: {num}",
                ))
                slot_idx += 1

            # Proposition quote slot
            slots.append(Slot(
                id=f"{claim_id}-slot-{slot_idx}",
                claim_id=claim_id,
                citation_key=all_keys[0] if all_keys else "",
                field_type="quote",
                expected_value=s_clean,
                description="Verbatim supporting quote from source",
            ))

            claims.append(Claim(
                id=claim_id,
                text=s_clean,
                citation_keys=all_keys,
                source_location=section_name,
                slots=slots,
            ))
            claim_idx += 1

    return claims


def identify_uncited_claims(body_text: str, section_name: str = "Results") -> list[Claim]:
    """Identify empirical claims in manuscript text that lack citations (Requirement 1 & 7)."""
    all_claims = deterministic_extract_claims(body_text, section_name=section_name, include_uncited=True)
    return [c for c in all_claims if not c.citation_keys or len(c.citation_keys) == 0]


def extract_claims(
    body_text: str,
    section_name: str = "Results",
    llm_client: Optional[Any] = None,
    include_uncited: bool = True,
) -> list[Claim]:
    """Extract claims and atomize slots using LLM with strict JSON validation and 1-retry fallback."""
    if not llm_client:
        return deterministic_extract_claims(body_text, section_name=section_name, include_uncited=include_uncited)

    prompt = f"{CLAIM_EXTRACTION_PROMPT}\nManuscript excerpt:\n{body_text[:4000]}\n"

    # 1. First LLM attempt
    try:
        raw_response = llm_client.generate(prompt)
        # Strip potential markdown fences
        cleaned = re.sub(r'^```(?:json)?\s*', '', raw_response.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned).strip()
        data = json.loads(cleaned)
        is_valid, err = validate_claims_json(data)
        if is_valid:
            return _dict_to_claims(data)
    except Exception as exc:
        err = str(exc)

    # 2. One retry rule (AGENTS.md: bad JSON -> 1 retry -> fallback, never crash)
    try:
        retry_prompt = f"Your previous response had error: {err}. Output ONLY valid JSON array according to schema.\n{prompt}"
        raw_response = llm_client.generate(retry_prompt)
        cleaned = re.sub(r'^```(?:json)?\s*', '', raw_response.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned).strip()
        data = json.loads(cleaned)
        is_valid, _ = validate_claims_json(data)
        if is_valid:
            return _dict_to_claims(data)
    except Exception:
        pass

    # 3. Graceful fallback to deterministic extraction
    return deterministic_extract_claims(body_text, section_name=section_name)


def _dict_to_claims(data: list[dict[str, Any]]) -> list[Claim]:
    """Convert validated dictionary data into Claim and Slot dataclasses."""
    claims: list[Claim] = []
    for c in data:
        slots = [
            Slot(
                id=s["id"],
                claim_id=c["id"],
                citation_key=s.get("citation_key", c["citation_keys"][0] if c.get("citation_keys") else ""),
                field_type=s.get("field_type", "quote"),
                expected_value=s.get("expected_value"),
                description=s.get("description", ""),
            )
            for s in c.get("slots", [])
        ]
        claims.append(Claim(
            id=c["id"],
            text=c["text"],
            citation_keys=c.get("citation_keys", []),
            source_location=c.get("source_location", ""),
            slots=slots,
        ))
    return claims
