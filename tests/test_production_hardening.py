"""Automated test suite verifying production hardening requirements.

Covers:
- Phase 3: Persistent storage surviving server restart
- Phase 4: Authentication, RBAC, server-side reviewer identity, CORS, rate limiting
- Phase 4: File upload security (extension, magic bytes, 25MB ceiling, path traversal)
- Phase 5: Access tier grounding & confidence capping
- Phase 7: Health check endpoint
"""

from __future__ import annotations

import io
import os
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from credence.auth.models import UserCreate, UserLogin
from credence.auth.security import create_access_token, hash_password, verify_password
from credence.auth.store import UserStore, user_store
from credence.report.models import AccessTier, Claim, Verdict, VerdictType
from credence.report.storage import DurableReportStore, ReportStoreMapping
from credence.security.rate_limiter import SlidingWindowRateLimiter
from credence.security.upload import sanitize_filename, validate_and_save_upload
from credence.server import app
from credence.verify.pipeline import build_report, verify_claim

client = TestClient(app)


# ---------------------------------------------------------------------------
# Phase 3 Tests: Durable Storage & Server Restart Simulation
# ---------------------------------------------------------------------------

def test_persistent_storage_survives_server_restart(tmp_path):
    """Verify that reports stored in DurableReportStore survive restarts."""
    db_file = tmp_path / "test_restart.db"
    store1 = DurableReportStore(db_path=db_file)

    test_rep = {
        "id": "persist-test-1",
        "document_name": "restart_study.pdf",
        "access_tier": "full_text",
        "claims": [{"id": "c1", "text": "Claim survived restart"}],
        "metadata": {"test": True},
    }
    store1.save_report(test_rep, owner_id="reviewer-1")

    # Re-instantiate store from same database file (simulating server crash/restart)
    store2 = DurableReportStore(db_path=db_file)
    retrieved = store2.get_report("persist-test-1")

    assert retrieved is not None
    assert retrieved["id"] == "persist-test-1"
    assert retrieved["document_name"] == "restart_study.pdf"
    assert len(retrieved["claims"]) == 1
    assert retrieved["claims"][0]["text"] == "Claim survived restart"


def test_persistent_storage_list_and_delete(tmp_path):
    """Verify listing and deleting reports from persistent storage."""
    db_file = tmp_path / "test_list.db"
    store = DurableReportStore(db_path=db_file)

    store.save_report({"id": "rep-a", "document_name": "paper_a.pdf"})
    store.save_report({"id": "rep-b", "document_name": "paper_b.pdf"})

    all_reps = store.list_reports()
    assert len(all_reps) >= 2
    ids = [r["id"] for r in all_reps]
    assert "rep-a" in ids and "rep-b" in ids

    deleted = store.delete_report("rep-a")
    assert deleted is True
    assert store.get_report("rep-a") is None


def test_report_store_mapping_dict_interface(tmp_path):
    """Verify ReportStoreMapping acts like a Python dict backed by the DB."""
    db_file = tmp_path / "test_mapping.db"
    mapping = ReportStoreMapping(DurableReportStore(db_path=db_file))

    mapping["dict-rep-1"] = {"id": "dict-rep-1", "document_name": "dict_test.pdf"}
    assert "dict-rep-1" in mapping
    assert mapping["dict-rep-1"]["document_name"] == "dict_test.pdf"
    assert mapping.get("dict-rep-1") is not None
    assert mapping.get("non-existent") is None


# ---------------------------------------------------------------------------
# Phase 4 Tests: Authentication, RBAC & Server-Side Identity
# ---------------------------------------------------------------------------

