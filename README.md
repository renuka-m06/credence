# Credence

> **Scientific claim verification against citations with deterministic proof.**

Credence extracts claims and citations from manuscripts (PDF/DOCX), retrieves cited literature across academic databases, and deterministically verifies whether the source evidence backs each asserted claim.

---

## Core Principle: Every Verdict Carries Proof

The engine enforces strict epistemic separation between language models and deterministic verification:

- **LLMs judge meaning only.** Python decides every deterministic fact: verbatim quote existence, number/unit equality, and hedge words. An LLM can never override code verification.
- **Strict Hallucination Discarding:** If a candidate quote returned by an LLM is not found verbatim in the source paper after normalization, that slot is discarded and triaged as **"Needs review"**.
- **Computed Confidence:** Confidence is derived mathematically from paper access tier ceilings minus deterministic penalties for unverified slots and pass disagreement. It is **never** the model's self-reported number.
- **Transparent Search Accounting:** "Not found in databases" is never reported as fabricated. Credence explicitly reports what was searched and where.
- **Fixed Deterministic Verdict Table:** Verdicts are derived strictly from the fixed rule table in `credence/verify/verdict.py`, never from a single LLM label.
- **Default Stance:** Open to human review with no silent auto-decisions.

---

## Reliability Core (`credence/verify`)

### 1. Verification Checks (`checks.py`)
- `quote_check(quote, source_text)`: Deterministic verbatim quote check with Unicode NFKC normalization, quote standardisation, line-break dehyphenation, and whitespace collapse. Catches and rejects LLM quote hallucinations.
- `number_check(claim_text, quote_text)`: Numerical precision and unit consistency checker. Catches value mismatches (e.g. `30%` vs `12.1%`) and unit distinctions (e.g. `percent` vs `percentage points`).
- `hedge_check(claim, quote)`: Epistemic calibration checker. Detects hedge stripping and overclaiming (e.g. claiming "proves that X causes Y" when the source quote states "may suggest a potential correlation").

### 2. Verdict Rule Table (`verdict.py`)
Maps factual slot states (`match`, `mismatch`, `absent`, `outdated`, `hallucinated`) to triage verdicts:

| Condition | Verdict |
| :--- | :--- |
| Candidate quote not found in source text | `needs review` |
| Cited paper is inaccessible or not found | `needs review` |
| No factual slots extracted | `needs review` |
| Citation retracted, superseded, or outdated | `potentially outdated` |
| Any slot mismatch / numerical conflict | `contradictory` |
| All slots match with zero absent/mismatch | `supported` |
| At least one match and at least one absent | `partially supported` |
| All slots absent from retrieved paper | `unsupported` |

### 3. Computed Confidence Formula
$$\text{Confidence} = \max\left(0.0, \min\left(\text{Cap}, \text{Cap} - (\text{unverified\_slots} \times 0.15) - (\text{pass\_disagreement} \times 0.20)\right)\right)$$

**Access Tier Ceilings:**
- **Full Text**: `0.9`
- **Abstract Only**: `0.6`
- **Metadata Only**: `0.2`
- **Inaccessible / Not Found**: `0.0`

---

## Repository Structure

```
credence/
├── .env.example              # Environment credentials template
├── config.py                 # Central settings & access-tier confidence caps
├── requirements.txt          # Python dependencies
├── AGENTS.md                 # Project rules, contracts, and validation gates
├── README.md
├── credence/
│   ├── __init__.py
│   ├── ingest/               # Document parsing (PDF/DOCX) & claim extraction
│   ├── resolve/              # Paper retrieval (Crossref, OpenAlex, arXiv, etc.) & cache
│   ├── verify/               # Deterministic checks & verdict rule table
│   │   ├── checks.py         # quote_check, number_check, hedge_check
│   │   └── verdict.py        # Fixed rule table & compute_confidence
│   ├── report/               # Dataclasses (Claim, Slot, SlotResult, Verdict, Report)
│   │   └── models.py
│   └── benchmark/            # Precision/recall evaluation on gold_set.jsonl
├── data/
│   └── demo/                 # Sample documents & benchmark evaluation corpora
└── tests/
    ├── test_checks.py        # Unit tests for quote, number, and hedge checks
    ├── test_models.py        # Serialization & access tier tests
    └── test_verdict.py       # Rule table and confidence computation tests
```

---

## Quickstart

### 1. Requirements & Setup
- Python 3.11+
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```
- Copy and configure the environment variables:
  ```bash
  cp .env.example .env
  ```

### 2. Running Tests
Run all unit tests using pytest:
```bash
pytest -v
```

---

## Build Order

Following the contract in `AGENTS.md`:
1. `models` $\rightarrow$ `checks(+tests)` *(Completed)*
2. `verdict` *(Completed)*
3. `parse` $\rightarrow$ `citations` $\rightarrow$ `reference+matcher+cache`
4. `sources` $\rightarrow$ `slots+retrieve` $\rightarrow$ `llm` $\rightarrow$ `adversarial`
5. `report wiring` $\rightarrow$ `FastAPI` $\rightarrow$ `React` $\rightarrow$ `benchmark`
