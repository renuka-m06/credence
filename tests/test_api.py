"""Unit tests for FastAPI endpoints: /health, /demo/report, /verify, /report/{id}, /report/{id}/review."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from credence.server import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_get_demo_report():
    resp = client.get("/demo/report")
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert "claims" in data
    assert len(data["claims"]) >= 3
    # First claim should be LearnFast
    learnfast = data["claims"][0]
    assert "LearnFast" in learnfast["text"]
    assert "Partially supported, needs review" in learnfast["verdict"]["display_verdict"]


def test_verify_text_claim():
    payload = {
        "claim_text": "Compound-X demonstrated a 12.1% reduction in 30-day mortality compared with placebo [1]",
        "source_text": "In a clinical trial, Compound-X demonstrated a 12.1% reduction in 30-day mortality compared with placebo.",
        "access_tier": "full_text",
        "citation_key": "1",
    }
    resp = client.post("/verify/text", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert len(data["claims"]) == 1
    assert data["claims"][0]["verdict"]["verdict"] == "supported"


def test_verify_document_upload():
    pdf_path = Path("data/demo/sample_paper.pdf")
    assert pdf_path.exists()

    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/verify",
            files={"file": ("sample_paper.pdf", f, "application/pdf")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["document_name"] == "sample_paper.pdf"
    assert len(data["claims"]) >= 1

    report_id = data["id"]
    # Check GET /report/{id}
    fetch_resp = client.get(f"/report/{report_id}")
    assert fetch_resp.status_code == 200
    assert fetch_resp.json()["id"] == report_id


def test_review_claim_actions():
    resp = client.get("/demo/report")
    report_id = resp.json()["id"]
    claim_id = resp.json()["claims"][0]["id"]

    # Test Accept
    accept_resp = client.post(
        f"/report/{report_id}/review?claim_id={claim_id}",
        json={"action": "accept", "comment": "Agreed with partial support verdict."},
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["review"]["action"] == "accept"

    # Test Override
    override_resp = client.post(
        f"/report/{report_id}/review?claim_id={claim_id}",
        json={"action": "override", "override_verdict": "contradictory", "comment": "Overriding to contradictory due to pilot size."},
    )
    assert override_resp.status_code == 200

    # Fetch updated report
    updated_report = client.get(f"/report/{report_id}").json()
    updated_claim = next(c for c in updated_report["claims"] if c["id"] == claim_id)
    assert updated_claim["verdict"]["verdict"] == "contradictory"
