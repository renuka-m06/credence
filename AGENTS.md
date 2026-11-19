## Job
Credence verifies scientific claims against their citations. Upload a PDF/DOCX →
extract claims + citations → retrieve the cited paper → check whether the source
backs each claim → output an evidence-backed, human-reviewable report.
Core principle: EVERY VERDICT CARRIES PROOF. The LLM must return a verbatim quote
that OUR CODE confirms exists in the source. Never present a result as a final
academic judgment — it's a triage aid, open to human review.

## Stack (do not swap without asking)
Backend: Python 3.11, FastAPI, the verification engine as a UI-agnostic package.
Frontend: React (Vite) + plain CSS (tokens below).
LLM: Gemini free tier via google-genai (fallback: Ollama local). All LLM output = strict JSON.
Retrieval: Crossref, OpenAlex (API key), Semantic Scholar, Unpaywall, arXiv, PMC.
Parsing: PyMuPDF, python-docx. Search: rank_bm25, sentence-transformers. Fuzzy: rapidfuzz.
Cache + ledger: SQLite. Tests: pytest.

## Golden rules — these ARE the project
1. LLM judges MEANING only. Python decides every deterministic fact: quote existence,
   number/unit equality, hedge words. The LLM can NEVER override a code check.
2. If a returned quote is not found in the source after normalization → discard that
   slot → "Needs review". Log it so the benchmark counts caught hallucinations.
3. Confidence is COMPUTED (access-tier cap − unverified slots − pass disagreement),
   never the model's self-reported number.
4. "Not found in databases" ≠ fabricated. Report what was searched and where.
5. Verdict is derived from the fixed rule table in verify/verdict.py, never one LLM label.
6. Default stance = human review. No silent auto-decisions.

## Validation gates (pass before marking any task done)
- verify/checks.py has unit tests; pytest tests/test_checks.py green.
- No HTTP call bypasses resolve/cache.py (cache-first) with timeout + retry/backoff.
- Every LLM call validates against a JSON schema; bad JSON → 1 retry → "Needs review", never crash.
- python -m credence.benchmark.score prints per-verdict precision/recall on gold_set.jsonl.
- Frontend runs end-to-end against the API on sample data with NO live API calls.

## UI contract (match exactly)
Fonts: Inter (body/UI), Spectral (serif headings). Dark theme, orange planet-glow in corners.
Tokens:
  --bg #0b0b0e | --panel #16161c | --panel2 #1c1c23 | --line rgba(255,255,255,.08)
  --ink #edeef1 | --muted #9a9ca4 | --faint #6a6c75
  --orange #f06a2c | --orange2 #ff7d3c
Verdict colors (text / 14%-alpha bg):
  supported #5fcf6a | partial #e3a93a | unsupported #ef6b6b | contradictory #e0574f | needs-review #5aa9f0
Screens: Home (hero w/ seal badge + serif headline + wave + 3 feature cards + trust strip),
Report (summary strip + claim list, default filter "Needs review" + detail panel:
claim → verdict+confidence → slot table → verified quote w/ shield → source link → Accept/Override/Comment),
Benchmark (per-verdict precision/recall table + calibration chart).

## Build order (do not reorder; later layers depend on earlier contracts)
models → checks(+tests) → verdict → parse → citations → reference+matcher+cache →
sources → slots+retrieve → llm → adversarial → report wiring → FastAPI → React → benchmark.