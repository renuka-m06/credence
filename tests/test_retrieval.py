"""Evaluation of reference parser, cache, sources, and matcher on a 20-reference test set.

Dataset:
- 5 Valid references
- 5 Wrong-year references
- 5 Fake-DOI references
- 5 Fake-title references
"""

import pytest
from credence.resolve.cache import CacheStore
from credence.resolve.matcher import CandidatePaper, score_candidate
from credence.resolve.reference import Reference, parse_reference
from credence.resolve.sources import UnifiedResolver


@pytest.fixture
def isolated_resolver(tmp_path):
    """Create an isolated CacheStore and UnifiedResolver for testing."""
    db_file = tmp_path / "test_cache.db"
    cache = CacheStore(db_path=db_file)
    resolver = UnifiedResolver(cache=cache)

    # Seed known candidate records into cache for deterministic testing
    known_papers = {
        "10.1109/cvpr.2016.90": {
            "title": "Deep Residual Learning for Image Recognition",
            "authors": ["He, Kaiming", "Zhang, Xiangyu", "Ren, Shaoqing", "Sun, Jian"],
            "year": 2016,
            "doi": "10.1109/cvpr.2016.90",
        },
        "10.1145/3065386": {
            "title": "Attention Is All You Need",
            "authors": ["Vaswani, Ashish", "Shazeer, Noam", "Parmar, Niki"],
            "year": 2017,
            "doi": "10.1145/3065386",
        },
        "10.5555/1953048.2078195": {
            "title": "Scikit-learn: Machine Learning in Python",
            "authors": ["Pedregosa, Fabian", "Varoquaux, Gael", "Gramfort, Alexandre"],
            "year": 2011,
            "doi": "10.5555/1953048.2078195",
        },
        "10.18653/v1/n19-1423": {
            "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
            "authors": ["Devlin, Jacob", "Chang, Ming-Wei", "Lee, Kenton"],
            "year": 2019,
            "doi": "10.18653/v1/n19-1423",
        },
        "10.48550/arxiv.1412.6980": {
            "title": "Adam: A Method for Stochastic Optimization",
            "authors": ["Kingma, Diederik", "Ba, Jimmy"],
            "year": 2014,
            "doi": "10.48550/arxiv.1412.6980",
        },
    }

    # Pre-populate Crossref cache
    for doi, meta in known_papers.items():
        crossref_payload = {
            "message": {
                "title": [meta["title"]],
                "DOI": meta["doi"],
                "issued": {"date-parts": [[meta["year"]]]},
                "author": [{"family": a.split(",")[0], "given": a.split(",")[1].strip() if "," in a else ""} for a in meta["authors"]],
            }
        }
        cache.set("crossref", f"works/{doi}", crossref_payload)

    # Pre-populate 404s for the 5 fake DOIs
    fake_dois = [
        "10.1000/182.fake.teleport.99999",
        "10.9999/fabricated.doi.cancer.2024",
        "10.5555/fake.entropy.1234",
        "10.1234/fake.alchemy.2023",
        "10.1111/fake.perpetual.9999",
    ]
    for fdoi in fake_dois:
        cache.set("crossref", f"works/{fdoi}", {}, http_status=404, ttl_seconds=86400)
        cache.set("openalex", f"works/https://doi.org/{fdoi}?mailto=researcher%40example.com", {}, http_status=404)
        cache.set("semanticscholar", f"paper/DOI:{fdoi}?fields=title%2Cauthors%2Cyear%2Cabstract%2CopenAccessPdf", {}, http_status=404)

    return resolver


# ---------------------------------------------------------------------------
# 20 Reference Benchmark Dataset
# ---------------------------------------------------------------------------

