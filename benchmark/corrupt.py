"""Root forwarder for benchmark/corrupt.py."""
import sys
from credence.benchmark.corrupt import *

if __name__ == "__main__":
    from credence.benchmark.corrupt import generate_gold_dataset
    out_file = sys.argv[1] if len(sys.argv) > 1 else "gold_set.jsonl"
    items = generate_gold_dataset(out_file)
    print(f"Generated {len(items)} gold benchmark samples in '{out_file}'.")
