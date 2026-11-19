"""Slot extraction prompt, JSON schema, and atomization engine.

Extracts verifiable propositions (finding, number, population, design, quote) from claims.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from credence.report.models import Slot

SLOT_EXTRACTION_PROMPT = """You are an academic claim atomization agent.
Deconstruct the following empirical scientific claim into independent verifiable slots:
1. "finding": the direction or qualitative assertion (e.g. "improved test scores")
2. "number": any specific numerical percentages, rates, or counts (e.g. "30%", "12.1%")
3. "population": the sample or cohort description (e.g. "students", "40 students")
4. "design": study design or control assertions (e.g. "randomized controlled trial", "no control group")
5. "quote": expected supporting sentence

Output MUST be strict JSON in the following format:
{
  "claim_id": "claim-1",
  "slots": [
    {
      "id": "claim-1-slot-1",
      "field_type": "finding",
      "expected_value": "improved test scores",
      "description": "Qualitative direction of effect"
    },
    {
      "id": "claim-1-slot-2",
      "field_type": "number",
      "expected_value": "30%",
      "description": "Reported score improvement rate"
    }
  ]
}
Output ONLY valid JSON.
"""

SLOT_SCHEMA = {
    "type": "object",
    "required": ["claim_id", "slots"],
    "properties": {
        "claim_id": {"type": "string"},
        "slots": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "field_type", "expected_value"],
                "properties": {
                    "id": {"type": "string"},
                    "field_type": {"type": "string", "enum": ["finding", "number", "population", "design", "quote", "quantity"]},
                    "expected_value": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
    },
}


def deterministic_atomize_claim(
    claim_text: str,
    claim_id: str = "claim-1",
    citation_key: str = "",
) -> list[Slot]:
    """Pure-Python deterministic slot atomization."""
    slots: list[Slot] = []
    slot_idx = 1

    # Strip citation brackets before extracting empirical numbers
    text_without_citations = re.sub(r'\[\s*\d+(?:\s*[-–,]\s*\d+)*\s*\]', '', claim_text).strip()

    # 1. Number / percentage slots
    numbers = re.findall(r'(\d+(?:\.\d+)?\s*(?:%|percent|percentage\s*points?)?)', text_without_citations, re.IGNORECASE)
    for num in numbers:
        num_clean = num.strip()
        if not num_clean:
            continue
        slots.append(Slot(
            id=f"{claim_id}-slot-{slot_idx}",
            claim_id=claim_id,
            citation_key=citation_key,
            field_type="number" if "%" in num_clean or "." in num_clean else "quantity",
            expected_value=num_clean,
            description=f"Numerical assertion: {num_clean}",
        ))
        slot_idx += 1

    # 2. Finding / outcome slot
    finding_match = re.search(
        r'\b(improved|increased|decreased|reduced|eradicated|cured|prevented|demonstrated|showed|associated\s+with)\s+([a-zA-Z\s]+?)(?=\s+by|\s+in|\s+with|\s+\[|\s*\.|$)',
        claim_text,
        re.IGNORECASE
    )
    if finding_match:
        direction = finding_match.group(1).lower()
        target = finding_match.group(2).strip()
        expected_finding = f"{direction} {target}"
        slots.append(Slot(
            id=f"{claim_id}-slot-{slot_idx}",
            claim_id=claim_id,
            citation_key=citation_key,
            field_type="finding",
            expected_value=expected_finding,
            description="Asserted outcome or direction of effect",
        ))
        slot_idx += 1
    else:
        # Fallback qualitative finding slot
        clean_prop = re.sub(r'\[.*?\]', '', claim_text).strip()
        slots.append(Slot(
            id=f"{claim_id}-slot-{slot_idx}",
            claim_id=claim_id,
            citation_key=citation_key,
            field_type="finding",
            expected_value=clean_prop,
            description="Asserted claim proposition",
        ))
        slot_idx += 1

    # 3. Verbatim quote slot
    clean_quote = re.sub(r'\[.*?\]', '', claim_text).strip()
    slots.append(Slot(
        id=f"{claim_id}-slot-{slot_idx}",
        claim_id=claim_id,
        citation_key=citation_key,
        field_type="quote",
        expected_value=clean_quote,
        description="Verbatim evidence quote expected in source",
    ))

    return slots


def extract_slots(
    claim_text: str,
    claim_id: str = "claim-1",
    citation_key: str = "",
    llm_client: Optional[Any] = None,
) -> list[Slot]:
    """Extract and atomize slots from claim using LLM with strict validation and fallback."""
    if not llm_client:
        return deterministic_atomize_claim(claim_text, claim_id=claim_id, citation_key=citation_key)

    prompt = f"{SLOT_EXTRACTION_PROMPT}\nClaim: \"{claim_text}\"\n"
    try:
        resp = llm_client.generate(prompt)
        cleaned = re.sub(r'^```(?:json)?\s*', '', resp.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned).strip()
        data = json.loads(cleaned)

        if "slots" in data and isinstance(data["slots"], list):
            slots = []
            for s in data["slots"]:
                slots.append(Slot(
                    id=s.get("id", f"{claim_id}-slot-{len(slots)+1}"),
                    claim_id=claim_id,
                    citation_key=citation_key,
                    field_type=s.get("field_type", "finding"),
                    expected_value=s.get("expected_value", ""),
                    description=s.get("description", ""),
                ))
            if slots:
                return slots
    except Exception:
        pass

    return deterministic_atomize_claim(claim_text, claim_id=claim_id, citation_key=citation_key)
