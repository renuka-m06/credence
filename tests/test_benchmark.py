"""Unit tests for credence.benchmark.corrupt and credence.benchmark.score."""

import json
from pathlib import Path

from credence.benchmark.corrupt import (
    BASE_SCIENTIFIC_CLAIMS,
    generate_gold_dataset,
    inject_fake_doi,
    inject_fabricated_quote,
    inject_negation,
    inject_number_swap,
    inject_scope_widen,
    inject_unrelated_citation,
)
from credence.benchmark.score import evaluate_benchmark


def test_corrupt_functions():
    base = BASE_SCIENTIFIC_CLAIMS[0]

    # 1. Number swap
    ns = inject_number_swap(base)
    assert ns["corruption_type"] == "number_swap"
    assert ns["expected_verdict"] == "partially supported"
    assert "30" in ns["claim_text"] or ns["claim_text"] != base["claim_text"]

    # 2. Negation
    neg = inject_negation(base)
    assert neg["corruption_type"] == "negation"
    assert neg["expected_verdict"] == "contradictory"
    assert any(term in neg["claim_text"].lower() for term in ("failed to", "increased", "did not"))

    # 3. Scope widen
    sw = inject_scope_widen(base)
    assert sw["corruption_type"] == "scope_widen"
    assert sw["expected_verdict"] == "unsupported"
    assert any(term in sw["claim_text"].lower() for term in ("definitively", "all human", "cures", "guarantees"))

    # 4. Unrelated citation
    unrel = inject_unrelated_citation(base)
    assert unrel["corruption_type"] == "unrelated_citation"
    assert unrel["expected_verdict"] == "unsupported"

    # 5. Fake DOI
    fake = inject_fake_doi(base, 42)
    assert fake["corruption_type"] == "fake_doi"
    assert fake["expected_verdict"] == "needs review"
    assert "10.9999/fake.doi" in fake["doi"]

    # 6. Fabricated quote
    fab = inject_fabricated_quote(base)
    assert fab["corruption_type"] == "fabricated_quote"
    assert fab["expected_verdict"] == "needs review"
    assert fab["fabricated_quote"] is not None


def test_gold_dataset_generation(tmp_path):
    out_file = tmp_path / "test_gold.jsonl"
    dataset = generate_gold_dataset(str(out_file))
    assert 40 <= len(dataset) <= 50
    assert out_file.exists()

    with open(out_file, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f]
    assert len(lines) == len(dataset)

    # Ensure all corruption types are present
    types = {item["corruption_type"] for item in lines}
    assert types == {"none", "number_swap", "negation", "scope_widen", "unrelated_citation", "fake_doi", "fabricated_quote"}


def test_score_benchmark_evaluation():
    report = evaluate_benchmark("gold_set.jsonl")
    assert report.total_samples == 100
    assert report.overall_accuracy >= 0.90
    assert report.macro_f1 >= 0.90
    assert report.fabricated_quotes_caught == report.fabricated_quotes_tested == 10
    assert report.hallucination_catch_rate == 1.0

    # Needs review and Unsupported should be 1.0 precision and recall
    assert report.per_verdict["needs review"].precision == 1.0
    assert report.per_verdict["needs review"].recall == 1.0
    assert report.per_verdict["unsupported"].precision == 1.0
    assert report.per_verdict["unsupported"].recall == 1.0
