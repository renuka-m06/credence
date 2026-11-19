"""Benchmark corruption engine: injects empirical errors into known-good claims.

Corruptions supported per AGENTS.md:
1. number-swap: perturbs empirical numbers or percentages (e.g. 12.1% -> 30%)
2. negation: inverts polarity of empirical findings (e.g. improved -> failed to improve)
3. scope-widen: strips hedges and generalizes pilot/animal findings to universal clinical claims
4. unrelated-citation: points claim to a completely unrelated paper where evidence is absent
5. fake-doi: injects fabricated / nonexistent DOI leading to inaccessible source
6. fabricated-quote: injects an unverified hallucinated quote to test code verification gates
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any, Optional

from credence.report.models import AccessTier, VerdictType


# ---------------------------------------------------------------------------
# Base Scientific Ground Truth Papers & Claims
# ---------------------------------------------------------------------------

BASE_SCIENTIFIC_CLAIMS = [
    {
        "id": "base-med-compound-x",
        "domain": "Medicine / Cardiology",
        "claim_text": "Patients receiving Compound-X demonstrated a 12.1% reduction in 30-day mortality [1]",
        "citation_key": "1",
        "doi": "10.1056/NEJMoa12345",
        "source_title": "Evaluation of Compound-X in Acute Coronary Syndromes",
        "source_text": (
            "Background: We evaluated Compound-X in acute coronary syndromes. "
            "In a double-blind, randomized controlled trial involving 1,450 patients, "
            "patients receiving Compound-X demonstrated a 12.1% reduction in 30-day mortality "
            "compared with the placebo arm (p = 0.003). Adverse events were similar across both groups."
        ),
        "access_tier": "full_text",
        "finding": "reduction in 30-day mortality",
        "number": "12.1%",
    },
    {
        "id": "base-edu-learnfast",
        "domain": "Education Technology",
        "claim_text": "LearnFast software increased student test scores [4]",
        "citation_key": "4",
        "doi": "10.1145/3065386",
        "source_title": "Classroom Evaluation of Interactive Educational Software",
        "source_text": (
            "Background: Educational software interventions were evaluated. "
            "In our pilot evaluation involving 40 students with no control group, "
            "test scores increased by 12.1%. Further randomized trials are required to establish efficacy."
        ),
        "access_tier": "full_text",
        "finding": "increased student test scores",
        "number": "12.1%",
    },
    {
        "id": "base-ai-transformers",
        "domain": "Artificial Intelligence / NLP",
        "claim_text": "The Transformer model achieved a score of 28.4 BLEU on the WMT 2014 English-to-German translation task [5]",
        "citation_key": "5",
        "doi": "10.48550/arXiv.1706.03762",
        "source_title": "Attention Is All You Need",
        "source_text": (
            "On the WMT 2014 English-to-German translation task, the big transformer model achieves "
            "a state-of-the-art BLEU score of 28.4, outperforming the best previously reported models, "
            "including ensembles, by more than 2.0 BLEU. The model was trained on 8 P100 GPUs."
        ),
        "access_tier": "full_text",
        "finding": "achieved state-of-the-art BLEU score",
        "number": "28.4",
    },
    {
        "id": "base-oncol-pembro",
        "domain": "Oncology / Immunotherapy",
        "claim_text": "Pembrolizumab combined with chemotherapy improved median progression-free survival to 8.8 months compared with 4.2 months for chemotherapy alone [2]",
        "citation_key": "2",
        "doi": "10.1056/NEJMoa1801005",
        "source_title": "Pembrolizumab plus Chemotherapy in Metastatic Non-Small-Cell Lung Cancer",
        "source_text": (
            "In patients with metastatic non-small-cell lung cancer, the addition of pembrolizumab "
            "to standard chemotherapy resulted in significantly longer overall survival. "
            "The median progression-free survival was 8.8 months in the pembrolizumab-combination group "
            "versus 4.2 months in the placebo-combination group (hazard ratio for disease progression, 0.52; p < 0.001)."
        ),
        "access_tier": "full_text",
        "finding": "improved progression-free survival",
        "number": "8.8 months",
    },
    {
        "id": "base-phys-qdots",
        "domain": "Physics / Nanotechnology",
        "claim_text": "Colloidal perovskite quantum dots achieved a photoluminescence quantum yield of 92.5% at room temperature [7]",
        "citation_key": "7",
        "doi": "10.1021/acs.nanolett.5b02554",
        "source_title": "Colloidal Perovskite Nanocrystals with High Photoluminescence",
        "source_text": (
            "Colloidal cesium lead halide perovskite nanocrystals exhibit bright photoluminescence. "
            "We synthesize monodisperse nanocrystals demonstrating photoluminescence quantum yields "
            "reaching 92.5% at room temperature without the need for post-synthetic surface shell growth."
        ),
        "access_tier": "full_text",
        "finding": "photoluminescence quantum yields reaching 92.5%",
        "number": "92.5%",
    },
    {
        "id": "base-neuro-amyloid",
        "domain": "Neuroscience / Alzheimer's",
        "claim_text": "Lecanemab therapy reduced brain amyloid plaque burden by 41.2% at 18 months [3]",
        "citation_key": "3",
        "doi": "10.1056/NEJMoa2212948",
        "source_title": "Lecanemab in Early Alzheimer's Disease",
        "source_text": (
            "In this 18-month multicenter phase 3 trial in early Alzheimer's disease, "
            "intravenous lecanemab reduced brain amyloid burden on PET imaging by 41.2% relative to placebo "
            "(difference: -59.1 centiloids, p < 0.001). Infusion-related reactions occurred in 26.4% of participants."
        ),
        "access_tier": "full_text",
        "finding": "reduced brain amyloid burden",
        "number": "41.2%",
    },
    {
        "id": "base-crispr-cas9",
        "domain": "Genetics / Gene Editing",
        "claim_text": "Cas9 ribonucleoprotein delivery achieved 68.4% targeted gene disruption in primary T cells [6]",
        "citation_key": "6",
        "doi": "10.1073/pnas.1512503112",
        "source_title": "Generation of Knockout Human T Cells Using Cas9 RNPs",
        "source_text": (
            "Electroporation of recombinant Cas9 ribonucleoproteins into stimulated primary human T cells "
            "achieved targeted gene disruption frequencies of up to 68.4% at the CXCR4 locus. "
            "Off-target cleavage was below 0.5% across predicted genomic homologous sites."
        ),
        "access_tier": "full_text",
        "finding": "targeted gene disruption",
        "number": "68.4%",
    },
    {
        "id": "base-vax-mrna",
        "domain": "Virology / Immunology",
        "claim_text": "The mRNA-1273 vaccine demonstrated 94.1% efficacy against symptomatic illness in a trial of 30,420 participants [8]",
        "citation_key": "8",
        "doi": "10.1056/NEJMoa2035389",
        "source_title": "Efficacy and Safety of the mRNA-1273 SARS-CoV-2 Vaccine",
        "source_text": (
            "The trial enrolled 30,420 volunteers who were randomly assigned in a 1:1 ratio. "
            "Symptomatic illness occurred in 185 participants in the placebo group and in 11 participants "
            "in the mRNA-1273 group. Vaccine efficacy was 94.1% (95% CI: 89.3 to 96.8%; p < 0.001)."
        ),
        "access_tier": "full_text",
        "finding": "vaccine efficacy of 94.1%",
        "number": "94.1%",
    },
    {
        "id": "base-energy-perovskite",
        "domain": "Energy / Solar Cells",
        "claim_text": "Perovskite-silicon tandem solar cells reached a certified power conversion efficiency of 29.8% [9]",
        "citation_key": "9",
        "doi": "10.1126/science.abd4016",
        "source_title": "Monolithic Perovskite/Silicon Tandem Solar Cells Exceeding 29%",
        "source_text": (
            "Monolithic perovskite/silicon tandem architectures enable low-cost, high-efficiency photovoltaics. "
            "Here we report a certified power conversion efficiency of 29.8% for a tandem device, "
            "enabled by self-assembled methyl-substituted carbazole hole-selective monolayers."
        ),
        "access_tier": "full_text",
        "finding": "power conversion efficiency of 29.8%",
        "number": "29.8%",
    },
    {
        "id": "base-cardio-dash",
        "domain": "Public Health / Nutrition",
        "claim_text": "The DASH diet reduced systolic blood pressure by 5.5 mmHg compared with the control diet [10]",
        "citation_key": "10",
        "doi": "10.1056/NEJM199704173361601",
        "source_title": "A Clinical Trial of the Effects of Dietary Patterns on Blood Pressure",
        "source_text": (
            "In 459 adults with systolic blood pressure of less than 160 mm Hg, "
            "the combination DASH diet reduced systolic blood pressure by 5.5 mmHg (p < 0.001) "
            "and diastolic blood pressure by 3.0 mmHg (p < 0.001) more than the control diet."
        ),
        "access_tier": "full_text",
        "finding": "reduced systolic blood pressure",
        "number": "5.5 mmHg",
    },
    {
        "id": "base-supercond-lah",
        "domain": "Condensed Matter Physics",
        "claim_text": "Lanthanum hydride exhibited superconductivity at a critical temperature of 250 K under 170 GPa pressure [11]",
        "citation_key": "11",
        "doi": "10.1038/s41586-019-1201-8",
        "source_title": "Superconductivity at 250 K in Lanthanum Hydride Under High Pressures",
        "source_text": (
            "We synthesized lanthanum hydride (LaH10) in diamond anvil cells and observed electrical "
            "resistance dropping sharply to zero at a critical temperature of 250 K at 170 GPa. "
            "The upper critical magnetic field was estimated to exceed 120 tesla at low temperatures."
        ),
        "access_tier": "full_text",
        "finding": "superconductivity at a critical temperature of 250 K",
        "number": "250 K",
    },
    {
        "id": "base-astro-proxima",
        "domain": "Astrophysics / Exoplanets",
        "claim_text": "Doppler measurements detected a planet orbiting Proxima Centauri with a minimum mass of 1.17 Earth masses [12]",
        "citation_key": "12",
        "doi": "10.1051/0004-6361/202037998",
        "source_title": "Revisiting the Proxima Centauri Planetary System",
        "source_text": (
            "High-precision radial velocity observations from ESPRESSO confirmed the presence of Proxima b. "
            "The planet has an orbital period of 11.2 days and a minimum mass of 1.17 Earth masses "
            "(± 0.19 Earth masses), orbiting within the habitable zone of the red dwarf host star."
        ),
        "access_tier": "full_text",
        "finding": "detected a planet with minimum mass 1.17 Earth masses",
        "number": "1.17 Earth masses",
    },
    {
        "id": "base-econ-microcredit",
        "domain": "Economics / Development",
        "claim_text": "Microcredit expansion showed no significant effect on average business profits across 104 urban slums [13]",
        "citation_key": "13",
        "doi": "10.1257/app.20130533",
        "source_title": "The Miracle of Microfinance? Evidence from a Randomized Evaluation",
        "source_text": (
            "We report on a randomized evaluation of microcredit in Hyderabad, India. "
            "While borrowing increased, we find no significant effect of access to microfinance "
            "on average business profits, average monthly consumption, or female empowerment measures."
        ),
        "access_tier": "full_text",
        "finding": "no significant effect on average business profits",
        "number": "104",
    },
    {
        "id": "base-psych-replication",
        "domain": "Psychology / Replication",
        "claim_text": "A multi-lab replication of the ego depletion effect observed an effect size of d = 0.04 across 23 laboratories [14]",
        "citation_key": "14",
        "doi": "10.1177/1745691616652873",
        "source_title": "A Multilab Preregistered Replication of the Ego-Depletion Effect",
        "source_text": (
            "In a registered replication report encompassing 23 laboratories and 2,141 participants, "
            "the observed meta-analytic effect size for ego depletion was d = 0.04 (95% CI: -0.07 to 0.15). "
            "The result was statistically indistinguishable from zero across all testing sites."
        ),
        "access_tier": "full_text",
        "finding": "observed an effect size of d = 0.04",
        "number": "0.04",
    },
    {
        "id": "base-climate-icecore",
        "domain": "Paleoclimatology",
        "claim_text": "Antarctic ice core data demonstrated atmospheric carbon dioxide levels remained between 180 and 280 ppm over the past 800,000 years [15]",
        "citation_key": "15",
        "doi": "10.1038/nature06949",
        "source_title": "High-Resolution Carbon Dioxide Specimen from EPICA Dome C Ice Core",
        "source_text": (
            "Analysis of air bubbles trapped in the EPICA Dome C Antarctic ice core reveals that "
            "atmospheric CO2 concentrations fluctuated strictly within 180 to 280 ppm throughout the "
            "past 800,000 years, establishing that modern CO2 concentrations exceed pre-industrial baselines."
        ),
        "access_tier": "full_text",
        "finding": "CO2 concentrations fluctuated within 180 to 280 ppm",
        "number": "800,000 years",
    },
]

# Unrelated papers used for unrelated-citation corruption
UNRELATED_PAPERS = [
    {
        "doi": "10.1103/PhysRevLett.116.061102",
        "title": "Observation of Gravitational Waves from a Binary Black Hole Merger",
        "text": (
            "On September 14, 2015 at 09:50:45 UTC the two detectors of the Laser Interferometer "
            "Gravitational-Wave Observatory observed a transient gravitational-wave signal from a "
            "binary black hole merger with initial black hole masses of 36 and 29 solar masses."
        ),
        "key": "99",
    },
    {
        "doi": "10.1038/nature01404",
        "title": "Initial Sequencing and Analysis of the Human Genome",
        "text": (
            "The human genome contains roughly 3 billion base pairs of DNA. We report the sequence "
            "and comparative analysis of the euchromatic portion, revealing approximately 20,000 to "
            "25,000 protein-coding genes."
        ),
        "key": "98",
    },
    {
        "doi": "10.1145/3318464.3389700",
        "title": "Spanner: Google's Globally-Distributed Database",
        "text": (
            "Spanner is Google's scalable, multi-version, globally-distributed, and synchronously-replicated "
            "database. It allocates globally-meaningful commit timestamps using TrueTime APIs."
        ),
        "key": "97",
    },
]


# ---------------------------------------------------------------------------
# Individual Corruption Functions
# ---------------------------------------------------------------------------

def inject_number_swap(base: dict[str, Any], swap_mode: str = "auto") -> dict[str, Any]:
    """Corrupt claim by injecting conflicting numerical assertions.

    Produces:
      - 'partially_supported' when finding direction holds but statistical figure is inflated/discrepant
      - 'contradictory' when extreme numerical conflict is introduced
    """
    claim_text = base["claim_text"]
    source_text = base["source_text"]

    # Match numbers like 12.1%, 92.5%, 28.4, 8.8, 41.2%, etc.
    pct_matches = list(re.finditer(r'(\d+(?:\.\d+)?)\s*(%|percent|months?|mmHg|K|BLEU)?', claim_text))

    if not pct_matches:
        # Fallback perturbation
        corrupted_text = claim_text + " reaching 95% efficacy"
        expected_verdict = "contradictory"
    else:
        # Pick first significant number
        target = pct_matches[0]
        val = float(target.group(1))
        unit = target.group(2) or ""

        # Perturb value significantly (e.g. 12.1% -> 30%, 28.4 -> 48.4, 92.5% -> 25.0%)
        if val > 50.0:
            new_val = round(val / 3.0, 1)  # Drop to low number
        elif val < 20.0:
            new_val = 30.0 if "12.1" in str(val) else round(val * 2.8, 1)
        else:
            new_val = round(val + 20.0, 1)

        rep = f"{new_val}{unit}" if not unit or unit == "%" else f"{new_val} {unit}"
        corrupted_text = claim_text[:target.start()] + rep + claim_text[target.end():]
        expected_verdict = "partially supported"

    return {
        "id": f"{base['id']}-numswap",
        "claim_text": corrupted_text,
        "source_text": source_text,
        "citation_key": base["citation_key"],
        "doi": base["doi"],
        "expected_verdict": expected_verdict,
        "corruption_type": "number_swap",
        "access_tier": base.get("access_tier", "full_text"),
        "details": f"Number perturbed from source value in {base['id']}",
    }


def inject_negation(base: dict[str, Any]) -> dict[str, Any]:
    """Corrupt claim by inverting empirical polarity, yielding a direct contradiction."""
    claim_text = base["claim_text"]
    source_text = base["source_text"]

    # Transformation rules for empirical assertions
    transformations = [
        (r'\bdemonstrated a\b', 'failed to demonstrate any'),
        (r'\bdemonstrated\b', 'failed to demonstrate'),
        (r'\bimproved\b', 'failed to improve'),
        (r'\bincreased\b', 'failed to increase'),
        (r'\breduced\b', 'increased'),
        (r'\breached\b', 'failed to reach'),
        (r'\bachieved a\b', 'failed to achieve a'),
        (r'\bachieved\b', 'failed to achieve'),
        (r'\bexhibited\b', 'failed to exhibit'),
        (r'\bdetected\b', 'failed to detect'),
        (r'\bshowed no significant effect\b', 'demonstrated dramatic positive effects'),
    ]

    corrupted_text = claim_text
    applied = False
    for pattern, replacement in transformations:
        if re.search(pattern, corrupted_text, re.IGNORECASE):
            corrupted_text = re.sub(pattern, replacement, corrupted_text, count=1, flags=re.IGNORECASE)
            applied = True
            break

    if not applied:
        corrupted_text = f"Contrary to hypothesis, {claim_text[:1].lower() + claim_text[1:]} showed no effect"

    return {
        "id": f"{base['id']}-negation",
        "claim_text": corrupted_text,
        "source_text": source_text,
        "citation_key": base["citation_key"],
        "doi": base["doi"],
        "expected_verdict": "contradictory",
        "corruption_type": "negation",
        "access_tier": base.get("access_tier", "full_text"),
        "details": f"Inverted polarity on {base['id']}",
    }


def inject_scope_widen(base: dict[str, Any]) -> dict[str, Any]:
    """Corrupt claim by widening scope, stripping hedges, or injecting definitive boosters."""
    claim_text = base["claim_text"]
    source_text = base["source_text"]

    # Replace qualified or limited claims with absolute universal claims
    widenings = [
        (r'\[(\d+)\]', r'definitively across all human patient populations [\1]'),
        (r'\b(\w+)\s+reduced\b', r'\1 definitively cures and eliminates'),
        (r'\b(\w+)\s+improved\b', r'\1 unconditionally guarantees massive improvements in'),
        (r'\b(\w+)\s+increased\b', r'\1 proves permanent universal increases in'),
    ]

    corrupted_text = claim_text
    applied = False
    for pat, rep in widenings:
        if re.search(pat, corrupted_text, re.IGNORECASE):
            corrupted_text = re.sub(pat, rep, corrupted_text, count=1, flags=re.IGNORECASE)
            applied = True
            break

    if not applied:
        corrupted_text = f"The intervention conclusively cures all conditions and guarantees perfection {claim_text}"

    return {
        "id": f"{base['id']}-scopewiden",
        "claim_text": corrupted_text,
        "source_text": source_text,
        "citation_key": base["citation_key"],
        "doi": base["doi"],
        "expected_verdict": "unsupported",
        "corruption_type": "scope_widen",
        "access_tier": base.get("access_tier", "full_text"),
        "details": f"Epistemic hedge stripping and booster injection on {base['id']}",
    }


def inject_unrelated_citation(base: dict[str, Any], unrelated_paper: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Corrupt claim by pointing citation to a completely unrelated paper where evidence is absent."""
    if not unrelated_paper:
        unrelated_paper = UNRELATED_PAPERS[0]

    claim_text = re.sub(r'\[\d+\]', f"[{unrelated_paper['key']}]", base["claim_text"])

    return {
        "id": f"{base['id']}-unrelated",
        "claim_text": claim_text,
        "source_text": unrelated_paper["text"],
        "citation_key": unrelated_paper["key"],
        "doi": unrelated_paper["doi"],
        "expected_verdict": "unsupported",
        "corruption_type": "unrelated_citation",
        "access_tier": "full_text",
        "details": f"Swapped cited source for unrelated publication '{unrelated_paper['title']}'",
    }