BENCHMARK_20_REFERENCES = [
    # --- 5 Valid References ---
    {
        "id": "val-1",
        "raw": "Vaswani A, Shazeer N, Parmar N. Attention Is All You Need. NeurIPS. 2017. https://doi.org/10.1145/3065386",
        "expected_class": "valid",
    },
    {
        "id": "val-2",
        "raw": "He K, Zhang X, Ren S, Sun J. Deep Residual Learning for Image Recognition. CVPR. 2016. https://doi.org/10.1109/cvpr.2016.90",
        "expected_class": "valid",
    },
    {
        "id": "val-3",
        "raw": "Devlin J, Chang MW, Lee K. BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. NAACL. 2019. https://doi.org/10.18653/v1/n19-1423",
        "expected_class": "valid",
    },
    {
        "id": "val-4",
        "raw": "Kingma D, Ba J. Adam: A Method for Stochastic Optimization. ICLR. 2014. https://doi.org/10.48550/arxiv.1412.6980",
        "expected_class": "valid",
    },
    {
        "id": "val-5",
        "raw": "Pedregosa F, Varoquaux G, Gramfort A. Scikit-learn: Machine Learning in Python. JMLR. 2011. https://doi.org/10.5555/1953048.2078195",
        "expected_class": "valid",
    },

    # --- 5 Wrong-Year References ---
    {
        "id": "wy-1",
        "raw": "Vaswani A, Shazeer N. Attention Is All You Need. NeurIPS. 1998. https://doi.org/10.1145/3065386",
        "expected_class": "wrong_year",
    },
    {
        "id": "wy-2",
        "raw": "He K, Zhang X, Ren S. Deep Residual Learning for Image Recognition. CVPR. 2004. https://doi.org/10.1109/cvpr.2016.90",
        "expected_class": "wrong_year",
    },
    {
        "id": "wy-3",
        "raw": "Devlin J, Chang MW. BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. 2005. https://doi.org/10.18653/v1/n19-1423",
        "expected_class": "wrong_year",
    },
    {
        "id": "wy-4",
        "raw": "Kingma D, Ba J. Adam: A Method for Stochastic Optimization. 1995. https://doi.org/10.48550/arxiv.1412.6980",
        "expected_class": "wrong_year",
    },
    {
        "id": "wy-5",
        "raw": "Pedregosa F, Varoquaux G. Scikit-learn: Machine Learning in Python. 1980. https://doi.org/10.5555/1953048.2078195",
        "expected_class": "wrong_year",
    },

    # --- 5 Fake-DOI References ---
    {
        "id": "fdoi-1",
        "raw": "Smith J, Walker T. Quantum teleportation of human consciousness. J Neurophys. 2021. https://doi.org/10.1000/182.fake.teleport.99999",
        "expected_class": "fake_doi",
    },
    {
        "id": "fdoi-2",
        "raw": "Doe A, Martin K. Eradication of oncogenic pathways in Homo sapiens. Lancet Oncol. 2024. https://doi.org/10.9999/fabricated.doi.cancer.2024",
        "expected_class": "fake_doi",
    },
    {
        "id": "fdoi-3",
        "raw": "Williams R. Reverse thermodynamics in cellular biology. Cell. 2022. https://doi.org/10.5555/fake.entropy.1234",
        "expected_class": "fake_doi",
    },
    {
        "id": "fdoi-4",
        "raw": "Johnson T. Direct synthesis of gold from seawater at room temperature. Nat Mater. 2023. https://doi.org/10.1234/fake.alchemy.2023",
        "expected_class": "fake_doi",
    },
    {
        "id": "fdoi-5",
        "raw": "Brown M. Perpetual energy extraction from atmospheric vacuum. Phys Rev. 2020. https://doi.org/10.1111/fake.perpetual.9999",
        "expected_class": "fake_doi",
    },

    # --- 5 Fake-Title References ---
    {
        "id": "ftit-1",
        "raw": "Vaswani A, Shazeer N. Complete Eradication of All Infectious Pathogens. 2017. https://doi.org/10.1145/3065386",
        "expected_class": "fake_title",
    },
    {
        "id": "ftit-2",
        "raw": "He K, Zhang X. Global Telepathic Synchronization of Neural Brainwaves. CVPR. 2016. https://doi.org/10.1109/cvpr.2016.90",
        "expected_class": "fake_title",
    },
    {
        "id": "ftit-3",
        "raw": "Devlin J, Chang MW. Perpetual Fusion Reactor Design for Domestic Kitchens. 2019. https://doi.org/10.18653/v1/n19-1423",
        "expected_class": "fake_title",
    },
    {
        "id": "ftit-4",
        "raw": "Kingma D, Ba J. Secret Molecular Formula for Eternal Cellular Immortality. 2014. https://doi.org/10.48550/arxiv.1412.6980",
        "expected_class": "fake_title",
    },
    {
        "id": "ftit-5",
        "raw": "Pedregosa F, Varoquaux G. Direct Interstellar Travel via Acoustic Resonances. JMLR. 2011. https://doi.org/10.5555/1953048.2078195",
        "expected_class": "fake_title",
    },
]


def test_20_reference_benchmark(isolated_resolver):
    """Run all 20 references through resolver and check classification accuracy."""
    correct_count = 0
    total = len(BENCHMARK_20_REFERENCES)
    results = []

    for item in BENCHMARK_20_REFERENCES:
        ref = parse_reference(item["raw"], key=item["id"])
        match_result = isolated_resolver.resolve(ref)

        is_correct = match_result.classification == item["expected_class"]
        if is_correct:
            correct_count += 1

        results.append({
            "id": item["id"],
            "expected": item["expected_class"],
            "actual": match_result.classification,
            "score": match_result.score,
            "discrepancies": match_result.discrepancies,
            "correct": is_correct,
        })

    # Print summary table for visibility
    print(f"\nBenchmark Accuracy: {correct_count}/{total} ({correct_count/total*100:.1f}%)")
    for r in results:
        status_sym = "[PASS]" if r["correct"] else "[FAIL]"
        print(f"  {status_sym} {r['id']:<8} Expected: {r['expected']:<12} Actual: {r['actual']:<12} Score: {r['score']:.2f}")

    assert correct_count == total, f"Expected 20/20 correct classifications, got {correct_count}/{total}"
