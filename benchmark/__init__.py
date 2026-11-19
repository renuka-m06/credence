"""Root benchmark package forwarding to credence.benchmark."""
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