def inject_fake_doi(base: dict[str, Any], idx: int = 1) -> dict[str, Any]:
    """Corrupt claim by injecting a nonexistent/fabricated DOI and inaccessible source text."""
    fake_doi = f"10.9999/fake.doi.credence.benchmark.{idx:04d}"

    return {
        "id": f"{base['id']}-fakedoi",
        "claim_text": base["claim_text"],
        "source_text": "",
        "citation_key": base["citation_key"],
        "doi": fake_doi,
        "expected_verdict": "needs review",
        "corruption_type": "fake_doi",
        "access_tier": "inaccessible",
        "details": f"Fabricated DOI '{fake_doi}' with inaccessible paper text",
    }


def inject_fabricated_quote(base: dict[str, Any]) -> dict[str, Any]:
    """Inject an unverified, hallucinated quote to test code verification gate (Golden Rule 2)."""
    # Plausible sounding academic quote that does not appear anywhere in source text
    fab_quote = (
        f"In our multi-site analysis, {base['finding']} was conclusively confirmed "
        f"with p < 0.00001 across all secondary endpoints without exception."
    )

    return {
        "id": f"{base['id']}-fabquote",
        "claim_text": base["claim_text"],
        "source_text": base["source_text"],
        "citation_key": base["citation_key"],
        "doi": base["doi"],
        "expected_verdict": "needs review",
        "corruption_type": "fabricated_quote",
        "access_tier": base.get("access_tier", "full_text"),
        "fabricated_quote": fab_quote,
        "details": "Simulated hallucinated quote rejected by deterministic quote_check",
    }


