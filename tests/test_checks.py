"""Unit tests for pure-Python deterministic verification checks.

Validates:
- 30% vs 12.1% is a mismatch
- percent vs percentage-points is a unit mismatch
- a fabricated quote that does NOT exist in the source is rejected
- hedge stripping / overclaiming is rejected
- quote normalization across linebreaks, hyphens, and unicode quotes
"""

import pytest
from credence.verify.checks import (
    CheckResult,
    hedge_check,
    normalize_text,
    number_check,
    quote_check,
)


class TestQuoteCheck:
    """Tests for quote_check ensuring verbatim proof and rejection of hallucinations."""

    SOURCE_TEXT = """
    Background: Cardioprotective therapies require rigorous evaluation.
    Methods: In a double-blind, randomized controlled trial involving 1,450 patients,
    we evaluated the efficacy of Compound-X.
    Results: Patients receiving Compound-X demonstrated a 12.1% reduction in 30-day mortality
    compared with the placebo arm (p = 0.003). Adverse events were mild and treatment-
    associated toxicities occurred in fewer than 2% of participants.
    Conclusion: Our findings suggest that Compound-X may provide significant clinical benefit.
    """

    def test_verbatim_quote_accepted(self):
        """Verbatim snippet present in source text must pass."""
        quote = "Patients receiving Compound-X demonstrated a 12.1% reduction in 30-day mortality"
        result = quote_check(quote, self.SOURCE_TEXT)
        assert result.passed is True
        assert result == True
        assert bool(result) is True
        assert "exact_normalized" in result.details.get("match_type", "")

    def test_quote_with_linebreaks_and_hyphens_normalized(self):
        """Quotes split across lines or with dehyphenated words must match after normalization."""
        # 'treatment-\nassociated' in source vs dehyphenated/normalized quote
        quote = "treatment-associated toxicities occurred in fewer than 2% of participants."
        result = quote_check(quote, self.SOURCE_TEXT)
        assert result.passed is True
        assert result == True

    def test_quote_with_fancy_unicode_quotes(self):
        """Quotes enclosed in smart/curly quotes must be normalized and matched."""
        quote = '“we evaluated the efficacy of Compound-X.”'
        result = quote_check(quote, self.SOURCE_TEXT)
        assert result.passed is True
        assert result == True

    def test_fabricated_quote_rejected(self):
        """A fabricated quote that does NOT exist in the source must be rejected."""
        # Golden Rule 2: LLM hallucination / fabricated quote rejection
        fabricated_quote = "Patients receiving Compound-X demonstrated an unprecedented 95% survival advantage"
        result = quote_check(fabricated_quote, self.SOURCE_TEXT)
        assert result.passed is False
        assert result == False
        assert bool(result) is False
        assert "Fabricated quote" in result.reason
        assert result.details["match_type"] == "not_found"

    def test_subtly_altered_quote_rejected(self):
        """A quote with modified numerical value must be rejected as verbatim quote."""
        altered_quote = "Patients receiving Compound-X demonstrated a 30% reduction in 30-day mortality"
        result = quote_check(altered_quote, self.SOURCE_TEXT)
        assert result.passed is False
        assert result == False

    def test_empty_inputs_handled_safely(self):
        """Empty quotes or empty source texts must return failure without crashing."""
        assert quote_check("", self.SOURCE_TEXT).passed is False
        assert quote_check("valid quote", "").passed is False
        assert quote_check("   ", self.SOURCE_TEXT).passed is False


