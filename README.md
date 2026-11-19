# Credence — Deterministic Scientific Claim Verification Engine

> **Every Verdict Carries Proof.** Credence extracts empirical claims and citations from manuscripts (PDF/DOCX), resolves cited literature across academic databases (Crossref, OpenAlex, Semantic Scholar, arXiv, PMC, Unpaywall), and deterministically verifies whether source evidence backs each asserted claim.

[![Tests](https://img.shields.io/badge/pytest-154%20passed-5fcf6a.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)]()
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-5aa9f0.svg)]()
[![Frontend](https://img.shields.io/badge/frontend-React%20%7C%20Vite-f06a2c.svg)]()
[![Docker](https://img.shields.io/badge/docker-ready-2496ed.svg)]()

---

## Table of Contents
- [Core Architecture & Epistemic Principles](#core-architecture--epistemic-principles)
- [System Architecture](#system-architecture)
- [Golden Rules](#golden-rules)
- [Security Hardening & Production Features](#security-hardening--production-features)
- [Quick Start](#quick-start)
- [Environment Configuration](#environment-configuration)
- [Docker & Containerized Deployment](#docker--containerized-deployment)
- [API Reference](#api-reference)
- [Human-in-the-Loop Review Ledger](#human-in-the-loop-review-ledger)
- [Benchmarking & Empirical Validation](#benchmarking--empirical-validation)
- [Automated Testing Suite](#automated-testing-suite)
- [License](#license)

---

## Core Architecture & Epistemic Principles

Credence addresses the critical problem of scientific citation distortion, paper mills, retracted citations, and hallucinations by strictly separating probabilistic inference from deterministic code verification:

1. **LLMs judge meaning only.** Python decides every deterministic fact: verbatim quote existence, numerical precision, unit equivalence, and epistemic hedge calibration. The LLM can never override code checks.
2. **Deterministic Hallucination Discarding:** If a retrieved quote candidate does not exist verbatim in the normalized source publication, that evidence slot is discarded and routed to `"Needs review"`.
3. **Computed Confidence:** Confidence is computed via a mathematical formula bound to the source access-tier cap minus deterministic penalties for unverified slots and pass disagreement. It is never a self-reported model score.
4. **Transparent Retrieval Ledger:** "Not found in databases" is never reported as fabricated. Credence explicitly logs what queries were run and which databases were queried.
5. **Fixed Verdict Table:** Final triage classifications (`supported`, `partially supported`, `unsupported`, `contradictory`, `needs review`, `potentially outdated`) are determined by a fixed deterministic rule table.
6. **Default Stance: Academic Triage:** Results are presented as human-reviewable evidence aids with an append-only audit ledger, never as unilateral final academic judgments.

---

## System Architecture

```
                                  [ Upload Manuscript (PDF / DOCX) ]
                                                  │
                                                  ▼
                                       PyMuPDF / python-docx
                               (Sections, Paragraphs & Page Tracking)
                                                  │
                      ┌───────────────────────────┴───────────────────────────┐
                      ▼                                                       ▼
            In-Text Citation Parsing                                Empirical Claim Extraction
           (Regex + Disambiguation)                                   (Sentence Tokenization)
                      │                                                       │
                      ▼                                                       ▼
           Citation Bibliography Map                              Atomized Factual Slots
                      │                                                       │
                      └───────────────────────────┬───────────────────────────┘
                                                  │
                                                  ▼
                                      Unified Scholarly Resolver
                              (Crossref, OpenAlex, Semantic Scholar,
                                  arXiv, PMC, Unpaywall + Cache)
                                                  │
                                                  ▼
                                      Deterministic Verification
                                   ┌─────────────────────────────┐
                                   │ 1. Verbatim Quote Check     │
                                   │ 2. Number & Unit Equality   │
                                   │ 3. Epistemic Hedge Check    │
                                   │ 4. Retraction & Outdated    │
                                   └─────────────────────────────┘
                                                  │
                                                  ▼
                                      Computed Confidence &
                                   Deterministic Verdict Machine
                                                  │
                                                  ▼
                                    Durable Report Storage Engine
                                    (SQLite / PostgreSQL + WAL)
                                                  │
                                                  ▼
                             Interactive React Workbench & Review Ledger
```

---

## Golden Rules

| Rule | Enforcement Mechanism |
| :--- | :--- |
| **1. Separation of Powers** | Python handles string matching, number comparisons, hedge words; LLM handles semantic paraphrase slots. |
| **2. Zero Hallucinations** | Candidate quotes failing `quote_check()` are dropped; benchmark tracks caught hallucinations. |
| **3. Computed Confidence** | Tier cap (`FULL_TEXT`: 0.9, `ABSTRACT`: 0.6, `METADATA`: 0.2, `INACCESSIBLE`: 0.0) − unverified slots − pass disagreement. |
| **4. Database Transparency** | Logs every query to Crossref, OpenAlex, arXiv, and Semantic Scholar with response codes. |
| **5. Fixed State Machine** | Verdict computed from `verify/verdict.py` rule matrix, never an LLM prompt. |
| **6. Human Review Default** | Discrepancies and unverified claims default to `needs review` with manual override support. |

---

## Security Hardening & Production Features

Credence is hardened for secure enterprise and institutional deployment:

- **Durable Persistent Storage (`credence/report/storage.py`):**
  - Uploaded reports and claim evaluations survive server restarts.
  - Backed by SQLite (default with WAL mode and transaction isolation) or PostgreSQL via `DATABASE_URL`.
  - Automatic migration and schema provisioning on startup.
- **Strict File Upload Validation (`credence/security/upload.py`):**
  - 25 MB strict size ceiling enforced during streaming.
  - Magic-byte signature verification (`%PDF` for PDFs, `PK\x03\x04` archive container for DOCX).
  - Path traversal defense: sanitizes filenames against directory attacks (`../../etc/passwd`).
- **Authentication & RBAC (`credence/auth/`):**
  - Signed HMAC-SHA256 JWT access tokens.
  - Passwords hashed with bcrypt and PBKDF2 fallback.
  - Role-based access control (`admin`, `reviewer`, `viewer`).
  - Server-side reviewer identity verification on override and comment submissions.
- **Security & Network Hardening:**
  - Configurable CORS origin whitelist via `ALLOWED_ORIGINS` (disallowing wildcard credentials).
  - Sliding-window rate limiter protecting heavy verification endpoints (`POST /verify`).
  - Centralized exception handlers preventing database query leaks and internal stack trace exposure.
  - Standardized `/health` check endpoint for Kubernetes, Docker, and Cloud Run orchestrators.

---

## Quick Start

### 1. Prerequisites
- Python 3.11 or 3.12
- Node.js 18+ (for frontend development)

### 2. Installation
Clone the repository and install backend dependencies:
```bash
git clone https://github.com/rushildk/credence.git
cd credence

# Install Python requirements
pip install -r requirements.txt

# Install frontend dependencies
npm --prefix frontend install
```

### 3. Environment Setup
Copy the example environment configuration:
```bash
cp .env.example .env
```

### 4. Running Locally
Start the FastAPI backend server:
```bash
python -m uvicorn credence.server:app --host 0.0.0.0 --port 8000 --reload
```

In a separate terminal, start the React Vite dev server:
```bash
npm --prefix frontend run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Environment Configuration

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `CREDENCE_ENV` | `production` | Environment mode (`production` or `development`). |
| `HOST` | `0.0.0.0` | Server host binding. |
| `PORT` | `8000` | Server HTTP port (auto-bound on cloud services). |
| `DATABASE_URL` | `sqlite:///./data/credence.db` | Persistent storage connection (supports Postgres). |
| `ALLOWED_ORIGINS` | `http://localhost:5173,...` | Comma-separated CORS allowed origins. |
| `CREDENCE_SECRET_KEY` | *(auto-generated)* | JWT signing secret key. |
| `CREDENCE_AUTH_REQUIRED` | `false` | When `true`, requires Bearer token for all reviews. |
| `MAX_UPLOAD_SIZE_BYTES` | `26214400` | Maximum file upload size (25 MB). |
| `RATE_LIMIT_PER_MINUTE` | `60` | Max verification requests per IP per minute. |
| `GEMINI_API_KEY` | `""` | Optional Google Gemini API key for semantic parsing. |
| `OPENALEX_API_KEY` | `""` | Optional OpenAlex API key for high-throughput paper queries. |
| `SEMANTIC_SCHOLAR_API_KEY`| `""` | Optional Semantic Scholar API key. |
| `CROSSREF_MAILTO` | `researcher@example.com` | Polite Crossref pool email. |

---

## Docker & Containerized Deployment

Credence includes an enterprise-grade multi-stage `Dockerfile` that builds the React client and packages it with the FastAPI backend into a single lean container running as a non-root user.

### Run with Docker Compose
```bash
# Build and run with default persistent SQLite
docker compose up -d --build

# Run with PostgreSQL profile
docker compose --profile with-postgres up -d --build
```
The application will be live at [http://localhost:8000](http://localhost:8000).

### Deploying to Cloud Run / Render / AWS ECS
The container binds dynamically to `0.0.0.0:$PORT` and provides a health check at `/health`:
```bash
docker build -t credence:latest .
docker run -p 8000:8000 -e PORT=8000 credence:latest
```

---

## API Reference

### Core Endpoints

- `POST /verify`
  Upload a `.pdf` or `.docx` manuscript. Executes parsing, citation mapping, scholarly database resolution, deterministic checks, and persists report.
- `GET /report/{id}`
  Retrieve a verified report with effective review overrides applied. Survives server restarts.
- `POST /report/{id}/review` or `POST /claims/{claim_id}/review`
  Record human reviewer actions (`accept`, `override`, `comment`) in the append-only SQLite review ledger.
- `GET /claims/{claim_id}/source`
  Inspect source publication title, DOI, page number, section, paragraph, and highlighted verbatim evidence.
- `GET /claims/{claim_id}/reviews`
  Retrieve complete chronological review history for auditability.
- `GET /report/{id}/export?format={html|markdown|json}`
  Download report export reflecting effective overridden verdicts while preserving original automated findings.
- `GET /benchmark`
  Retrieve precision, recall, F1, and ECE across synthetic and real-world datasets.
- `GET /health`
  Health check returning service status and persistent storage confirmation.

### Authentication Endpoints

- `POST /auth/register` — Register a new reviewer account.
- `POST /auth/login` — Authenticate and receive a JWT Bearer token.
- `GET /auth/me` — Retrieve the current user's profile and roles.

---

## Human-in-the-Loop Review Ledger

Credence maintains an append-only audit trail in the `review_ledger` table:
- **Zero Deletion:** Reviews, comments, and overrides are never updated or deleted.
- **Latest Override Wins:** Reports compute the effective verdict from the most recent valid override while preserving the original algorithmic verdict.
- **Mandatory Rationale:** Changing a verdict (`override`) strictly requires an explanation.
- **Audit Export:** Chronological review logs can be inspected via `/audit` or exported in reports.

---

## Benchmarking & Empirical Validation

Run the reproducible benchmark score gate:
```bash
python -m credence.benchmark.score
```

### Empirical Results Summary

| Evaluation Dataset | Samples | Accuracy | Macro Precision | Macro Recall | Macro F1 | ECE | Fabricated Quotes Caught |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Synthetic Corrupted (`gold_set.jsonl`)** | 100 | **97.00%** | 0.9631 | 0.9600 | 0.9599 | 0.0402 | **10/10 (100.0%)** |
| **Real-World Academic Evaluation** | 30 | **100.00%** | 1.0000 | 1.0000 | 1.0000 | 0.0633 | **Confirmed (100.0%)** |

---

## Automated Testing Suite

Credence maintains a comprehensive unit and integration test suite with 154 passing tests:

```bash
pytest -v
```

**Test Coverage Categories:**
- `test_checks.py`: Verbatim quote normalization, unit and number precision, epistemic hedges.
- `test_verdict.py`: Deterministic rule matrix and computed confidence formula.
- `test_ledger.py` & `test_override_complete.py`: Human-in-the-loop overrides, append-only persistence.
- `test_production_hardening.py`: JWT authentication, RBAC, file upload magic bytes, server restart recovery, rate limiting.
- `test_retraction_outdated.py`: Crossref and OpenAlex retraction and errata detection.
- `test_misleading_citations.py`: Off-topic, contradictory, and numerical discrepancy detection.
- `test_missing_citations.py`: Uncited empirical assertions, unmapped markers, orphan bibliography items.
- `test_source_traceability.py`: Page and section extraction, verbatim evidence highlighting.
- `test_benchmark_real.py`: Real-world academic validation and confusion matrix calculation.

---

## License

MIT License. Designed and developed for verifiable, reproducible scientific claim verification.