# ---------------------------------------------------------------------------
# Dataset Generation Pipeline
# ---------------------------------------------------------------------------

def generate_gold_dataset(
    output_path: Optional[str] = "gold_set.jsonl",
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Generate a balanced gold standard benchmark dataset with known-good and corrupted claims."""
    random.seed(seed)
    dataset: list[dict[str, Any]] = []

    # 1. Clean Known-Good Claims (Expected: Supported)
    for b in BASE_SCIENTIFIC_CLAIMS:
        # Full text supported
        dataset.append({
            "id": f"{b['id']}-clean",
            "claim_text": b["claim_text"],
            "source_text": b["source_text"],
            "citation_key": b["citation_key"],
            "doi": b["doi"],
            "expected_verdict": "supported",
            "corruption_type": "none",
            "access_tier": "full_text",
            "details": "Ground truth verified scientific claim",
        })

    # 2. Number-Swap Corruptions (Expected: Partially Supported or Contradictory)
    for b in BASE_SCIENTIFIC_CLAIMS:
        dataset.append(inject_number_swap(b))

    # 3. Negation Corruptions (Expected: Contradictory)
    for b in BASE_SCIENTIFIC_CLAIMS:
        dataset.append(inject_negation(b))

    # 4. Scope-Widen Corruptions (Expected: Unsupported)
    for b in BASE_SCIENTIFIC_CLAIMS:
        dataset.append(inject_scope_widen(b))

    # 5. Unrelated-Citation Corruptions (Expected: Unsupported)
    for idx, b in enumerate(BASE_SCIENTIFIC_CLAIMS):
        unrel = UNRELATED_PAPERS[idx % len(UNRELATED_PAPERS)]
        dataset.append(inject_unrelated_citation(b, unrel))

    # 6. Fake-DOI / Inaccessible Corruptions (Expected: Needs Review)
    for idx, b in enumerate(BASE_SCIENTIFIC_CLAIMS):
        dataset.append(inject_fake_doi(b, idx + 1))

    # 7. Fabricated-Quote Corruptions (Expected: Needs Review via RULE_HALLUCINATED_QUOTE)
    for b in BASE_SCIENTIFIC_CLAIMS[:10]:
        dataset.append(inject_fabricated_quote(b))

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            for item in dataset:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    return dataset


if __name__ == "__main__":
    items = generate_gold_dataset("gold_set.jsonl")
    print(f"Generated {len(items)} gold benchmark samples in 'gold_set.jsonl'.")
