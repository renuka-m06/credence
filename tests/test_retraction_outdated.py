"""Unit and integration tests for Retraction and Outdated Research Paper Detection.

Covers:
1. Crossref publication status checking:
   - update-to (retraction, erratum, corrigendum, expression of concern)
   - relation (is-retracted-by, is-corrected-by, is-superseded-by, is-replaced-by)
   - Crossmark assertion tags
   - Title prefix flags (RETRACTED:, WITHDRAWN:)
2. OpenAlex publication status checking:
   - is_retracted boolean flag
   - work type and type_crossref
   - Title prefix flags
3. Retraction Watch database integration:
   - DOI lookup
   - Title fuzzy matching lookup
   - Retraction reason extraction (e.g., Data Fabrication, Unreliable Findings)
   - Retraction notice DOI, date, notes
   - Dynamic record addition
4. Erratum and correction detection:
   - Formal erratum / corrigendum detection
   - correction_check deterministic CheckResult
5. Superseded publication detection:
   - superseded_check deterministic CheckResult
   - Preprint to peer-reviewed publication replacement
   - Crossref is-superseded-by and is-replaced-by relations
6. End-to-end pipeline verification:
   - Retracted paper triggers POTENTIALLY_OUTDATED with grounded evidence
   - Superseded paper triggers POTENTIALLY_OUTDATED with grounded evidence
   - Active, unretracted paper maintains standard empirical verdict
"""


from credence.report.models import AccessTier, VerdictType
from credence.resolve.matcher import CandidatePaper
from credence.resolve.publication_status import (
    CorrectionRecord,
    PublicationStatus,
    PublicationStatusChecker,
    PublicationStatusReport,
    RetractionRecord,
    RetractionWatchStore,
    SupersededRecord,
    check_crossref_status,
    check_openalex_status,
    check_publication_status,
    retraction_watch_store,
)
from credence.resolve.sources import _parse_crossref_message, _parse_openalex_work
from credence.verify.checks import (
    correction_check,
    publication_status_check,
    retraction_check,
    superseded_check,
)
from credence.verify.pipeline import verify_claim
from credence.verify.verdict import (
    RULE_OUTDATED_CITATION,
    RULE_UNGROUNDED_OUTDATED_REJECTED,
    determine_verdict,
    validate_outdated_evidence,
)


# ===========================================================================
# 1. Crossref Publication Status Checking
# ===========================================================================

def test_crossref_update_to_retraction():
    """Verify Crossref update-to retraction notices are accurately extracted."""
    msg = {
        "title": ["Clinical evaluation of compound alpha"],
        "DOI": "10.1000/182",
        "update-to": [
            {
                "type": "retraction",
                "label": "Notice of Retraction",
                "DOI": "10.1000/182-retraction",
                "updated": {"date-parts": [[2023, 5, 20]]},
            }
        ],
    }
    ret, corr, sup = check_crossref_status(msg)
    assert ret is not None
    assert ret.is_retracted is True
    assert ret.source == "crossref"
    assert ret.retraction_doi == "10.1000/182-retraction"
    assert ret.retraction_date == "2023-05-20"
    assert corr is None
    assert sup is None


def test_crossref_update_to_correction_erratum():
    """Verify Crossref update-to erratum notices are accurately extracted."""
    msg = {
        "title": ["Metabolic responses in diabetes mellitus"],
        "DOI": "10.2337/dc20-0001",
        "update-to": [
            {
                "type": "erratum",
                "label": "Erratum: Table 2 patient demographics corrected",
                "DOI": "10.2337/dc20-erratum",
                "updated": {"date-parts": [[2021, 2, 10]]},
            }
        ],
    }
    ret, corr, sup = check_crossref_status(msg)
    assert ret is None
    assert corr is not None
    assert corr.is_corrected is True
    assert corr.source == "crossref"
    assert corr.correction_type == "erratum"
    assert corr.correction_doi == "10.2337/dc20-erratum"


def test_crossref_relation_is_superseded_by():
    """Verify Crossref relation is-superseded-by is accurately extracted."""
    msg = {
        "title": ["Preliminary guidelines for hypertension management"],
        "DOI": "10.1161/hyp.2015.001",
        "relation": {
            "is-superseded-by": [{"id": "10.1161/hyp.2020.999"}]
        },
    }
    ret, corr, sup = check_crossref_status(msg)
    assert sup is not None
    assert sup.is_superseded is True
    assert sup.superseded_by_doi == "10.1161/hyp.2020.999"
    assert "is-superseded-by" in sup.reason


