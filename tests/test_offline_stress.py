"""Stress test: 30-claim document verification entirely from cache with ZERO live API calls.

Requirements:
- Harden every HTTP call: timeout, retry with backoff, cache-first via resolve/cache.py,
  graceful degradation to abstract-only / inaccessible tiers.
- Run the full pipeline on a 30-claim document entirely from cache with ZERO live API calls.
- Gate: the offline run completes and produces a valid Report.
"""

import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from credence.report.models import AccessTier, Claim, Report, VerdictType
from credence.resolve.cache import CacheStore
from credence.resolve.matcher import CandidatePaper
from credence.resolve.reference import Reference
from credence.resolve.sources import CrossrefClient, UnifiedResolver
from credence.verify.llm import GeminiClient
from credence.verify.pipeline import build_report, verify_claim


# 30 Diverse Scientific Claims across 6 Fields
STRESS_30_CLAIMS = [
    # 1-5: Oncology & Pharmacology
    {
        "id": "claim-01",
        "text": "Pembrolizumab monotherapy demonstrated a 39.3% overall survival rate at 5 years in advanced NSCLC [1]",
        "citation_key": "1",
        "doi": "10.1001/jamaoncol.2019.3241",
        "title": "Five-Year Overall Survival for Patients With Advanced Non-Small-Cell Lung Cancer Treated With Pembrolizumab",
        "tier": "full_text",
        "source_text": "In patients with advanced NSCLC, pembrolizumab monotherapy demonstrated a 39.3% overall survival rate at 5 years among treatment-naive individuals.",
    },
    {
        "id": "claim-02",
        "text": "Sotorasib achieved a 37.1% objective response rate in KRAS p.G12C mutated solid tumors [2]",
        "citation_key": "2",
        "doi": "10.1056/nejmoa2103695",
        "title": "Kras G12C Inhibition with Sotorasib in Advanced Solid Tumors",
        "tier": "full_text",
        "source_text": "Sotorasib achieved a 37.1% objective response rate in patients with KRAS p.G12C mutant colorectal and lung tumors.",
    },
    {
        "id": "claim-03",
        "text": "Olaparib maintenance therapy reduced the risk of disease progression by 70% in BRCA-mutated ovarian cancer [3]",
        "citation_key": "3",
        "doi": "10.1056/nejmoa1810858",
        "title": "Maintenance Olaparib in Patients with Newly Diagnosed Advanced Ovarian Cancer",
        "tier": "full_text",
        "source_text": "Maintenance therapy with olaparib reduced the risk of disease progression or death by 70% in patients with BRCA-mutated ovarian cancer.",
    },
    {
        "id": "claim-04",
        "text": "Trastuzumab deruxtecan resulted in a 75.8% 12-month progression-free survival in HER2-positive breast cancer [4]",
        "citation_key": "4",
        "doi": "10.1056/nejmoa2115022",
        "title": "Trastuzumab Deruxtecan versus Trastuzumab Emtansine for HER2-Positive Metastatic Breast Cancer",
        "tier": "abstract_only",
        "source_text": "Abstract: Patients receiving trastuzumab deruxtecan exhibited a 75.8% 12-month progression-free survival compared with 34.1% in control arm.",
    },
    {
        "id": "claim-05",
        "text": "CAR-T cell therapy axicabtagene ciloleucel induced complete response in 54% of refractory large B-cell lymphoma [5]",
        "citation_key": "5",
        "doi": "10.1056/nejmoa1707447",
        "title": "Long-Term Safety and Activity of Axicabtagene Ciloleucel in Refractory Large B-Cell Lymphoma",
        "tier": "abstract_only",
        "source_text": "Abstract: Axicabtagene ciloleucel induced a complete response rate of 54% in patients with refractory large B-cell lymphoma.",
    },

    # 6-10: Cardiology & Vascular Medicine
    {
        "id": "claim-06",
        "text": "Dapagliflozin reduced the risk of cardiovascular death or worsening heart failure by 26% [6]",
        "citation_key": "6",
        "doi": "10.1056/nejmoa1911303",
        "title": "Dapagliflozin in Patients with Heart Failure and Reduced Ejection Fraction",
        "tier": "full_text",
        "source_text": "Dapagliflozin reduced the risk of cardiovascular death or worsening heart failure by 26% compared with placebo in heart failure.",
    },
    {
        "id": "claim-07",
        "text": "Evolocumab added to statin therapy lowered LDL cholesterol by 59% in established cardiovascular disease [7]",
        "citation_key": "7",
        "doi": "10.1056/nejmoa1701188",
        "title": "Evolocumab and Clinical Outcomes in Patients with Cardiovascular Disease",
        "tier": "full_text",
        "source_text": "Evolocumab lowered LDL cholesterol levels by 59% relative to placebo in patients receiving statin therapy.",
    },
    {
        "id": "claim-08",
        "text": "Catheter ablation lowered all-cause mortality to 13.4% compared to 25.0% for medical therapy in heart failure [8]",
        "citation_key": "8",
        "doi": "10.1056/nejmoa1707859",
        "title": "Catheter Ablation for Atrial Fibrillation with Heart Failure",
        "tier": "full_text",
        "source_text": "All-cause mortality was 13.4% in the catheter ablation group versus 25.0% in the medical therapy group.",
    },
    {
        "id": "claim-09",
        "text": "Sacubitril-valsartan decreased cardiovascular death by 20% compared with enalapril [9]",
        "citation_key": "9",
        "doi": "10.1056/nejmoa1409077",
        "title": "Angiotensin-Neprilysin Inhibition versus Enalapril in Heart Failure",
        "tier": "abstract_only",
        "source_text": "Abstract: Death from cardiovascular causes was reduced by 20% in the sacubitril-valsartan group compared with the enalapril group.",
    },
    {
        "id": "claim-10",
        "text": "Intensive blood pressure treatment reduced major cardiovascular events by 25% [10]",
        "citation_key": "10",
        "doi": "10.1056/nejmoa1511939",
        "title": "A Randomized Trial of Intensive versus Standard Blood-Pressure Control",
        "tier": "metadata_only",
        "source_text": "A Randomized Trial of Intensive versus Standard Blood-Pressure Control. N Engl J Med 2015.",
    },

    # 11-15: Neuroscience & Psychiatry
    {
        "id": "claim-11",
        "text": "Lecanemab reduced clinical decline on the CDR-SB by 27% at 18 months in early Alzheimer's disease [11]",
        "citation_key": "11",
        "doi": "10.1056/nejmoa2212948",
        "title": "Lecanemab in Early Alzheimer's Disease",
        "tier": "full_text",
        "source_text": "Lecanemab reduced clinical decline on the CDR-SB scale by 27% at 18 months relative to placebo in early Alzheimer's disease.",
    },
    {
        "id": "claim-12",
        "text": "Intravenous ketamine produced rapid antidepressant response in 71% of treatment-resistant depression patients [12]",
        "citation_key": "12",
        "doi": "10.1001/archpsyc.63.8.856",
        "title": "A Randomized Trial of an N-methyl-D-aspartate Antagonist in Treatment-Resistant Major Depression",
        "tier": "full_text",
        "source_text": "Intravenous ketamine produced rapid antidepressant response in 71% of treatment-resistant major depression patients at 24 hours.",
    },
    {
        "id": "claim-13",
        "text": "Deep brain stimulation of the subthalamic nucleus improved motor scores by 41% in Parkinson's disease [13]",
        "citation_key": "13",
        "doi": "10.1056/nejmoa060281",
        "title": "A Randomized Trial of Deep-Brain Stimulation for Parkinson's Disease",
        "tier": "abstract_only",
        "source_text": "Abstract: Deep brain stimulation of the subthalamic nucleus improved UPDRS motor scores by 41% compared with baseline medical therapy.",
    },
    {
        "id": "claim-14",
        "text": "Psilocybin-assisted psychotherapy produced a 67% response rate in treatment-resistant depression [14]",
        "citation_key": "14",
        "doi": "10.1056/nejmoa2032994",
        "title": "Trial of Psilocybin versus Escitalopram for Depression",
        "tier": "metadata_only",
        "source_text": "Trial of Psilocybin versus Escitalopram for Depression. N Engl J Med 2021.",
    },
    {
        "id": "claim-15",
        "text": "Subthalamic neurostimulation decreased medication requirements by 50% in dystonia cohorts [15]",
        "citation_key": "15",
        "doi": "10.1016/s1474-4422(06)70544-7",
        "title": "Bilateral deep-brain stimulation in primary generalised or segmental dystonia",
        "tier": "inaccessible",
        "source_text": "",  # Unreachable source
    },

    # 16-20: Infectious Disease & Virology
    {
        "id": "claim-16",
        "text": "BNT162b2 mRNA vaccine demonstrated 95% efficacy against COVID-19 in participants without prior infection [16]",
        "citation_key": "16",
        "doi": "10.1056/nejmoa2034577",
        "title": "Safety and Efficacy of the BNT162b2 mRNA Covid-19 Vaccine",
        "tier": "full_text",
        "source_text": "A two-dose regimen of BNT162b2 conferred 95% protection against Covid-19 in persons 16 years of age or older.",
    },
    {
        "id": "claim-17",
        "text": "Remdesivir shortened median recovery time to 10 days compared to 15 days for placebo [17]",
        "citation_key": "17",
        "doi": "10.1056/nejmoa2007764",
        "title": "Remdesivir for the Treatment of Covid-19 — Final Report",
        "tier": "full_text",
        "source_text": "Patients in the remdesivir group had a median recovery time of 10 days, as compared with 15 days in the placebo group.",
    },
    {
        "id": "claim-18",
        "text": "Nirmatrelvir plus ritonavir resulted in an 89% reduction in Covid-19-related hospitalization or death [18]",
        "citation_key": "18",
        "doi": "10.1056/nejmoa2118542",
        "title": "Oral Nirmatrelvir for High-Risk, Nonhospitalized Adults with Covid-19",
        "tier": "full_text",
        "source_text": "Treatment with nirmatrelvir plus ritonavir resulted in an 89% reduction in Covid-19-related hospitalization or death by day 28.",
    },
    {
        "id": "claim-19",
        "text": "Dolutegravir-based therapy maintained viral suppression in 92% of treatment-naive HIV-1 infected individuals [19]",
        "citation_key": "19",
        "doi": "10.1016/s0140-6736(18)30980-3",
        "title": "Dolutegravir plus lamivudine for initial treatment of HIV-1 infection (GEMINI-1 and GEMINI-2)",
        "tier": "abstract_only",
        "source_text": "Abstract: Dolutegravir plus lamivudine maintained plasma HIV-1 RNA <50 copies per mL in 92% of participants at 48 weeks.",
    },
    {
        "id": "claim-20",
        "text": "Convalescent plasma reduced mortality by 80% across all pediatric respiratory viral infections [20]",
        "citation_key": "20",
        "doi": "10.1056/nejmoa2033700",
        "title": "Early High-Titer Plasma Therapy in Older Adults with Mild Covid-19",
        "tier": "inaccessible",
        "source_text": "",  # Unreachable source
    },

    # 21-25: Environmental & Climate Science
    {
        "id": "claim-21",
        "text": "September Arctic sea ice extent declined at a rate of 12.8% per decade from 1979 to 2018 [21]",
        "citation_key": "21",
        "doi": "10.1088/1748-9326/ab2802",
        "title": "Recent decline in Arctic sea ice volume and extent",
        "tier": "full_text",
        "source_text": "Observed September Arctic sea ice extent has declined at an estimated rate of 12.8% per decade over the 1979-2018 satellite record.",
    },
    {
        "id": "claim-22",
        "text": "Global surface temperature increased by 1.09°C from 1850-1900 to 2011-2020 [22]",
        "citation_key": "22",
        "doi": "10.1017/9781009157896.001",
        "title": "IPCC Sixth Assessment Report: The Physical Science Basis",
        "tier": "full_text",
        "source_text": "Global surface temperature was 1.09°C higher in 2011-2020 than in 1850-1900, with larger increases over land than over ocean.",
    },
    {
        "id": "claim-23",
        "text": "Ocean surface pH declined by 0.1 units since the beginning of the industrial era [23]",
        "citation_key": "23",
        "doi": "10.1038/nature04095",
        "title": "Anthropogenic ocean acidification over the twenty-first century and its impact on calcifying organisms",
        "tier": "abstract_only",
        "source_text": "Abstract: Surface ocean pH has declined by approximately 0.1 units since 1750, representing a 30% increase in hydrogen ion concentration.",
    },
    {
        "id": "claim-24",
        "text": "Amazon forest carbon sink capacity declined by 30% over the past two decades [24]",
        "citation_key": "24",
        "doi": "10.1038/nature14283",
        "title": "Long-term decline of the Amazon carbon sink",
        "tier": "metadata_only",
        "source_text": "Long-term decline of the Amazon carbon sink. Nature 2015.",
    },
    {
        "id": "claim-25",
        "text": "Atmospheric methane emissions from permafrost thaw exceed total fossil fuel emissions [25]",
        "citation_key": "25",
        "doi": "10.1038/s41558-021-01038-6",
        "title": "Permafrost carbon feedbacks in the climate system",
        "tier": "inaccessible",
        "source_text": "",  # Unreachable source
    },

    # 26-30: Artificial Intelligence & Machine Learning
    {
        "id": "claim-26",
        "text": "The Transformer architecture achieved a BLEU score of 28.4 on the WMT 2014 English-to-German task [26]",
        "citation_key": "26",
        "doi": "10.1145/3065386",
        "title": "Attention Is All You Need",
        "tier": "full_text",
        "source_text": "On the WMT 2014 English-to-German translation task, the big transformer model achieved a BLEU score of 28.4, outperforming existing ensembles.",
    },
    {
        "id": "claim-27",
        "text": "ResNet-152 achieved a 4.49% top-5 error rate on the ImageNet test set [27]",
        "citation_key": "27",
        "doi": "10.1109/cvpr.2016.90",
        "title": "Deep Residual Learning for Image Recognition",
        "tier": "full_text",
        "source_text": "Our 152-layer residual network achieves a 4.49% top-5 error rate on the ImageNet test set, winning the 1st place in ILSVRC 2015.",
    },
    {
        "id": "claim-28",
        "text": "BERT achieved 80.5% accuracy on the Multi-Genre Natural Language Inference dataset [28]",
        "citation_key": "28",
        "doi": "10.18653/v1/n19-1423",
        "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        "tier": "full_text",
        "source_text": "BERT achieved a state-of-the-art accuracy of 80.5% on the MNLI matched benchmark evaluation.",
    },
    {
        "id": "claim-29",
        "text": "Adam optimizer demonstrated faster empirical convergence than SGD across standard deep networks [29]",
        "citation_key": "29",
        "doi": "10.48550/arxiv.1412.6980",
        "title": "Adam: A Method for Stochastic Optimization",
        "tier": "abstract_only",
        "source_text": "Abstract: Empirical results demonstrate that Adam converges faster than stochastic gradient descent with momentum on complex deep learning architectures.",
    },
    {
        "id": "claim-30",
        "text": "Scikit-learn provides an efficient, unified Python interface for machine learning [30]",
        "citation_key": "30",
        "doi": "10.5555/1953048.2078195",
        "title": "Scikit-learn: Machine Learning in Python",
        "tier": "metadata_only",
        "source_text": "Scikit-learn: Machine Learning in Python. JMLR 2011.",
    },
]


