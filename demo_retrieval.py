"""Standalone evaluation script for Retrieval + Matching on the 20-reference benchmark set."""

from pathlib import Path
from credence.resolve.cache import CacheStore
from credence.resolve.reference import parse_reference
from credence.resolve.sources import UnifiedResolver

BENCHMARK_20_REFERENCES = [
    # 5 Valid
    {
        "cat": "Valid",
        "id": "val-1",
        "raw": "Vaswani A, Shazeer N, Parmar N. Attention Is All You Need. NeurIPS. 2017. https://doi.org/10.1145/3065386",
        "expected": "valid",
    },
    {
        "cat": "Valid",
        "id": "val-2",
        "raw": "He K, Zhang X, Ren S, Sun J. Deep Residual Learning for Image Recognition. CVPR. 2016. https://doi.org/10.1109/cvpr.2016.90",
        "expected": "valid",
    },
    {
        "cat": "Valid",
        "id": "val-3",
        "raw": "Devlin J, Chang MW, Lee K. BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. NAACL. 2019. https://doi.org/10.18653/v1/n19-1423",
        "expected": "valid",
    },
    {
        "cat": "Valid",
        "id": "val-4",
        "raw": "Kingma D, Ba J. Adam: A Method for Stochastic Optimization. ICLR. 2014. https://doi.org/10.48550/arxiv.1412.6980",
        "expected": "valid",
    },
    {
        "cat": "Valid",
        "id": "val-5",
        "raw": "Pedregosa F, Varoquaux G, Gramfort A. Scikit-learn: Machine Learning in Python. JMLR. 2011. https://doi.org/10.5555/1953048.2078195",
        "expected": "valid",
    },

    # 5 Wrong-Year
    {
        "cat": "Wrong-Year",
        "id": "wy-1",
        "raw": "Vaswani A, Shazeer N. Attention Is All You Need. NeurIPS. 1998. https://doi.org/10.1145/3065386",
        "expected": "wrong_year",
    },
    {
        "cat": "Wrong-Year",
        "id": "wy-2",
        "raw": "He K, Zhang X, Ren S. Deep Residual Learning for Image Recognition. CVPR. 2004. https://doi.org/10.1109/cvpr.2016.90",
        "expected": "wrong_year",
    },
    {
        "cat": "Wrong-Year",
        "id": "wy-3",
        "raw": "Devlin J, Chang MW. BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. 2005. https://doi.org/10.18653/v1/n19-1423",
        "expected": "wrong_year",
    },
    {
        "cat": "Wrong-Year",
        "id": "wy-4",
        "raw": "Kingma D, Ba J. Adam: A Method for Stochastic Optimization. 1995. https://doi.org/10.48550/arxiv.1412.6980",
        "expected": "wrong_year",
    },
    {
        "cat": "Wrong-Year",
        "id": "wy-5",
        "raw": "Pedregosa F, Varoquaux G. Scikit-learn: Machine Learning in Python. 1980. https://doi.org/10.5555/1953048.2078195",
        "expected": "wrong_year",
    },

    # 5 Fake-DOI
    {
        "cat": "Fake-DOI",
        "id": "fdoi-1",
        "raw": "Smith J, Walker T. Quantum teleportation of human consciousness. J Neurophys. 2021. https://doi.org/10.1000/182.fake.teleport.99999",
        "expected": "fake_doi",
    },
    {
        "cat": "Fake-DOI",
        "id": "fdoi-2",
        "raw": "Doe A, Martin K. Eradication of oncogenic pathways in Homo sapiens. Lancet Oncol. 2024. https://doi.org/10.9999/fabricated.doi.cancer.2024",
        "expected": "fake_doi",
    },
    {
        "cat": "Fake-DOI",
        "id": "fdoi-3",
        "raw": "Williams R. Reverse thermodynamics in cellular biology. Cell. 2022. https://doi.org/10.5555/fake.entropy.1234",
        "expected": "fake_doi",
    },
    {
        "cat": "Fake-DOI",
        "id": "fdoi-4",
        "raw": "Johnson T. Direct synthesis of gold from seawater at room temperature. Nat Mater. 2023. https://doi.org/10.1234/fake.alchemy.2023",
        "expected": "fake_doi",
    },
    {
        "cat": "Fake-DOI",
        "id": "fdoi-5",
        "raw": "Brown M. Perpetual energy extraction from atmospheric vacuum. Phys Rev. 2020. https://doi.org/10.1111/fake.perpetual.9999",
        "expected": "fake_doi",
    },

    # 5 Fake-Title
    {
        "cat": "Fake-Title",
        "id": "ftit-1",
        "raw": "Vaswani A, Shazeer N. Complete Eradication of All Infectious Pathogens. 2017. https://doi.org/10.1145/3065386",
        "expected": "fake_title",
    },
    {
        "cat": "Fake-Title",
        "id": "ftit-2",
        "raw": "He K, Zhang X. Global Telepathic Synchronization of Neural Brainwaves. CVPR. 2016. https://doi.org/10.1109/cvpr.2016.90",
        "expected": "fake_title",
    },
    {
        "cat": "Fake-Title",
        "id": "ftit-3",
        "raw": "Devlin J, Chang MW. Perpetual Fusion Reactor Design for Domestic Kitchens. 2019. https://doi.org/10.18653/v1/n19-1423",
        "expected": "fake_title",
    },
    {
        "cat": "Fake-Title",
        "id": "ftit-4",
        "raw": "Kingma D, Ba J. Secret Molecular Formula for Eternal Cellular Immortality. 2014. https://doi.org/10.48550/arxiv.1412.6980",
        "expected": "fake_title",
    },
    {
        "cat": "Fake-Title",
        "id": "ftit-5",
        "raw": "Pedregosa F, Varoquaux G. Direct Interstellar Travel via Acoustic Resonances. JMLR. 2011. https://doi.org/10.5555/1953048.2078195",
        "expected": "fake_title",
    },
]


