# Reporting, diagnostics and timeout patch — 2026-11-13

This patch implements the low-risk follow-up to the repository correctness audit.

## Changes

- Methods2Test: charged but unresolved generation cells remain in the call budget,
  but compilation/class-pass/coverage-success results are unknown until terminal
  evidence is available. Completed model-output and infrastructure failures retain
  the existing scoring policy and have distinct `generation_status` values.
- Repeat diagnostics in `aggregate.json` expose both stored coverage measurements,
  coverage mismatch and per-test outcome mismatch warnings. The Markdown summary
  reports unknown class outcomes and repeat warnings. **Primary coverage/class-pass
  scoring is not changed.** Older evidence with no repeat measurements stays unknown.
- `generation_timeout_seconds: 1800` in the shared Java evaluation runtime applies to
  matrix Ollama generation (direct, skills, RAG and refactoring). Embedding timeout,
  interactive provider settings and Java execution timeout are untouched. It is a
  transport timeout, not a strict end-to-end deadline or an HF generation limit.
- Training tokenization optionally accumulates diagnostics without altering returned
  features, truncation, masks or input data. Future training writes a separate
  `results/tokenization_diagnostics.json`; no existing training summary is rewritten.
- Offline diagnostics can be run without model weights, training or network access:

```bash
.venv_wsl/bin/python scripts/finetuning/diagnose_token_lengths.py \
  --tokenizer /mnt/c/models/huggingface/Qwen2.5-Coder-7B-Instruct \
  --dataset data/processed/refactoring/train.jsonl \
  --dataset data/processed/refactoring/val.jsonl \
  --max-seq-length 2048
```

The CLI prints JSON to stdout, including dataset/tokenizer hashes and per-file
original/effective token totals, maxima, truncated outputs and one-token prompts.
It neither loads an adapter nor modifies a dataset. Save stdout to a new file if needed.

A clean-process check also exposed a pre-existing circular import between the
`approaches` package and canonical prompting. Public approach exports now load
lazily; their names and implementations are unchanged. A subprocess regression
checks the standalone training import as well as the public approach API.

## Frozen preparations and compatibility

Existing frozen runs and evidence were **not** rewritten or re-frozen. Source/runtime
changes intentionally invalidate their old source pins: use a **new run ID** for
subsequent generation, and prepare/freeze under the new source identity. Do not
bypass verification or replace source hashes in an old freeze.

No prompts, schemas, decoding token limits, dataset selection logic, retrieval
ranking, training truncation policy or model weights were changed. No model-answer
calls or training were performed. Diagnostics tests assert identical tokenized
features and unchanged primary scores for completed, stored results.

## Verification performed

- Full remaining regression suite: **297 passed, 2 skipped** (31.88 s).
- Ruff over `src scripts tests`: passed.
- Clean subprocess import regression: passed.
- Offline CLI completed over all four actual train/validation files, with no weights
  loaded and no model-answer calls. Results at 2048 tokens:

| Split | Examples | Truncated examples | One-token prompt | Truncated output |
|---|---:|---:|---:|---:|
| refactoring/train | 4478 | 1345 | 162 | 162 |
| refactoring/val | 600 | 173 | 22 | 22 |
| testing/train | 4000 | 1 | 1 | 1 |
| testing/val | 500 | 0 | 0 | 0 |

These reproduce the audit totals. The diagnostic deliberately reports the current
policy rather than fixing it or silently retraining the existing adapters.
