"""Unit tests for the append-only SQLite review ledger and human review endpoints."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from credence.report.ledger import (
    apply_ledger_to_claim,
    apply_ledger_to_report,
    get_audit_log,
    get_latest_override,
    get_reviews_for_claim,
    init_ledger,
    record_review,
)
from credence.server import app

client = TestClient(app)


@pytest.fixture
def temp_db(tmp_path):
    """Provide a clean temporary SQLite database for isolated ledger tests."""
    db_file = tmp_path / "test_ledger.db"
    init_ledger(db_file)
    return db_file


def test_append_only_record_review(temp_db):
    """Test recording accept, comment, and override actions into the append-only ledger."""
    # 1. Accept action
    rev1 = record_review(
        claim_id="claim-101",
        action="accept",
        comment="Algorithm finding confirmed against source.",
        reviewer_id="reviewer-alpha",
        db_path=temp_db,
    )
    assert rev1["action"] == "accept"
    assert rev1["claim_id"] == "claim-101"
    assert rev1["review_id"].startswith("rev-")

    # 2. Comment action
    rev2 = record_review(
        claim_id="claim-101",
        action="comment",
        comment="Note: author published a 2024 erratum.",
        reviewer_id="reviewer-beta",
        db_path=temp_db,
    )
    assert rev2["action"] == "comment"

    # 3. Override action
    rev3 = record_review(
        claim_id="claim-101",
        action="override",
        override_verdict="supported",
        comment="Full cohort replication proves claim.",
        reviewer_id="reviewer-gamma",
        db_path=temp_db,
    )
    assert rev3["action"] == "override"
    assert rev3["override_verdict"] == "supported"

    # Verify chronological retrieval
    history = get_reviews_for_claim("claim-101", db_path=temp_db)
    assert len(history) == 3
    assert [h["action"] for h in history] == ["accept", "comment", "override"]

    # Verify latest override
    latest_ov = get_latest_override("claim-101", db_path=temp_db)
    assert latest_ov is not None
    assert latest_ov["override_verdict"] == "supported"
    assert latest_ov["reviewer_id"] == "reviewer-gamma"


def test_review_validation_errors(temp_db):
    """Test that invalid actions and missing override verdicts raise errors."""
    with pytest.raises(ValueError, match="Invalid review action"):
        record_review(claim_id="claim-1", action="invalid_action", db_path=temp_db)

    with pytest.raises(ValueError, match="Override action requires"):
        record_review(claim_id="claim-1", action="override", override_verdict=None, db_path=temp_db)


def test_apply_ledger_to_report(temp_db):
    """Test that ledger overrides update claim verdicts and recalculate summary tallies."""
    sample_report = {
        "id": "rep-test",
        "document_name": "paper.pdf",
        "claims": [
            {
                "id": "c-1",
                "text": "Claim 1",
                "verdict": {
                    "claim_id": "c-1",
                    "verdict": "needs review",
                    "display_verdict": "Needs review",
                    "needs_review": True,
                },
            },
            {
                "id": "c-2",
                "text": "Claim 2",
                "verdict": {
                    "claim_id": "c-2",
                    "verdict": "contradictory",
                    "display_verdict": "Contradictory",
                    "needs_review": True,
                },
            },
        ],
        "summary": {
            "supported": 0,
            "partially_supported": 0,
            "unsupported": 0,
            "contradictory": 1,
            "needs_review": 1,
            "human_review_required": True,
        },
    }

    # Record override for c-1: needs review -> supported
    record_review(
        claim_id="c-1",
        action="override",
        override_verdict="supported",
        comment="Verified independently.",
        db_path=temp_db,
    )

    updated_report = apply_ledger_to_report(sample_report, db_path=temp_db)
    claim_1 = updated_report["claims"][0]
    assert claim_1["verdict"]["verdict"] == "supported"
    assert "Supported (Overridden)" in claim_1["verdict"]["display_verdict"]
    assert claim_1["verdict"]["override_info"]["action"] == "override"
    assert len(claim_1["reviews"]) == 1

    # Check updated summary tallies
    assert updated_report["summary"]["supported"] == 1
    assert updated_report["summary"]["needs_review"] == 0
    assert updated_report["summary"]["contradictory"] == 1
    assert updated_report["summary"]["human_overrides"] == 1


def test_audit_log(temp_db):
    """Test global audit log retrieval."""
    record_review(claim_id="c-10", action="comment", comment="First comment", db_path=temp_db)
    record_review(claim_id="c-20", action="accept", comment="Second accept", db_path=temp_db)

    audit = get_audit_log(limit=10, db_path=temp_db)
    assert len(audit) >= 2
    # Newest first
    assert audit[0]["claim_id"] == "c-20"
    assert audit[1]["claim_id"] == "c-10"


def test_api_endpoints_and_reload_persistence_gate():
    """GATE TEST: An override submitted via POST /claims/{id}/review persists across reloads."""
    import uuid
    claim_id = f"claim-gate-test-{uuid.uuid4().hex[:6]}"

    # 1. Post override action to /claims/{id}/review
    post_resp = client.post(
        f"/claims/{claim_id}/review",
        json={
            "action": "override",
            "override_verdict": "supported",
            "comment": "Persisting override across reload test.",
            "reviewer_id": "dr-smith",
        },
    )
    assert post_resp.status_code == 200
    data = post_resp.json()
    assert data["status"] == "ok"
    assert data["claim_id"] == claim_id
    assert data["review"]["action"] == "override"
    assert data["review"]["override_verdict"] == "supported"

    # 2. Add an academic comment to same claim
    comment_resp = client.post(
        f"/claims/{claim_id}/review",
        json={
            "action": "comment",
            "comment": "Supplemental data attached.",
            "reviewer_id": "dr-smith",
        },
    )
    assert comment_resp.status_code == 200

    # 3. Simulate page reload / new session by fetching /claims/{id}/reviews
    history_resp = client.get(f"/claims/{claim_id}/reviews")
    assert history_resp.status_code == 200
    history_data = history_resp.json()
    assert history_data["total_reviews"] == 2
    assert history_data["latest_override"]["override_verdict"] == "supported"
    assert [r["action"] for r in history_data["reviews"]] == ["override", "comment"]

    # 4. Check global audit endpoint
    audit_resp = client.get("/audit?limit=5")
    assert audit_resp.status_code == 200
    audit_entries = audit_resp.json()["audit_log"]
    assert any(e["claim_id"] == claim_id for e in audit_entries)

    # 5. Verify persistence across report reload with custom report
    custom_report_id = "test-reload-report-99"
    from credence.server import REPORTS_STORE
    test_claim_id = "claim-gate-reload-1"
    REPORTS_STORE[custom_report_id] = {
        "id": custom_report_id,
        "document_name": "gate_test.pdf",
        "claims": [
            {
                "id": test_claim_id,
                "text": "Intervention shows preliminary benefit",
                "verdict": {
                    "claim_id": test_claim_id,
                    "verdict": "needs review",
                    "display_verdict": "Needs review",
                    "needs_review": True,
                },
            }
        ],
        "summary": {"needs_review": 1, "supported": 0},
    }

    # Override test_claim_id to 'supported' via POST /claims/{id}/review
    ov_resp = client.post(
        f"/claims/{test_claim_id}/review",
        json={"action": "override", "override_verdict": "supported", "comment": "Confirmed by panel."},
    )
    assert ov_resp.status_code == 200

    # Fresh reload of /report/{id}: Gate asserts override persisted
    reloaded_rep = client.get(f"/report/{custom_report_id}").json()
    target_claim = next(c for c in reloaded_rep["claims"] if c["id"] == test_claim_id)
    assert target_claim["verdict"]["verdict"] == "supported"
    assert "Supported (Overridden)" in target_claim["verdict"]["display_verdict"]
    assert len(target_claim["reviews"]) >= 1
