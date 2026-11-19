"""Tests for Real-World Academic Benchmark & Validation Framework in Credence.

Validates Requirements 1-9:
- Real academic dataset with all 9 evaluation categories
- Empirical prediction comparison against ground truth
- Metrics: Accuracy, Precision, Recall, Macro F1, Confusion Matrix, ECE
- Retracted publication detection rate
- Distinguishes real-world from synthetic benchmark
- API endpoint integration
"""

import json
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from credence.benchmark.score import (
    VERDICT_CLASSES,
    BenchmarkReport,
    evaluate_benchmark,
)
from credence.benchmark.real_dataset import (
    REAL_ACADEMIC_EVAL_DATASET,
    REQUIRED_BENCHMARK_CATEGORIES,
)
from credence.server import app

client = TestClient(app)


def test_real_academic_dataset_schema_and_categories():
    """Requirement 1 & 2: Dataset contains all 9 evaluation categories with real academic papers."""
    assert len(REAL_ACADEMIC_EVAL_DATASET) >= 30

    present_categories = {c.category for c in REAL_ACADEMIC_EVAL_DATASET}
    for required_cat in REQUIRED_BENCHMARK_CATEGORIES:
        assert required_cat in present_categories, f"Missing category {required_cat} in evaluation dataset"

    # Verify every case has expected verdict and evidence (Requirement 3)
    for c in REAL_ACADEMIC_EVAL_DATASET:
        assert c.id
        assert c.claim_text
        assert c.expected_verdict in ("supported", "partially supported", "unsupported", "contradictory", "needs review")
        assert c.expected_evidence
        if c.category != "missing_citation":
            assert c.paper_title


def test_evaluate_benchmark_real_world():
    """Requirement 4 & 5: Evaluate real-world academic claims and verify performance metrics."""
    report = evaluate_benchmark("real")

    assert isinstance(report, BenchmarkReport)
    assert report.total_samples == 30
    assert report.dataset_type == "real_world"
    assert "Real-World" in report.dataset_name

    # Requirements 5: Accuracy, Precision, Recall, Macro F1 >= 90%
    assert report.overall_accuracy >= 0.90
    assert report.macro_precision >= 0.90
    assert report.macro_recall >= 0.90
    assert report.macro_f1 >= 0.90
    assert report.ece <= 0.15

    # Confusion matrix structure
    assert report.confusion_matrix is not None
    for exp_cls in VERDICT_CLASSES:
        assert exp_cls in report.confusion_matrix
        for pred_cls in VERDICT_CLASSES:
            assert pred_cls in report.confusion_matrix[exp_cls]
            assert isinstance(report.confusion_matrix[exp_cls][pred_cls], int)

    # Verify diagonal dominance (high true positives)
    diagonal_sum = sum(report.confusion_matrix[v][v] for v in VERDICT_CLASSES)
    assert diagonal_sum >= 27  # At least 90% accuracy

    # Category breakdown includes all categories
    assert len(report.category_breakdown) >= 9
    for cat in REQUIRED_BENCHMARK_CATEGORIES:
        assert cat in report.category_breakdown
        assert report.category_breakdown[cat]["total"] >= 3
        assert report.category_breakdown[cat]["accuracy"] >= 0.90


def test_retracted_publication_audit():
    """Requirement 2 & 5: Retracted research paper evaluation cases routed to needs review."""
    report = evaluate_benchmark("real")
    retracted_recs = [r for r in report.detailed_records if r.get("category") == "retracted_publication"]
    assert len(retracted_recs) == 3
    for rec in retracted_recs:
        assert rec["expected"] == "needs review"
        assert rec["predicted"] == "needs review"
        assert 0.0 <= rec["confidence"] <= 1.0  # Golden Rule 3: Tier cap minus slot penalties


def test_missing_and_misleading_citation_audit():
    """Requirement 2: Misleading and missing citation categorization and detection."""
    report = evaluate_benchmark("real")

    missing_recs = [r for r in report.detailed_records if r.get("category") == "missing_citation"]
    assert len(missing_recs) == 3
    for rec in missing_recs:
        assert rec["expected"] == "needs review"
        assert rec["predicted"] == "needs review"

    misleading_recs = [r for r in report.detailed_records if r.get("category") == "misleading_citation"]
    assert len(misleading_recs) == 3
    for rec in misleading_recs:
        assert rec["expected"] == "unsupported"
        assert rec["predicted"] == "unsupported"


def test_api_benchmark_real_and_synthetic_endpoints():
    """Requirement 6 & 7: API endpoints serve both real and synthetic benchmarks."""
    # 1. Real endpoint
    res_real = client.get("/benchmark/real")
    assert res_real.status_code == 200
    data_real = res_real.json()
    assert data_real["dataset_type"] == "real_world"
    assert data_real["total_samples"] == 30
    assert "confusion_matrix" in data_real
    assert "category_breakdown" in data_real

    # 2. Synthetic endpoint
    res_synth = client.get("/benchmark/synthetic")
    assert res_synth.status_code == 200
    data_synth = res_synth.json()
    assert data_synth["dataset_type"] == "synthetic"
    assert data_synth["total_samples"] == 100
    assert "confusion_matrix" in data_synth

    # 3. Combined /benchmark endpoint
    res_all = client.get("/benchmark")
    assert res_all.status_code == 200
    data_all = res_all.json()
    assert data_all["total_samples"] >= 40  # Backwards compatibility
    assert "real_world" in data_all
    assert "synthetic" in data_all
    assert data_all["real_world"]["total_samples"] == 30
    assert data_all["synthetic"]["total_samples"] == 100

    # 4. Query param ?dataset=real
    res_q = client.get("/benchmark?dataset=real")
    assert res_q.status_code == 200
    assert res_q.json()["dataset_type"] == "real_world"
