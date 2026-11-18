"""Offline token-length diagnostics; no weights, training or dataset changes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from llm_ontology.finetuning.training.finetuning import build_tokenized_training_example


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer", required=True, type=Path, help="Existing local tokenizer directory")
    parser.add_argument("--dataset", required=True, type=Path, action="append", help="JSONL; repeat for separate splits")
    parser.add_argument("--max-seq-length", type=int, default=2048)
    args = parser.parse_args(argv)
    if args.max_seq_length < 2:
        parser.error("--max-seq-length must be at least 2")
    directory = args.tokenizer.expanduser().resolve()
    if not directory.is_dir():
        parser.error("--tokenizer must be an existing local directory")
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(directory), local_files_only=True, trust_remote_code=False)
    result = {"diagnostic_only": True, "tokenization_policy_changed": False,
              "max_seq_length": args.max_seq_length, "tokenizer": str(directory),
              "tokenizer_files": {str(p): digest(p) for p in sorted(directory.glob("*.json"))
                                  if "token" in p.name or p.name == "config.json"}, "datasets": {}}
    for path in args.dataset:
        path = path.expanduser().resolve()
        before = digest(path)
        stats = {"sha256": before, "examples": 0, "dropped_examples": 0}
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                stats["examples"] += 1
                build_tokenized_training_example(record, tokenizer, args.max_seq_length, diagnostics=stats)
        if digest(path) != before:
            raise RuntimeError("Dataset changed while diagnosing: " + str(path))
        result["datasets"][str(path)] = stats
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
