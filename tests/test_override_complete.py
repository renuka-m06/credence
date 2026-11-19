"""Comprehensive test suite for Credence Human Review Override functionality.

Covers the 10 mandatory verification gates:
1. Override a supported claim.
2. Override an unsupported claim.
3. Override without providing an explanation (must fail with 400).
4. Submit an invalid claim ID (empty / whitespace / null / undefined -> 400).
5. Refresh the browser after overriding (persistence on GET /report/{id} and GET /demo/report).
6. Override the same claim multiple times (ensure latest override wins).
7. Check whether review history is preserved (append-only ledger integrity, zero deletions).
8. Export a report after overriding (HTML, Markdown, and JSON reflect effective verdict and preserve original automated verdict).
9. Verify that the latest override is displayed.
10. Verify that the original verdict remains available.
"""

import json
import sqlite3
import uuid
import pytest
from fastapi.testclient import TestClient

from credence.server import app, REPORTS_STORE, _generate_demo_report
from credence.report.ledger import (
    get_connection,
    get_reviews_for_claim,
    get_latest_override,
    apply_ledger_to_report,
    record_review,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_demo_report():
    """Ensure a clean demo report is seeded in REPORTS_STORE before each test."""
    _generate_demo_report()


def test_01_override_supported_claim():
    """Test Case 1: Override a supported claim."""
    claim_id = f"test-claim-supp-{uuid.uuid4().hex[:6]}"
    report_id = f"test-rep-{uuid.uuid4().hex[:6]}"

    # Setup report with a supported claim
    REPORTS_STORE[report_id] = {
        "id": report_id,
        "document_name": "cardio_study.pdf",
        "claims": [
            {
                "id": claim_id,
                "text": "Drug A reduces mortality by 12%",
                "verdict": {
                    "claim_id": claim_id,
                    "verdict": "supported",
                    "display_verdict": "Supported",
                    "confidence": 0.95,
                    "needs_review": False,
                },
            }
        ],
        "summary": {"supported": 1, "needs_review": 0, "contradictory": 0},
    }

    # Override supported -> contradictory
    res = client.post(
        f"/claims/{claim_id}/review",
        json={
            "action": "override",
            "override_verdict": "contradictory",
            "explanation": "Independent meta-analysis 2025 disproved mortality benefit.",
            "reviewer_id": "dr-smith",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "ok"
    assert data["claim_id"] == claim_id
    assert data["review"]["action"] == "override"
    assert data["review"]["override_verdict"] == "contradictory"
    assert data["review"]["original_verdict"] == "supported"
    assert "disproved" in data["review"]["explanation"]

    # Verify report reflects effective verdict
    rep_res = client.get(f"/report/{report_id}")
    assert rep_res.status_code == 200
    claim = rep_res.json()["claims"][0]
    assert claim["verdict"]["verdict"] == "contradictory"
    assert "Contradictory (Overridden)" in claim["verdict"]["display_verdict"]
    assert claim["verdict"]["original_verdict"] == "supported"


def test_02_override_unsupported_claim():
    """Test Case 2: Override an unsupported claim."""
    claim_id = f"test-claim-unsupp-{uuid.uuid4().hex[:6]}"
    report_id = f"test-rep-{uuid.uuid4().hex[:6]}"

    REPORTS_STORE[report_id] = {
        "id": report_id,
        "document_name": "oncology.pdf",
        "claims": [
            {
                "id": claim_id,
                "text": "Compound-X produced 95% survival advantage",
                "verdict": {
                    "claim_id": claim_id,
                    "verdict": "unsupported",
                    "display_verdict": "Unsupported",
                    "confidence": 0.88,
                    "needs_review": False,
                },
            }
        ],
        "summary": {"supported": 0, "unsupported": 1},
    }

    # Override unsupported -> supported
    res = client.post(
        f"/claims/{claim_id}/review",
        json={
            "action": "override",
            "override_verdict": "supported",
            "explanation": "Author provided full trial registration and verified supplement tables.",
            "reviewer_id": "reviewer-senior",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["review"]["override_verdict"] == "supported"

    rep = client.get(f"/report/{report_id}").json()
    claim = rep["claims"][0]
    assert claim["verdict"]["verdict"] == "supported"
    assert "Supported (Overridden)" in claim["verdict"]["display_verdict"]
    assert claim["verdict"]["original_verdict"] == "unsupported"


def test_03_override_without_explanation_fails():
    """Test Case 3: Override without providing an explanation must fail with 400 Bad Request."""
    claim_id = f"test-claim-noexpl-{uuid.uuid4().hex[:6]}"

    # Empty string explanation
    res1 = client.post(
        f"/claims/{claim_id}/review",
        json={
            "action": "override",
            "override_verdict": "supported",
            "explanation": "",
        },
    )
    assert res1.status_code == 400
    assert "mandatory explanation" in res1.json()["detail"].lower()

    # Whitespace-only explanation
    res2 = client.post(
        f"/claims/{claim_id}/review",
        json={
            "action": "override",
            "override_verdict": "supported",
            "explanation": "     ",
        },
    )
    assert res2.status_code == 400
    assert "mandatory explanation" in res2.json()["detail"].lower()

    # None / omitted explanation
    res3 = client.post(
        f"/claims/{claim_id}/review",
        json={
            "action": "override",
            "override_verdict": "supported",
        },
    )
    assert res3.status_code == 400
    assert "mandatory explanation" in res3.json()["detail"].lower()

    # Ensure no record was inserted
    reviews = get_reviews_for_claim(claim_id)
    assert len(reviews) == 0


def test_04_submit_invalid_claim_id():
    """Test Case 4: Submit an invalid claim ID."""
    invalid_ids = ["%20%20", "null", "undefined", "none"]

    for inv_id in invalid_ids:
        res = client.post(
            f"/claims/{inv_id}/review",
            json={
                "action": "override",
                "override_verdict": "supported",
                "explanation": "Valid explanation but invalid claim ID.",
            },
        )
        assert res.status_code == 400, f"Expected 400 for claim_id '{inv_id}', got {res.status_code}"
        assert "invalid claim id" in res.json()["detail"].lower()


def test_05_refresh_browser_persists_override():
    """Test Case 5: Refresh the browser after overriding (persists across reloads)."""
    # Override claim-1 in demo report
    override_expl = "Expert consensus confirms 12% gain is clinically significant."
    res = client.post(
        "/claims/claim-1/review",
        json={
            "action": "override",
            "override_verdict": "supported",
            "explanation": override_expl,
            "reviewer_id": "dr-reload-tester",
        },
    )
    assert res.status_code == 200

    # Simulate fresh reload 1: GET /demo/report
    demo_rep = client.get("/demo/report").json()
    c1 = next(c for c in demo_rep["claims"] if c["id"] == "claim-1")
    assert c1["verdict"]["verdict"] == "supported"
    assert "Supported (Overridden)" in c1["verdict"]["display_verdict"]
    assert c1["verdict"]["override_info"]["explanation"] == override_expl

    # Simulate fresh reload 2: GET /report/demo-report-1
    full_rep = client.get("/report/demo-report-1").json()
    c1_full = next(c for c in full_rep["claims"] if c["id"] == "claim-1")
    assert c1_full["verdict"]["verdict"] == "supported"
    assert "Supported (Overridden)" in c1_full["verdict"]["display_verdict"]


def test_06_override_same_claim_multiple_times():
    """Test Case 6: Override the same claim multiple times (latest override wins)."""
    claim_id = f"test-claim-multi-{uuid.uuid4().hex[:6]}"
    report_id = f"test-rep-{uuid.uuid4().hex[:6]}"

    REPORTS_STORE[report_id] = {
        "id": report_id,
        "document_name": "multi_test.pdf",
        "claims": [
            {
                "id": claim_id,
                "text": "Initial test claim",
                "verdict": {
                    "claim_id": claim_id,
                    "verdict": "needs review",
                    "display_verdict": "Needs review",
                },
            }
        ],
        "summary": {"needs_review": 1},
    }

    # Override 1: -> partially supported
    r1 = client.post(
        f"/claims/{claim_id}/review",
        json={
            "action": "override",
            "override_verdict": "partially supported",
            "explanation": "Override 1: Partially proven.",
        },
    )
    assert r1.status_code == 200

    # Override 2: -> potentially outdated
    r2 = client.post(
        f"/claims/{claim_id}/review",
        json={
            "action": "override",
            "override_verdict": "potentially outdated",
            "explanation": "Override 2: Guidelines changed in 2024.",
        },
    )
    assert r2.status_code == 200

    # Override 3: -> unsupported
    r3 = client.post(
        f"/claims/{claim_id}/review",
        json={
            "action": "override",
            "override_verdict": "unsupported",
            "explanation": "Override 3: Final consensus: fully unsupported.",
        },
    )
    assert r3.status_code == 200

    # Check report: latest override (Override 3: unsupported) must win
    rep = client.get(f"/report/{report_id}").json()
    cl = rep["claims"][0]
    assert cl["verdict"]["verdict"] == "unsupported"
    assert "Unsupported (Overridden)" in cl["verdict"]["display_verdict"]
    assert cl["verdict"]["override_info"]["explanation"] == "Override 3: Final consensus: fully unsupported."


def test_07_review_history_is_preserved_append_only():
    """Test Case 7: Check whether review history is preserved (append-only ledger, zero deletions)."""
    claim_id = f"test-claim-hist-{uuid.uuid4().hex[:6]}"

    # Add 1 accept, 1 comment, 2 overrides
    client.post(
        f"/claims/{claim_id}/review",
        json={"action": "accept", "comment": "Accepting baseline.", "reviewer_id": "r-1"},
    )
    client.post(
        f"/claims/{claim_id}/review",
        json={"action": "comment", "comment": "Comment on methodology.", "reviewer_id": "r-2"},
    )
    client.post(
        f"/claims/{claim_id}/review",
        json={
            "action": "override",
            "override_verdict": "partially supported",
            "explanation": "Overriding to partial.",
            "reviewer_id": "r-3",
        },
    )
    client.post(
        f"/claims/{claim_id}/review",
        json={
            "action": "override",
            "override_verdict": "contradictory",
            "explanation": "Overriding to contradictory.",
            "reviewer_id": "r-4",
        },
    )

    # Fetch from API endpoint /claims/{id}/reviews
    hist_res = client.get(f"/claims/{claim_id}/reviews")
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert hist_data["total_reviews"] == 4
    actions = [r["action"] for r in hist_data["reviews"]]
    assert actions == ["accept", "comment", "override", "override"]

    # Verify directly in SQLite database table review_ledger: zero deletions, all 4 intact
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT action, override_verdict, explanation FROM review_ledger WHERE claim_id = ? ORDER BY id ASC;",
            (claim_id,),
        )
        rows = cursor.fetchall()
        assert len(rows) == 4
        assert rows[0][0] == "accept"
        assert rows[1][0] == "comment"
        assert rows[2][0] == "override" and rows[2][1] == "partially supported"
        assert rows[3][0] == "override" and rows[3][1] == "contradictory"


def test_08_export_report_after_overriding():
    """Test Case 8: Export a report after overriding (HTML, Markdown, and JSON reflect effective verdict and preserve original)."""
    claim_id = f"test-claim-exp-{uuid.uuid4().hex[:6]}"
    report_id = f"test-rep-exp-{uuid.uuid4().hex[:6]}"

    REPORTS_STORE[report_id] = {
        "id": report_id,
        "document_name": "export_test.pdf",
        "claims": [
            {
                "id": claim_id,
                "text": "Cardiovascular risk is lowered by 40%",
                "source_location": "Page 5, Paragraph 2",
                "citation_keys": ["Ref12"],
                "verdict": {
                    "claim_id": claim_id,
                    "verdict": "needs review",
                    "display_verdict": "Needs review",
                    "confidence": 0.45,
                    "original_verdict": "needs review",
                },
            }
        ],
        "summary": {"needs_review": 1, "supported": 0, "human_overrides": 0},
    }

    # Override the claim
    client.post(
        f"/claims/{claim_id}/review",
        json={
            "action": "override",
            "override_verdict": "supported",
            "explanation": "Clinician committee verified endpoint statistics.",
            "reviewer_id": "dr-chair",
            "original_verdict": "needs review",
        },
    )

    # 1. JSON Export
    json_res = client.get(f"/report/{report_id}/export?format=json")
    assert json_res.status_code == 200
    assert json_res.headers["content-type"].startswith("application/json")
    json_data = json.loads(json_res.text)
    exp_claim = json_data["claims"][0]
    assert exp_claim["verdict"]["verdict"] == "supported"
    assert exp_claim["verdict"]["original_verdict"] == "needs review"
    assert exp_claim["verdict"]["override_info"]["action"] == "override"

    # 2. Markdown Export
    md_res = client.get(f"/report/{report_id}/export?format=markdown")
    assert md_res.status_code == 200
    assert md_res.headers["content-type"].startswith("text/markdown")
    md_text = md_res.text
    assert "Effective Verdict (Overridden):" in md_text
    assert "Supported (Overridden)" in md_text
    assert "Original Automated Verdict:** `needs review`" in md_text
    assert "Clinician committee verified endpoint statistics." in md_text

    # 3. HTML Export
    html_res = client.get(f"/report/{report_id}/export?format=html")
    assert html_res.status_code == 200
    assert html_res.headers["content-type"].startswith("text/html")
    html_text = html_res.text
    assert "Supported (Overridden)" in html_text
    assert "Overridden by human reviewer" in html_text
    assert "Original Automated Verdict: <em>needs review</em>" in html_text


def test_09_verify_latest_override_is_displayed():
    """Test Case 9: Verify that the latest override is displayed."""
    claim_id = f"test-claim-latest-{uuid.uuid4().hex[:6]}"
    report_id = f"test-rep-latest-{uuid.uuid4().hex[:6]}"

    REPORTS_STORE[report_id] = {
        "id": report_id,
        "document_name": "sequencing.pdf",
        "claims": [
            {
                "id": claim_id,
                "text": "Genomic sequence shows 99% homology",
                "verdict": {
                    "claim_id": claim_id,
                    "verdict": "supported",
                    "display_verdict": "Supported",
                },
            }
        ],
        "summary": {"supported": 1},
    }

    # First override -> contradictory
    client.post(
        f"/claims/{claim_id}/review",
        json={"action": "override", "override_verdict": "contradictory", "explanation": "Pass 1"},
    )
    # Second override -> potentially outdated
    client.post(
        f"/claims/{claim_id}/review",
        json={"action": "override", "override_verdict": "potentially outdated", "explanation": "Pass 2: Latest update"},
    )

    # API: GET /claims/{id}/reviews -> check latest_override
    rev_info = client.get(f"/claims/{claim_id}/reviews").json()
    assert rev_info["latest_override"]["override_verdict"] == "potentially outdated"
    assert rev_info["latest_override"]["explanation"] == "Pass 2: Latest update"

    # Report: GET /report/{id} -> check displayed verdict
    rep = client.get(f"/report/{report_id}").json()
    assert rep["claims"][0]["verdict"]["verdict"] == "potentially outdated"
    assert "potentially outdated (overridden)" in rep["claims"][0]["verdict"]["display_verdict"].lower()


def test_10_verify_original_verdict_remains_available():
    """Test Case 10: Verify that the original verdict remains available after overrides."""
    claim_id = f"test-claim-orig-{uuid.uuid4().hex[:6]}"
    report_id = f"test-rep-orig-{uuid.uuid4().hex[:6]}"

    initial_verdict = "supported"
    REPORTS_STORE[report_id] = {
        "id": report_id,
        "document_name": "conservation.pdf",
        "claims": [
            {
                "id": claim_id,
                "text": "Species diversity increased by 15%",
                "verdict": {
                    "claim_id": claim_id,
                    "verdict": initial_verdict,
                    "display_verdict": "Supported",
                },
            }
        ],
        "summary": {"supported": 1},
    }

    # Perform multiple overrides
    client.post(
        f"/claims/{claim_id}/review",
        json={"action": "override", "override_verdict": "needs review", "explanation": "Audit needed"},
    )
    client.post(
        f"/claims/{claim_id}/review",
        json={"action": "override", "override_verdict": "unsupported", "explanation": "Control bias confirmed"},
    )

    # Check report: original_verdict must still be initial_verdict ("supported")
    rep = client.get(f"/report/{report_id}").json()
    claim_data = rep["claims"][0]
    assert claim_data["verdict"]["verdict"] == "unsupported"
    assert claim_data["verdict"]["original_verdict"] == initial_verdict
