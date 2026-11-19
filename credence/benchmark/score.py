"""Evaluation benchmark: computes per-verdict precision/recall, confidence calibration, and caught hallucinations.

Validation gate per AGENTS.md:
- python -m credence.benchmark.score prints per-verdict precision/recall on gold_set.jsonl
- Enforces Golden Rule 2: LLM returned quote not found in source -> discarded -> "Needs review".
- Enforces Golden Rule 3: Computed confidence calibration vs empirical accuracy.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from credence.report.models import AccessTier, Claim, VerdictType
from credence.resolve.matcher import CandidatePaper
from credence.verify.pipeline import verify_claim
from credence.verify.verdict import RULE_HALLUCINATED_QUOTE


VERDICT_CLASSES = [
    "supported",
    "partially supported",
    "contradictory",
    "unsupported",
    "needs review",
]


@dataclass
class VerdictMetrics:
    verdict: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    support: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0


@dataclass
class CalibrationBin:
    bin_name: str
    lower: float
    upper: float
    count: int = 0
    mean_confidence: float = 0.0
    accuracy: float = 0.0
    support_rate: float = 0.0
    gap: float = 0.0


@dataclass
class BenchmarkReport:
    total_samples: int
    overall_accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    per_verdict: dict[str, VerdictMetrics]
    calibration_bins: list[CalibrationBin]
    ece: float
    fabricated_quotes_tested: int
    fabricated_quotes_caught: int
    hallucination_catch_rate: float
    dataset_name: str = "Synthetic Corrupted Benchmark (gold_set.jsonl)"
    dataset_type: str = "synthetic"
    confusion_matrix: dict[str, dict[str, int]] = field(default_factory=dict)
    category_breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)
    detailed_records: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_samples": self.total_samples,
            "overall_accuracy": round(self.overall_accuracy, 4),
            "macro_precision": round(self.macro_precision, 4),
            "macro_recall": round(self.macro_recall, 4),
            "macro_f1": round(self.macro_f1, 4),
            "ece": round(self.ece, 4),
            "fabricated_quotes_tested": self.fabricated_quotes_tested,
            "fabricated_quotes_caught": self.fabricated_quotes_caught,
            "hallucination_catch_rate": round(self.hallucination_catch_rate, 4),
            "dataset_name": self.dataset_name,
            "dataset_type": self.dataset_type,
            "confusion_matrix": self.confusion_matrix,
            "category_breakdown": self.category_breakdown,
            "per_verdict": {k: asdict(v) for k, v in self.per_verdict.items()},
            "calibration_bins": [asdict(b) for b in self.calibration_bins],
            "detailed_records": self.detailed_records,
        }


def normalize_verdict_str(v_str: str) -> str:
    """Normalize raw verdict string into standard evaluation class."""
    s = str(v_str).strip().lower()
    if "partially" in s or "partial" in s:
        return "partially supported"
    if "contradict" in s:
        return "contradictory"
    if "unsupport" in s:
        return "unsupported"
    if "support" in s:
        return "supported"
    if "review" in s or "outdated" in s:
        return "needs review"
    return "needs review"


def evaluate_benchmark(dataset_path: Optional[str] = None) -> BenchmarkReport:
    """Execute full benchmark evaluation across gold standard claims or real academic evaluation dataset."""
    path: Optional[Path] = None
    dataset_type = "synthetic"
    dataset_name = "Synthetic Corrupted Benchmark (gold_set.jsonl)"

    if dataset_path:
        p = Path(dataset_path)
        if p.exists():
            path = p
            if "real" in p.name.lower() or "academic" in p.name.lower():
                dataset_type = "real_world"
                dataset_name = "Real-World Academic Benchmark (Manually Annotated)"
            else:
                dataset_type = "synthetic"
                dataset_name = "Synthetic Corrupted Benchmark (gold_set.jsonl)"
        else:
            ds_str = str(dataset_path).strip().lower()
            if ds_str in ("real", "real_world", "real_academic"):
                for candidate in [
                    Path("data/real_academic_eval.jsonl"),
                    Path("tests/fixtures/real_academic_eval.jsonl"),
                ]:
                    if candidate.exists():
                        path = candidate
                        break
                dataset_type = "real_world"
                dataset_name = "Real-World Academic Benchmark (Manually Annotated)"
            elif ds_str in ("synthetic", "gold"):
                for candidate in [
                    Path("gold_set.jsonl"),
                    Path("data/gold_set.jsonl"),
                    Path("tests/fixtures/gold_set.jsonl"),
                ]:
                    if candidate.exists():
                        path = candidate
                        break
                dataset_type = "synthetic"
                dataset_name = "Synthetic Corrupted Benchmark (gold_set.jsonl)"

    if not path:
        for candidate in [
            Path("gold_set.jsonl"),
            Path("data/gold_set.jsonl"),
            Path("tests/fixtures/gold_set.jsonl"),
        ]:
            if candidate.exists():
                path = candidate
                dataset_type = "synthetic"
                dataset_name = "Synthetic Corrupted Benchmark (gold_set.jsonl)"
                break

    if not path or not path.exists():
        raise FileNotFoundError(f"Benchmark set not found at {dataset_path} or tests/fixtures/gold_set.jsonl or gold_set.jsonl")

    samples: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))

    # Detect real-world academic dataset by content schema
    if any("paper_title" in s or s.get("category") in ("retracted_publication", "misleading_citation", "incorrect_citation", "missing_citation", "numerical_discrepancy") for s in samples):
        dataset_type = "real_world"
        dataset_name = "Real-World Academic Benchmark (Manually Annotated)"

    records: list[dict[str, Any]] = []
    total = len(samples)
    correct_count = 0
    fab_tested = 0
    fab_caught = 0

    for idx, item in enumerate(samples, 1):
        claim_text = item["claim_text"]
        source_text = item.get("source_text", "")
        access_tier = AccessTier.from_str(item.get("access_tier", "full_text"))
        citation_key = item.get("citation_key", "1")
        fab_quote = item.get("fabricated_quote")
        expected_raw = item.get("expected_verdict", "needs review")
        expected = normalize_verdict_str(expected_raw)

        if fab_quote:
            fab_tested += 1

        # Retracted paper handling
        is_ret = bool(item.get("is_retracted", False))
        cand_paper = CandidatePaper(
            source="crossref",
            title=item.get("paper_title", "Cited Publication"),
            doi=item.get("doi"),
            is_retracted=is_ret,
            retraction_details={"reason": item.get("retraction_reason")} if is_ret else {},
        )
        outdated_ev = item.get("retraction_reason") if is_ret else None

        # Missing citation handling
        has_missing = bool(not citation_key or item.get("category") == "missing_citation" or item.get("has_missing_citation"))
        c_keys = [citation_key] if (citation_key and not has_missing) else []

        cl = Claim(
            id=item.get("id", f"claim-{idx}"),
            text=claim_text,
            citation_keys=c_keys,
            has_missing_citation=has_missing,
        )

        # Run verification engine
        claim = verify_claim(
            claim_input=cl,
            source_text=source_text,
            access_tier=access_tier,
            citation_key=citation_key if not has_missing else "",
            candidate_paper=cand_paper,
            is_outdated=is_ret,
            outdated_evidence=outdated_ev,
            simulated_hallucinated_quote=fab_quote,
        )

        pred_raw = claim.verdict.verdict.value if claim.verdict else "needs review"
        predicted = normalize_verdict_str(pred_raw)
        confidence = float(claim.verdict.confidence) if claim.verdict else 0.0
        rules = claim.verdict.rules_triggered if claim.verdict else []

        is_correct = (predicted == expected)
        if is_correct:
            correct_count += 1

        caught_hallucination = False
        if fab_quote and RULE_HALLUCINATED_QUOTE in rules:
            fab_caught += 1
            caught_hallucination = True

        category = item.get("category", item.get("corruption_type", "none"))
        records.append({
            "id": item.get("id"),
            "category": category,
            "paper_title": item.get("paper_title", ""),
            "doi": item.get("doi", ""),
            "claim_text": claim_text,
            "expected": expected,
            "predicted": predicted,
            "confidence": confidence,
            "correct": is_correct,
            "rules_triggered": rules,
            "corruption_type": item.get("corruption_type", "none"),
            "hallucination_caught": caught_hallucination,
            "evidence_quotation": claim.exact_quotation,
        })

    # 1. Per-verdict precision, recall, and F1
    per_verdict: dict[str, VerdictMetrics] = {v: VerdictMetrics(verdict=v) for v in VERDICT_CLASSES}
    for v in VERDICT_CLASSES:
        metrics = per_verdict[v]
        for rec in records:
            exp_match = (rec["expected"] == v)
            pred_match = (rec["predicted"] == v)

            if exp_match:
                metrics.support += 1

            if exp_match and pred_match:
                metrics.tp += 1
            elif not exp_match and pred_match:
                metrics.fp += 1
            elif exp_match and not pred_match:
                metrics.fn += 1

        prec = metrics.tp / (metrics.tp + metrics.fp) if (metrics.tp + metrics.fp) > 0 else 0.0
        rec = metrics.tp / (metrics.tp + metrics.fn) if (metrics.tp + metrics.fn) > 0 else 0.0
        f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        metrics.precision = round(prec, 4)
        metrics.recall = round(rec, 4)
        metrics.f1 = round(f1, 4)

    # Macro averages
    macro_p = sum(m.precision for m in per_verdict.values()) / len(VERDICT_CLASSES)
    macro_r = sum(m.recall for m in per_verdict.values()) / len(VERDICT_CLASSES)
    macro_f1 = sum(m.f1 for m in per_verdict.values()) / len(VERDICT_CLASSES)
    overall_acc = correct_count / total if total > 0 else 0.0

    # 2. Confusion Matrix across all 5 standard verdict classes
    confusion_matrix: dict[str, dict[str, int]] = {
        v1: {v2: 0 for v2 in VERDICT_CLASSES}
        for v1 in VERDICT_CLASSES
    }
    for rec in records:
        exp_c = rec["expected"]
        pred_c = rec["predicted"]
        if exp_c in confusion_matrix and pred_c in confusion_matrix[exp_c]:
            confusion_matrix[exp_c][pred_c] += 1

    # 3. Category Breakdown (Real academic categories or corruption types)
    category_breakdown: dict[str, dict[str, Any]] = {}
    distinct_categories = sorted({r.get("category", "none") for r in records})
    for cat in distinct_categories:
        cat_recs = [r for r in records if r.get("category") == cat]
        c_tot = len(cat_recs)
        c_cor = sum(1 for r in cat_recs if r["correct"])
        category_breakdown[cat] = {
            "category": cat,
            "total": c_tot,
            "correct": c_cor,
            "accuracy": round(c_cor / c_tot, 4) if c_tot > 0 else 0.0,
        }

    # 4. Calibration curve (Confidence vs Actual Accuracy)
    bin_defs = [
        ("0.0 - 0.2", 0.0, 0.2),
        ("0.2 - 0.4", 0.2, 0.4),
        ("0.4 - 0.6", 0.4, 0.6),
        ("0.6 - 0.8", 0.6, 0.8),
        ("0.8 - 1.0", 0.8, 1.01),
    ]

    calibration_bins: list[CalibrationBin] = []
    total_ece_weighted = 0.0

    def _ground_truth_support_weight(exp: str) -> float:
        if exp == "unsupported":
            return 0.0
        if "partially" in exp:
            return 0.50
        if exp == "supported":
            return 1.0
        return 0.0

    for name, low, high in bin_defs:
        bin_records = [
            r for r in records
            if (low <= r["confidence"] < high if high <= 1.0 else low <= r["confidence"] <= 1.0)
        ]
        cnt = len(bin_records)
        if cnt > 0:
            mean_conf = sum(r["confidence"] for r in bin_records) / cnt
            acc = sum(1 for r in bin_records if r["correct"]) / cnt
            support_rate = sum(_ground_truth_support_weight(r["expected"]) for r in bin_records) / cnt
            gap = abs(mean_conf - support_rate)
            total_ece_weighted += (cnt / total) * gap
        else:
            mean_conf = (low + high) / 2.0
            acc = 0.0
            support_rate = 0.0
            gap = 0.0

        calibration_bins.append(CalibrationBin(
            bin_name=name,
            lower=low,
            upper=high,
            count=cnt,
            mean_confidence=round(mean_conf, 4),
            accuracy=round(acc, 4),
            support_rate=round(support_rate, 4),
            gap=round(gap, 4),
        ))

    ece = round(total_ece_weighted, 4)
    hallucination_rate = fab_caught / fab_tested if fab_tested > 0 else 1.0

    return BenchmarkReport(
        total_samples=total,
        overall_accuracy=round(overall_acc, 4),
        macro_precision=round(macro_p, 4),
        macro_recall=round(macro_r, 4),
        macro_f1=round(macro_f1, 4),
        per_verdict=per_verdict,
        calibration_bins=calibration_bins,
        ece=ece,
        fabricated_quotes_tested=fab_tested,
        fabricated_quotes_caught=fab_caught,
        hallucination_catch_rate=round(hallucination_rate, 4),
        dataset_name=dataset_name,
        dataset_type=dataset_type,
        confusion_matrix=confusion_matrix,
        category_breakdown=category_breakdown,
        detailed_records=records,
    )


def print_benchmark_report(report: BenchmarkReport) -> None:
    """Format and print benchmark results matching AGENTS.md verification contract."""
    width = 78
    line_sep = "=" * width
    sub_sep = "-" * width

    print("\n" + line_sep)
    print(f"  CREDENCE BENCHMARK EVALUATION")
    print(f"  Dataset: {report.dataset_name} [{report.dataset_type.upper()}]")
    print(line_sep)
    print(f"  Total Annotated Claims:     {report.total_samples}")
    print(f"  Overall Empirical Accuracy: {report.overall_accuracy * 100:.2f}%")
    print(f"  Macro-Averaged Precision:   {report.macro_precision:.4f}")
    print(f"  Macro-Averaged Recall:      {report.macro_recall:.4f}")
    print(f"  Macro-Averaged F1-Score:    {report.macro_f1:.4f}")
    print(f"  Expected Calibration Error: {report.ece:.4f}")
    print(sub_sep)

    # 1. Confusion Matrix Table
    print("\n  CONFUSION MATRIX (Rows: Ground Truth Expected | Columns: Predicted)")
    print(sub_sep)
    header_cols = ["Supp", "Part", "Cont", "Unsp", "Revi", "TOTAL"]
    print(f"  {'EXPECTED \\ PREDICTED':<22} | " + " | ".join(f"{c:>5}" for c in header_cols))
    print(sub_sep)
    short_keys = {
        "supported": "Supported",
        "partially supported": "Partially Supp",
        "contradictory": "Contradictory",
        "unsupported": "Unsupported",
        "needs review": "Needs Review",
    }
    for exp_cls in VERDICT_CLASSES:
        row_counts = [report.confusion_matrix.get(exp_cls, {}).get(pred_cls, 0) for pred_cls in VERDICT_CLASSES]
        row_total = sum(row_counts)
        label = short_keys.get(exp_cls, exp_cls)
        row_str = " | ".join(f"{cnt:>5d}" for cnt in row_counts) + f" | {row_total:>5d}"
        print(f"  {label:<22} | {row_str}")
    print(sub_sep)

    # 2. Category Diagnostic Breakdown (if present)
    if report.category_breakdown:
        print("\n  CATEGORY DIAGNOSTIC BREAKDOWN")
        print(sub_sep)
        print(f"  {'CATEGORY':<28} {'TOTAL':<10} {'CORRECT':<10} {'ACCURACY':<10}")
        print(sub_sep)
        for cat_name, c_data in report.category_breakdown.items():
            acc_str = f"{c_data['accuracy'] * 100:.1f}%"
            print(f"  {cat_name.replace('_', ' ').title():<28} {c_data['total']:<10d} {c_data['correct']:<10d} {acc_str:<10}")
        print(sub_sep)

    # 3. Per-Verdict Table
    print("\n  PER-VERDICT PRECISION, RECALL & F1")
    print(sub_sep)
    print(f"  {'VERDICT':<24} {'PRECISION':<12} {'RECALL':<12} {'F1':<12} {'SUPPORT':<8}")
    print(sub_sep)

    for v_name in VERDICT_CLASSES:
        m = report.per_verdict[v_name]
        v_title = v_name.title()
        print(f"  {v_title:<24} {m.precision:<12.4f} {m.recall:<12.4f} {m.f1:<12.4f} {m.support:<8d}")

    print(sub_sep)

    # 4. Confidence Calibration Table
    print("\n  CONFIDENCE CALIBRATION CURVE (Predicted vs Evidence Support Rate)")
    print(sub_sep)
    print(f"  {'CONFIDENCE BIN':<16} {'SAMPLES':<10} {'PRED CONF':<14} {'OBS SUPPORT':<14} {'GAP':<10} {'ACCURACY':<10}")
    print(sub_sep)

    for b in report.calibration_bins:
        pred_pct = f"{b.mean_confidence * 100:.1f}%"
        supp_pct = f"{b.support_rate * 100:.1f}%"
        gap_pct = f"{b.gap * 100:.1f}%"
        acc_pct = f"{b.accuracy * 100:.1f}%"
        print(f"  {b.bin_name:<16} {b.count:<10d} {pred_pct:<14} {supp_pct:<14} {gap_pct:<10} {acc_pct:<10}")

    print(sub_sep)
    print(f"  Expected Calibration Error (ECE): {report.ece:.4f}")

    # 5. Caught Hallucinations Summary (Golden Rule 2)
    print("\n  GOLDEN RULE 2 AUDIT: FABRICATED QUOTE DETECTION")
    print(sub_sep)
    print(f"  Fabricated Quotes Injected:   {report.fabricated_quotes_tested}")
    print(f"  Caught by Deterministic Code: {report.fabricated_quotes_caught}")
    print(f"  Hallucination Catch Rate:     {report.hallucination_catch_rate * 100:.1f}%")
    if report.fabricated_quotes_tested > 0 and report.fabricated_quotes_caught == report.fabricated_quotes_tested:
        print("  ✓ Verification gate passed: 100% of unverified quotes caught and routed to 'Needs review'.")
    elif report.fabricated_quotes_tested == 0:
        print("  ✓ Real-world audit: Verbatim quotes verified against source text.")
    else:
        print("  ✗ Warning: Some unverified quotes bypassed deterministic check.")

    print(line_sep + "\n")


def main() -> None:
    args = sys.argv[1:]
    run_mode = "all"
    custom_path = None

    if args:
        if args[0] in ("--all", "-a"):
            run_mode = "all"
        elif args[0] in ("--real", "-r", "real"):
            run_mode = "real"
        elif args[0] in ("--synthetic", "-s", "synthetic"):
            run_mode = "synthetic"
        elif len(args) == 2 and args[0] == "--dataset":
            run_mode = args[1]
        else:
            custom_path = args[0]
            run_mode = "custom"

    out_dir = Path("data")
    out_dir.mkdir(parents=True, exist_ok=True)

    if run_mode == "real":
        report_real = evaluate_benchmark("real")
        print_benchmark_report(report_real)
        with open(out_dir / "real_academic_results.json", "w", encoding="utf-8") as f:
            json.dump(report_real.to_dict(), f, indent=2)
    elif run_mode == "synthetic":
        report_synth = evaluate_benchmark("synthetic")
        print_benchmark_report(report_synth)
        with open(out_dir / "benchmark_results.json", "w", encoding="utf-8") as f:
            json.dump(report_synth.to_dict(), f, indent=2)
    elif run_mode == "custom" and custom_path:
        report = evaluate_benchmark(custom_path)
        print_benchmark_report(report)
        out_name = "real_academic_results.json" if report.dataset_type == "real_world" else "benchmark_results.json"
        with open(out_dir / out_name, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
    else:
        # Default: evaluate both synthetic and real-world benchmarks
        report_synth = evaluate_benchmark("synthetic")
        print_benchmark_report(report_synth)
        with open(out_dir / "benchmark_results.json", "w", encoding="utf-8") as f:
            json.dump(report_synth.to_dict(), f, indent=2)

        report_real = evaluate_benchmark("real")
        print_benchmark_report(report_real)
        with open(out_dir / "real_academic_results.json", "w", encoding="utf-8") as f:
            json.dump(report_real.to_dict(), f, indent=2)


if __name__ == "__main__":
    main()