def test_crossref_crossmark_assertions_and_title_flags():
    """Verify Crossmark assertions and title prefixes flag retractions."""
    # Assertion check
    msg_assertion = {
        "title": ["Therapeutic stem cell differentiation"],
        "DOI": "10.1038/nature0001",
        "assertion": [
            {"name": "retraction", "value": "Paper retracted following inquiry"}
        ],
    }
    ret1, _, _ = check_crossref_status(msg_assertion)
    assert ret1 is not None
    assert ret1.is_retracted is True

    # Title prefix check
    msg_title = {
        "title": ["RETRACTED: Cardiovascular outcomes in cohort study"],
        "DOI": "10.1001/jama.2019.001",
    }
    ret2, _, _ = check_crossref_status(msg_title)
    assert ret2 is not None
    assert ret2.is_retracted is True


# ===========================================================================
# 2. OpenAlex Publication Status Checking
# ===========================================================================

def test_openalex_is_retracted_and_types():
    """Verify OpenAlex is_retracted flag and work types are parsed."""
    # 1. is_retracted flag
    oa_data1 = {
        "id": "https://openalex.org/W12345",
        "title": "Clinical efficacy trial",
        "doi": "https://doi.org/10.1056/nejm202001",
        "is_retracted": True,
        "type": "article",
    }
    ret1, corr1, _ = check_openalex_status(oa_data1)
    assert ret1 is not None
    assert ret1.is_retracted is True
    assert ret1.source == "openalex"

    # 2. type = 'erratum'
    oa_data2 = {
        "id": "https://openalex.org/W67890",
        "title": "Erratum to: Biomarker sensitivity analysis",
        "doi": "https://doi.org/10.1016/j.biom.2021.01",
        "is_retracted": False,
        "type": "erratum",
    }
    _, corr2, _ = check_openalex_status(oa_data2)
    assert corr2 is not None
    assert corr2.is_corrected is True
    assert corr2.correction_type == "erratum"


# ===========================================================================
# 3. Retraction Watch Database Integration
# ===========================================================================

def test_retraction_watch_doi_lookup():
    """Retraction Watch lookup by DOI retrieves verified retraction reasons and notice."""
    # Lancet Surgisphere COVID-19 retraction
    surgisphere_doi = "10.1016/s0140-6736(20)31180-6"
    rw_rec = retraction_watch_store.lookup(doi=surgisphere_doi)

    assert rw_rec is not None
    assert rw_rec.is_retracted is True
    assert rw_rec.source == "retraction_watch"
    assert "Data fabrication" in rw_rec.retraction_reasons
    assert rw_rec.retraction_doi == "10.1016/S0140-6736(20)31324-6"
    assert rw_rec.retraction_date == "2020-06-05"


def test_retraction_watch_title_fuzzy_lookup():
    """Retraction Watch lookup matches retracted papers by title fuzzy similarity."""
    title = "Superconductivity in single-crystal C60"
    rw_rec = retraction_watch_store.lookup(title=title)

    assert rw_rec is not None
    assert rw_rec.is_retracted is True
    assert "Falsification of data" in rw_rec.retraction_reasons


def test_retraction_watch_custom_record_addition():
    """Verify adding new Retraction Watch records dynamically to the store."""
    custom_doi = "10.1099/custom.retracted.2026"
    custom_title = "Evaluation of synthetic biomaterial X-99"

    retraction_watch_store.add_record(
        original_doi=custom_doi,
        original_title=custom_title,
        retraction_doi="10.1099/custom.notice.2026",
        retraction_date="2026-01-15",
        retraction_reasons=["Plagiarism", "Unethical research conduct"],
        journal="Journal of Biomaterials",
        publisher="Academic Press",
        notes="Whistleblower confirmed copied methodologies",
    )

    found = retraction_watch_store.lookup(doi=custom_doi)
    assert found is not None
    assert found.is_retracted is True
    assert "Plagiarism" in found.retraction_reasons
    assert found.retraction_date == "2026-01-15"


# ===========================================================================
# 4. Deterministic Check Functions (retraction_check, correction_check, superseded_check)
# ===========================================================================

def test_retraction_check_with_retraction_watch_match():
    """retraction_check identifies retracted candidate via Retraction Watch."""
    cand = CandidatePaper(
        source="openalex",
        title="Cardiovascular Disease, Drug Therapy, and Mortality in Covid-19",
        doi="10.1056/nejmoa2007621",
    )

    check_res = retraction_check(cand)
    assert check_res.passed is False
    assert "retracted" in check_res.reason.lower()
    assert check_res.details["is_retracted"] is True
    assert "Unreliable data" in check_res.details["retraction_details"]["retraction_reasons"]