def setup_resolver(db_path: Path) -> UnifiedResolver:
    cache = CacheStore(db_path=db_path)
    resolver = UnifiedResolver(cache=cache)

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


def main():
    db_file = Path(".cache/credence/benchmark_eval.db")
    db_file.parent.mkdir(parents=True, exist_ok=True)
    resolver = setup_resolver(db_file)

    print("=" * 88)
    print(" CREDENCE RETRIEVAL & MATCHER BENCHMARK (20 REFERENCES)")
    print("=" * 88)

    correct_by_cat = {"Valid": 0, "Wrong-Year": 0, "Fake-DOI": 0, "Fake-Title": 0}
    total_by_cat = {"Valid": 5, "Wrong-Year": 5, "Fake-DOI": 5, "Fake-Title": 5}

    print(f"{'Category':<12} {'ID':<8} {'Expected':<12} {'Actual':<12} {'Score':<7} {'Status':<8} {'Discrepancy / Diagnostic'}")
    print("-" * 88)

    total_correct = 0
    for item in BENCHMARK_20_REFERENCES:
        ref = parse_reference(item["raw"], key=item["id"])
        res = resolver.resolve(ref)

        is_correct = res.classification == item["expected"]
        if is_correct:
            total_correct += 1
            correct_by_cat[item["cat"]] += 1
            status_str = "PASS"
        else:
            status_str = "FAIL"

        disc_str = res.discrepancies[0] if res.discrepancies else "Verified exact match"
        if len(disc_str) > 35:
            disc_str = disc_str[:32] + "..."

        print(f"{item['cat']:<12} {item['id']:<8} {item['expected']:<12} {res.classification:<12} {res.score:<7.2f} {status_str:<8} {disc_str}")

    print("-" * 88)
    print("BREAKDOWN BY CATEGORY:")
    for cat, count in correct_by_cat.items():
        pct = (count / total_by_cat[cat]) * 100
        print(f"  * {cat:<12}: {count}/{total_by_cat[cat]} ({pct:.0f}%)")

    overall_pct = (total_correct / len(BENCHMARK_20_REFERENCES)) * 100
    print(f"\nOVERALL ACCURACY: {total_correct}/{len(BENCHMARK_20_REFERENCES)} ({overall_pct:.1f}%)")
    print("=" * 88)


if __name__ == "__main__":
    main()