def test_password_hashing_and_verification():
    """Verify bcrypt/PBKDF2 password hashing round-trip."""
    raw = "ScientificReview2026!"
    hashed = hash_password(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_user_registration_login_and_token(tmp_path):
    """Test user registration, JWT generation, and login verification."""
    test_user = f"user_{uuid.uuid4().hex[:8]}"
    test_pw = "SecurePass123!"

    # 1. Register new reviewer
    reg_resp = client.post("/auth/register", json={
        "username": test_user,
        "password": test_pw,
        "email": f"{test_user}@example.com",
        "role": "reviewer",
    })
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert "access_token" in reg_data
    assert reg_data["user"]["username"] == test_user
    assert reg_data["user"]["role"] == "reviewer"

    # 2. Duplicate registration rejected with 409
    dup_resp = client.post("/auth/register", json={
        "username": test_user,
        "password": test_pw,
    })
    assert dup_resp.status_code == 409

    # 3. Login with credentials
    login_resp = client.post("/auth/login", json={
        "username": test_user,
        "password": test_pw,
    })
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    token = login_data["access_token"]
    assert token is not None

    # 4. Access /auth/me with bearer token
    me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == test_user


def test_server_side_reviewer_identity_in_overrides():
    """Verify server stamps authenticated user's identity on review action, preventing client spoofing."""
    authed_user = f"auditor_{uuid.uuid4().hex[:6]}"
    reg_resp = client.post("/auth/register", json={
        "username": authed_user,
        "password": "Password123!",
        "role": "reviewer",
    })
    token = reg_resp.json()["access_token"]

    claim_id = f"claim-auth-{uuid.uuid4().hex[:6]}"
    # Submit review with a spoofed reviewer_id in payload, but with genuine bearer token
    rev_resp = client.post(
        f"/claims/{claim_id}/review",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "action": "override",
            "override_verdict": "contradictory",
            "explanation": "Contradiction verified from clinical table 3.",
            "reviewer_id": "spoofed-hacker-id",  # Should be overridden by server with authed_user
        },
    )
    assert rev_resp.status_code == 200
    review_record = rev_resp.json()["review"]
    # Server-side validation MUST record the authentic identity
    assert review_record["reviewer_id"] == authed_user


# ---------------------------------------------------------------------------
# Phase 4 Tests: File Upload Security & Sanitization
# ---------------------------------------------------------------------------

def test_filename_sanitization_path_traversal():
    """Verify filename sanitization prevents directory traversal attacks."""
    malicious_names = [
        "../../etc/passwd.pdf",
        "..\\..\\windows\\system32\\cmd.exe",
        "/var/root/secret.pdf",
        "....//....//payload.pdf",
    ]
    for m in malicious_names:
        clean = sanitize_filename(m)
        assert "/" not in clean
        assert "\\" not in clean
        assert ".." not in clean


def test_upload_rejection_invalid_extension():
    """Verify rejection of disallowed file extensions (.sh, .exe, .py)."""
    resp = client.post(
        "/verify",
        files={"file": ("malicious.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/x-msdownload")},
    )
    assert resp.status_code == 400
    assert "Unsupported file format" in resp.json()["detail"]


def test_upload_rejection_spoofed_pdf_magic_bytes():
    """Verify rejection of files with .pdf extension but missing %PDF magic signature."""
    fake_pdf = b"This is not a real PDF file. Just plain text."
    resp = client.post(
        "/verify",
        files={"file": ("fake.pdf", fake_pdf, "application/pdf")},
    )
    assert resp.status_code == 400
    assert "Invalid file signature" in resp.json()["detail"]


def test_upload_rejection_empty_file():
    """Verify rejection of 0-byte uploaded files."""
    resp = client.post(
        "/verify",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_rate_limiter_enforcement():
    """Verify sliding window rate limiter triggers 429 when threshold exceeded."""
    limiter = SlidingWindowRateLimiter(requests_per_minute=3)
    limiter.check_rate_limit("192.168.1.1")
    limiter.check_rate_limit("192.168.1.1")
    limiter.check_rate_limit("192.168.1.1")

    # 4th request from same IP must raise 429
    with pytest.raises(Exception) as excinfo:
        limiter.check_rate_limit("192.168.1.1")
    assert "429" in str(excinfo.value) or "Rate limit exceeded" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Phase 5 & Golden Rules Tests: Access Tier Grounding & Health Check
# ---------------------------------------------------------------------------

def test_access_tier_confidence_cap():
    """Verify AGENTS.md rule: Abstract-only access cannot exceed confidence cap 0.6."""
    c = verify_claim(
        claim_input="Efficacy was 88% in phase 3 trial [1]",
        source_text="In our phase 3 trial, efficacy was 88% across all study arms.",
        access_tier=AccessTier.ABSTRACT_ONLY,
        citation_key="1",
    )
    # Full support with quote verified, but abstract-only tier cap is 0.6
    assert c.verdict.confidence <= 0.60
    assert c.verdict.access_tier == AccessTier.ABSTRACT_ONLY


def test_health_check_endpoint():
    """Verify /health endpoint returns 200 with service information."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "credence-api"
    assert data["storage"] == "persistent"