def test_correction_check_with_issued_erratum():
    """correction_check identifies papers with issued corrections."""
    cand = CandidatePaper(
        source="crossref",
        title="Phase II trial of oncology candidate Z",
        doi="10.1000/trial-z",
        is_corrected=True,
        correction_details={"correction_type": "corrigendum", "description": "Confidence intervals revised"},
    )

    check_res = correction_check(cand)
    assert check_res.passed is False
    assert "correction" in check_res.reason.lower() or "corrigendum" in check_res.reason.lower()
    assert check_res.details["is_corrected"] is True


def test_superseded_check_with_newer_version():
    """superseded_check identifies publications superseded by newer versions."""
    cand = CandidatePaper(
        source="crossref",
        title="2016 Guidelines for Management of Sepsis",
        doi="10.1001/sepsis.2016",
        is_superseded=True,
        superseded_details={
            "source": "crossref",
            "reason": "Superseded by 2021 International Guidelines for Management of Sepsis",
            "superseded_by_doi": "10.1001/sepsis.2021",
        },
    )

    check_res = superseded_check(cand)
    assert check_res.passed is False
    assert "superseded" in check_res.reason.lower()
    assert check_res.details["is_superseded"] is True


def test_superseded_check_preprint_to_peer_reviewed_link():
    """Preprint candidate with referenced journal publication is flagged as superseded."""
    cand_preprint = CandidatePaper(
        source="arxiv",
        title="Transformer-based claim verification architecture",
        doi="10.48550/arxiv.2201.0001",
        publication_type="preprint",
        raw_payload={"journal_doi": "10.1162/tacl_a_00450"},
    )

    report = check_publication_status(cand_preprint)
    assert report.is_superseded is True
    assert report.status == PublicationStatus.SUPERSEDED

    check_res = superseded_check(cand_preprint)
    assert check_res.passed is False
    assert "superseded" in check_res.reason.lower()


def test_active_paper_passes_all_checks():
    """Legitimate active paper with no notices passes all status checks."""
    cand_active = CandidatePaper(
        source="crossref",
        title="Double-blind randomized trial of Compound-B in heart failure",
        doi="10.1056/nejmoa9999999",
        year=2024,
    )

    ret_res = retraction_check(cand_active)
    corr_res = correction_check(cand_active)
    sup_res = superseded_check(cand_active)
    pub_res = publication_status_check(cand_active)

    assert ret_res.passed is True
    assert corr_res.passed is True
    assert sup_res.passed is True
    assert pub_res.passed is True
    assert pub_res.details["publication_status"] == "active"


# ===========================================================================
# 5. Pipeline End-to-End Verification with Publication Status
# ===========================================================================

def test_pipeline_claim_backed_by_retracted_paper():
    """Claim citing a retracted paper is routed to 'potentially outdated' with full evidence."""
    cand_retracted = CandidatePaper(
        source="crossref",
        title="Hydroxychloroquine or chloroquine with or without a macrolide for treatment of COVID-19",
        doi="10.1016/s0140-6736(20)31180-6",
    )

    claim = verify_claim(
        claim_input="Hydroxychloroquine decreased hospital mortality in COVID-19 patients [1]",
        source_text="Treatment with hydroxychloroquine was associated with a 20% reduction in in-hospital mortality.",
        candidate_paper=cand_retracted,
    )

    assert claim.verdict is not None
    assert claim.verdict.verdict == VerdictType.POTENTIALLY_OUTDATED
    assert RULE_OUTDATED_CITATION in claim.verdict.rules_triggered
    assert "retraction" in claim.verdict.explanation.lower()
    assert "data fabrication" in claim.verdict.explanation.lower() or "retraction notice" in claim.verdict.explanation.lower()


def test_pipeline_claim_backed_by_superseded_paper():
    """Claim citing a superseded paper is routed to 'potentially outdated' with evidence."""
    cand_superseded = CandidatePaper(
        source="crossref",
        title="Early Pilot Cohort Study of Compound-Q",
        doi="10.1000/pilot-q",
        is_superseded=True,
        superseded_details={
            "reason": "Superseded by 2024 Phase III Multi-Center Randomized Trial showing no efficacy",
            "superseded_by_doi": "10.1000/phase3-q",
        },
    )

    claim = verify_claim(
        claim_input="Compound-Q demonstrated early efficacy in pilot cohort [1]",
        source_text="Pilot evaluation of Compound-Q demonstrated efficacy in 30 patients.",
        candidate_paper=cand_superseded,
    )

    assert claim.verdict is not None
    assert claim.verdict.verdict == VerdictType.POTENTIALLY_OUTDATED
    assert RULE_OUTDATED_CITATION in claim.verdict.rules_triggered
    assert "supersed" in claim.verdict.explanation.lower() or "contradicting study" in claim.verdict.explanation.lower()