def test_30_claim_document_stress_run_from_cache(tmp_path, monkeypatch):
    """Stress test: Run complete verification pipeline on 30 claims with ZERO live API calls."""
    # 1. Initialize isolated cache database for testing
    cache_db_path = tmp_path / "offline_stress.db"
    cache = CacheStore(db_path=cache_db_path)

    # 2. Spy on httpx to strictly guarantee ZERO live HTTP requests
    live_http_calls: list[str] = []

    def mock_httpx_send(*args, **kwargs):
        req_url = str(args[1].url) if len(args) > 1 and hasattr(args[1], "url") else str(args)
        live_http_calls.append(req_url)
        raise RuntimeError(f"Forbidden live HTTP call during offline run: {req_url}")

    monkeypatch.setattr(httpx.Client, "send", mock_httpx_send)

    # 3. Seed cache for all 30 references across tiers
    for item in STRESS_30_CLAIMS:
        doi = item["doi"]
        tier_str = item["tier"]

        if tier_str == "inaccessible":
            # Simulate negative/unreachable cache
            cache.set(
                source="crossref",
                key=f"works/{doi}",
                payload={},
                http_status=404,
                ttl_seconds=86400,
            )
            continue

        oa_url = f"https://example.org/pdf/{doi}.pdf" if tier_str == "full_text" else None
        abstract_text = item["source_text"] if tier_str in ("abstract_only", "full_text") else None

        msg_payload = {
            "title": [item["title"]],
            "DOI": doi,
            "issued": {"date-parts": [[2021]]},
            "author": [{"family": "Author", "given": "Test"}],
            "container-title": ["Journal of Testing"],
            "abstract": abstract_text,
            "link": [{"URL": oa_url}] if oa_url else [],
        }

        # Cache in crossref store
        cache.set(
            source="crossref",
            key=f"works/{doi}",
            payload={"message": msg_payload},
            http_status=200,
        )

    # 4. Instantiate offline resolver and LLM client
    resolver = UnifiedResolver(cache=cache, offline_mode=True)
    llm = GeminiClient(cache=cache, offline_mode=True)

    # 5. Execute complete verification pipeline across all 30 claims
    start_time = time.time()
    verified_claims: list[Claim] = []

    for item in STRESS_30_CLAIMS:
        # Resolve reference from cache
        ref = Reference(
            raw_text=f"{item['title']}. doi:{item['doi']}",
            doi=item["doi"],
            title=item["title"],
            key=item["citation_key"],
        )
        match_result = resolver.resolve(ref)
        cand = match_result.candidate

        # Determine effective access tier
        if item["tier"] == "full_text":
            tier = AccessTier.FULL_TEXT
        elif item["tier"] == "abstract_only":
            tier = AccessTier.ABSTRACT_ONLY
        elif item["tier"] == "metadata_only":
            tier = AccessTier.METADATA_ONLY
        else:
            tier = AccessTier.INACCESSIBLE

        # Verify claim
        verified = verify_claim(
            claim_input=item["text"],
            source_text=item["source_text"],
            access_tier=tier,
            citation_key=item["citation_key"],
            candidate_paper=cand,
            llm_client=llm,
        )
        verified.id = item["id"]
        verified_claims.append(verified)

    elapsed = time.time() - start_time

    # 6. Build final report
    report = build_report(
        document_name="stress_test_manuscript_30_claims.pdf",
        claims=verified_claims,
    )

    # =======================================================================
    # Validation Gate Assertions
    # =======================================================================

    # Gate 1: ZERO live HTTP calls initiated
    assert len(live_http_calls) == 0, f"Expected 0 live HTTP calls, but detected: {live_http_calls}"

    # Gate 2: Produces a valid, non-null Report dataclass
    assert isinstance(report, Report)
    assert report.document_name == "stress_test_manuscript_30_claims.pdf"
    assert len(report.claims) == 30

    # Gate 3: Fast execution (30 claims processed in < 5 seconds)
    print(f"\n[STRESS TEST] Successfully verified 30 claims in {elapsed:.2f}s with 0 live HTTP calls.")
    assert elapsed < 5.0, f"Expected execution under 5.0s, took {elapsed:.2f}s"

    # Gate 4: Every claim has computed verdict and confidence
    for c in report.claims:
        assert c.verdict is not None
        assert isinstance(c.verdict.verdict, VerdictType)
        assert 0.0 <= c.verdict.confidence <= 1.0
        assert len(c.slots) >= 1
        assert len(c.slot_results) >= 1

    # Gate 5: Confidence caps strictly respected across access tiers
    for idx, c in enumerate(report.claims):
        expected_tier = STRESS_30_CLAIMS[idx]["tier"]
        conf = c.verdict.confidence

        if expected_tier == "full_text":
            assert conf <= AccessTier.FULL_TEXT.confidence_cap
        elif expected_tier == "abstract_only":
            assert conf <= AccessTier.ABSTRACT_ONLY.confidence_cap  # Cap 0.60
        elif expected_tier == "metadata_only":
            assert conf <= AccessTier.METADATA_ONLY.confidence_cap  # Cap 0.20
        elif expected_tier == "inaccessible":
            assert conf == 0.0  # Cap 0.00
            assert c.verdict.verdict == VerdictType.NEEDS_REVIEW

    # Gate 6: Summary counters sum exactly to 30
    summary = report.summary
    assert summary["total_claims"] == 30
    verdict_sum = (
        summary["supported"]
        + summary["partially_supported"]
        + summary["unsupported"]
        + summary["contradictory"]
        + summary["needs_review"]
    )
    assert verdict_sum == 30
    assert summary["human_review_required"] is True

    # Gate 7: Search ledger recorded all queries transparently
    ledger_logs = cache.get_search_logs()
    assert len(ledger_logs) >= 30
    for log in ledger_logs:
        assert log["status"] in ("hit", "cached", "offline_miss", "not_found")
