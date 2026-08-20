# Frozen experiment contract: `baseline_v1`

## Purpose and immutability

`baseline_v1` is the frozen comparison of Direct, Single RAG, and MultiRAG on
the 24-case `handcrafted_smoke_v1` dataset. All three modes use the same local
generation model, task-specific canonical prompt v2, structured-output repair
policy, context window, and evaluator. The only intended mode-dependent input
is retrieved evidence.

This contract is immutable. A change to a prompt, model or digest, top-k,
fusion, generation parameter, dataset, or collection identity requires a new
`baseline_v2`; it must not be written back into `baseline_v1`.

Canonical configuration:
`configs/experiments/baseline_v1.yaml`.

## Frozen runtime and generation

| Field | Value |
|---|---|
| Runtime | WSL/Linux |
| Ollama URL | `http://localhost:11434` |
| Provider | `ollama` |
| Model | `qwen2.5-coder:7b` |
| Model digest | `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364` |
| Temperature / top-p / seed | `0.0` / `0.9` / `42` |
| Maximum generated tokens | `4096` |
| Context window | `32768` |
| Output reservation / safety margin | `2048` / `256` |
| Structured output | task-specific JSON schema, repair retry limit `2` |
| Tokenizer | `Qwen/Qwen2.5-Coder-7B-Instruct` |
| Tokenizer revision | `c03e6d358207e414f1eca0bb1891e29f1db0e242` |

The output reservation and maximum generated tokens record the actual current
runner values; the freeze does not silently normalize or improve them.

## Frozen embeddings and retrieval

| Field | Single RAG | MultiRAG |
|---|---|---|
| Embeddings | `ollama` / `bge-m3`, 1024 dimensions, normalized | same |
| Embedding digest | `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab` | same |
| Collections | `mixed` | `testing_db`, `refactoring_db` |
| Candidate policy | top-k `5` | top-k `5` per collection |
| Final evidence | top-k `5` | global top-k `5` |
| Fusion | none | RRF, `k=60` |
| Retrieval token budget | `12000` | `12000` |
| Allowed split | `train` only | `train` only |

Direct mode performs no retrieval. Smoke and benchmark/test examples are never
indexed.

## Canonical prompts

| Prompt field | Frozen value |
|---|---|
| Template version | `canonical-se-prompt-v2` |
| Testing template SHA-256 | `cfcd5f889c413fac5a75a69482b1dafc27a558334ce72463f0a1a82aa9c9d034` |
| Refactoring template SHA-256 | `f61cd1f944ac312414f6b2c1ccf1759b66e73fe23bc79b43fcdbc9ec02a9fde9` |

The runner recomputes both hashes from the canonical builder before inference.
Any difference produces `BASELINE_MISMATCH` and a failed preflight.

## Dataset and collection identity

`handcrafted_smoke_v1`:

- manifest ID:
  `a1e68395741c9b7f9f0e099b9a5e4f7a8513369177a526a052545a0f9a9cad5a`;
- content hash:
  `69273a1a5242a540060bfb191ab1ce8f15b1b5643f351d16dbe2cb4f8403c49b`.

| Collection | Documents | Semantic manifest ID | Corpus content hash |
|---|---:|---|---|
| `mixed` | 5739 | `18774f2a5a18f6c98cd0a69bed572dbc9dc079c499e5e93178e878ca9af4c029` | `2f07ebff77775c418757bda002d5ecc5fd053ef5cbbf998dc4c0efbe2474c3d2` |
| `testing_db` | 3978 | `765bc53bc741f78525d52148f91fd38984578cd042b1e07eba67c5fea9d9a681` | `921592f25033cd861b408c56d4cc6ea20a8e8a18b35d2dcd58db2b3923d5e171` |
| `refactoring_db` | 1761 | `30b8f729fd65cd9cbb095fa75f6ee512c9bf1c0648788ced661d119c6020aba5` | `598ff0e4b1a1a8b439a13f6a7e40fdb99452dc55addb21669bdd866459d5df25` |

Collection identities are canonical JSON hashes over semantic manifest fields;
build timestamps and local absolute paths are excluded. Corpus hashes cover the
upstream dataset manifest IDs, document count, chunker, ingestion pipeline, and
embedding template contract.

## Baseline fingerprint and artifacts

The frozen fingerprint is:

```text
74cc0a39be0c4d7f193fc749d8a40d448e4c364bef0b2c9eca19190c8db79e8f
```

It is SHA-256 over deterministic canonical JSON containing the effective
runtime, generation, embeddings, retrieval/fusion, prompt, dataset, and
collection contracts above. It excludes timestamps, output location,
`require_runtime_assets`, and absolute local paths, so the same effective
contract has the same fingerprint on another machine.

Every runner invocation writes or verifies two immutable artifacts in its
output directory:

- `effective_config.yaml`: resolved experiment and retrieval configuration;
- `environment.json`: actual OS/runtime, Python, live Ollama digests, portable
  Chroma path, collection identities, and baseline fingerprint.

An existing artifact with different content fails instead of being silently
overwritten. `runs.jsonl` remains append-only. Reports select only records with
the current `(baseline_id, baseline_fingerprint, case_id, mode)` identity, so
older prompt or 2048-token attempts remain auditable but are excluded.

## Fairness and preflight

Fairness requires identical task contract, case input, requirements, project
context, output schema, generation settings, and evaluator across modes. Prompt
normalization must differ only in `RETRIEVED EVIDENCE`.

Before inference the runner checks the baseline fingerprint, live generation
and embedding digests, current prompt hashes, retrieval config, collection
manifests, smoke manifest/content hash, leakage status, and WSL runtime. There
is no fallback to another model, prompt, collection, or URL.

Use the non-inference validation command:

```bash
python -m llm_ontology.experiments.smoke \
  --config configs/experiments/baseline_v1.yaml \
  --dry-run
```

The frozen contract expects `Preflight: PASS`, `Fairness: PASS`, baseline
fingerprint `MATCH`, and 72 planned runs.
