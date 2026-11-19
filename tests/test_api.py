"""Unit tests for FastAPI endpoints: /health, /demo/report, /verify, /report/{id}, /report/{id}/review."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from credence.server import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_demo_claim_reviews():
    """Ensure demo claim-1 has a clean slate for baseline demo tests."""
    from credence.report.ledger import get_connection
    with get_connection() as conn:
        conn.execute("DELETE FROM review_ledger WHERE claim_id = 'claim-1';")
        conn.commit()
    yield
    with get_connection() as conn:
        conn.execute("DELETE FROM review_ledger WHERE claim_id = 'claim-1';")
        conn.commit()


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
    verdict_text = (learnfast["verdict"].get("original_verdict") or learnfast["verdict"]["display_verdict"]).lower()
    assert "partially supported" in verdict_text


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


def test_verify_forced_error_and_invalid_extension():
    """Verify error states: forced pipeline error and invalid file format return friendly messages."""
    pdf_path = Path("data/demo/sample_paper.pdf")
    with open(pdf_path, "rb") as f:
        err_resp = client.post(
            "/verify?force_error=true",
            files={"file": ("sample_paper.pdf", f, "application/pdf")},
        )
    assert err_resp.status_code == 500
    err_data = err_resp.json()
    assert "Verification pipeline forced error" in err_data["detail"]

    bad_resp = client.post(
        "/verify",
        files={"file": ("notes.txt", b"plain text content", "text/plain")},
    )
    assert bad_resp.status_code == 400
    bad_data = bad_resp.json()
    assert "Supported file formats" in bad_data["detail"]


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


def test_benchmark_endpoint():
    """Verify GET /benchmark serves real evaluation numbers."""
    resp = client.get("/benchmark")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_samples"] >= 40
    assert data["overall_accuracy"] >= 0.80
    assert data["fabricated_quotes_caught"] >= 1
    assert "supported" in data["per_verdict"]
    assert len(data["calibration_bins"]) >= 5


def test_export_report_formats():
    """Verify GET /report/{id}/export generates downloadable HTML, Markdown, and JSON files."""
    # 1. HTML export
    res_html = client.get("/report/demo-report-1/export?format=html")
    assert res_html.status_code == 200
    assert "text/html" in res_html.headers["content-type"]
    assert "attachment; filename=" in res_html.headers["content-disposition"]
    assert "Credence Verification Report" in res_html.text

    # 2. Markdown export
    res_md = client.get("/report/demo-report-1/export?format=markdown")
    assert res_md.status_code == 200
    assert "text/markdown" in res_md.headers["content-type"]
    assert "# Credence Scientific Verification Dossier" in res_md.text

    # 3. JSON export
    res_json = client.get("/report/demo-report-1/export?format=json")
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers["content-type"]


def test_offline_demo_mode_upload():
    """Verify demo mode serves pre-cached data fully offline with 0 live API calls."""
    resp = client.post(
        "/verify?demo_mode=true",
        files={"file": ("offline_manuscript.pdf", b"%PDF-1.4 dummy", "application/pdf")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("offline_demo_mode") is True
    assert data.get("document_name") == "offline_manuscript.pdf"
    assert len(data.get("claims", [])) >= 1


def test_list_reports_endpoint():
    """Verify GET /reports returns historical verified reports list."""
    resp = client.get("/reports?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    assert isinstance(data.get("reports"), list)
    assert data.get("total", 0) >= 1


def test_api_redteam_challenge_endpoint():
    """Verify POST /api/redteam/challenge executes adversarial investigation."""
    payload = {
        "claim_id": "claim-2",
        "report_id": "demo-report-1",
        "claim_text": "Patients receiving Compound-X demonstrated a 12.1% reduction in 30-day mortality [1]",
        "citation_key": "1",
        "doi": "10.1056/NEJMoa1702345",
        "original_verdict": "supported",
        "original_confidence": 0.90,
        "demo_mode": True,
    }
    resp = client.post("/api/redteam/challenge", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    inv = data.get("investigation")
    assert inv is not None
    assert inv["claim_id"] == "claim-2"
    assert inv["overall_outcome"] == "Contested by contradictory evidence"
    assert len(inv["stage_b_counter_evidence"]) >= 1
    assert "nodes" in inv["dependency_graph"]
    assert len(inv["timeline"]) >= 1


def test_api_redteam_history_endpoint():
    """Verify GET /api/redteam/investigations/{claim_id} retrieves past runs."""
    resp = client.get("/api/redteam/investigations/claim-2")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    assert data.get("claim_id") == "claim-2"
    assert isinstance(data.get("investigations"), list)
    assert len(data.get("investigations")) >= 1