class TestNumberCheck:
    """Tests for number_check verifying numerical and unit precision."""

    def test_30_percent_vs_12_point_1_percent_mismatch(self):
        """30% vs 12.1% is a blatant numerical value mismatch."""
        claim = "Compound-X reduced 30-day mortality by 30%."
        quote = "Patients receiving Compound-X demonstrated a 12.1% reduction in 30-day mortality."
        result = number_check(claim, quote)
        assert result.passed is False
        assert result == False
        assert bool(result) is False
        assert "Numerical value mismatch" in result.reason
        assert any(
            m["type"] == "value_mismatch"
            for m in result.details.get("mismatches", [])
        )

    def test_percent_vs_percentage_points_mismatch(self):
        """percent vs percentage-points is a unit mismatch."""
        claim = "The overall remission rate increased by 5 percentage points."
        quote = "The overall remission rate increased by 5% in the intervention arm."
        result = number_check(claim, quote)
        assert result.passed is False
        assert result == False
        assert bool(result) is False
        assert "Unit mismatch" in result.reason
        assert any(
            m["type"] == "unit_mismatch"
            for m in result.details.get("mismatches", [])
        )

    def test_percentage_point_abbreviations_mismatch(self):
        """Abbreviated percentage points (pp) vs percent must also trigger unit mismatch."""
        claim = "There was a 3.5 pp increase in compliance."
        quote = "There was a 3.5% increase in compliance."
        result = number_check(claim, quote)
        assert result.passed is False
        assert "Unit mismatch" in result.reason

    def test_matching_numbers_and_units_accepted(self):
        """Exact matching numbers and units must pass."""
        claim = "Mortality was reduced by 12.1% in the treated cohort."
        quote = "Demonstrated a 12.1% reduction in 30-day mortality."
        result = number_check(claim, quote)
        assert result.passed is True
        assert result == True

    def test_claim_without_numbers_passes(self):
        """Qualitative claims without numbers do not produce numerical contradictions."""
        claim = "The drug significantly improved patient survival."
        quote = "Mortality decreased by 12.1% (p = 0.003)."
        result = number_check(claim, quote)
        assert result.passed is True

    def test_claim_numbers_missing_in_quote_fails(self):
        """When the claim asserts numbers not present anywhere in the quote, fail."""
        claim = "Mortality decreased by 12.1%."
        quote = "The drug exhibited favorable tolerability with no severe adverse effects."
        result = number_check(claim, quote)
        assert result.passed is False
        assert "claim asserts numbers" in result.reason


class TestHedgeCheck:
    """Tests for hedge_check detecting epistemic hedge-stripping and overclaiming."""

    def test_hedge_stripping_with_booster_rejected(self):
        """Hedged quote with a booster/definitive claim must be flagged as overclaiming."""
        claim = "This landmark study proves that Compound-X causes tumor eradication."
        quote = "Our preliminary findings suggest that Compound-X may be associated with reduced tumor volume."
        result = hedge_check(claim, quote)
        assert result.passed is False
        assert result == False
        assert bool(result) is False
        assert "Hedge mismatch" in result.reason
        assert "proves" in result.details["claim_boosters"]
        assert "suggest" in result.details["quote_hedges"] or "may" in result.details["quote_hedges"]

    def test_animal_model_preliminary_stripped_rejected(self):
        """Preliminary animal model scope stripped into definitive human claim must fail."""
        claim = "Compound-X definitely cures neurodegeneration."
        quote = "In mice, preliminary observations indicated that Compound-X could slow cognitive decline."
        result = hedge_check(claim, quote)
        assert result.passed is False
        assert "Hedge mismatch" in result.reason

    def test_calibrated_hedges_accepted(self):
        """When both claim and quote share consistent epistemic calibration, pass."""
        claim = "The therapy may offer potential benefits in early-stage disease."
        quote = "Our findings suggest that the therapy might provide clinical benefits."
        result = hedge_check(claim, quote)
        assert result.passed is True
        assert result == True

    def test_definitive_quote_with_conservative_claim_accepted(self):
        """When the quote is definitive and the claim is conservative, pass."""
        claim = "Compound-X was shown to reduce mortality."
        quote = "Clinical trial results proved that Compound-X eradicated bacterial load."
        result = hedge_check(claim, quote)
        assert result.passed is True
        assert result == True


class TestCheckResultBehavior:
    """Tests ensuring CheckResult conforms to pure Python truthiness and comparison."""

    def test_boolean_evaluation(self):
        passed_res = CheckResult(passed=True, reason="ok")
        failed_res = CheckResult(passed=False, reason="error")

        assert bool(passed_res) is True
        assert bool(failed_res) is False

        assert passed_res == True
        assert failed_res == False
        assert passed_res != False
        assert failed_res != True
