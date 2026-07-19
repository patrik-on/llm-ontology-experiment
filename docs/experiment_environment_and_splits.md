# Frozen RAG environment and group-safe dataset splits

Captured on 2026-07-19 for the Windows CPU baseline.

## Runtime lock

The machine-readable lock is
`configs/environment/rag_baseline_windows_cpu.lock.json`; the complete Python
package lock is `configs/environment/requirements-rag-windows-cpu.lock.txt`.

Important frozen values:

| Component | Frozen value |
|---|---|
| Python | CPython 3.12.10, MSC v.1943, Windows AMD64 |
| PyTorch | 2.13.0+cpu; CUDA unavailable |
| sentence-transformers | 5.6.0 |
| transformers | 4.57.6 |
| ChromaDB | 1.5.9 |
| tree-sitter / Java grammar | 0.26.0 / 0.23.5 |
| pypdf | 6.14.2 |
| Jina model revision | `516f4baf13dec4ddddda8631e019b5737c8bc250` |
| Jina remote-code revision | `3baf9e3ac750e76e8edd3019170176884695fb94` |
| Qwen tokenizer revision | `c03e6d358207e414f1eca0bb1891e29f1db0e242` |
| Ollama | 0.32.1 |
| Ollama model | `qwen2.5-coder:7b` |

At capture time Ollama reported no installed models. The Qwen runtime digest is
therefore deliberately `null` and the lock status is
`blocked_missing_runtime_components`. Java, Maven and the TestBench JDK variables
were also absent; this blocks Java benchmark execution but not Python RAG unit
tests. A final experiment must not start in this state.
After installing the exact model, record the digest returned by `/api/tags`, set
`installed: true`, set `runtime_digest`, change the lock status to `ready`, and
rerun the checker.

The source tree was dirty when captured. The lock records base commit
`195ee18c439a725d61c885cbe31130a050ab61fb`; after review, the final experiment
must additionally record the commit containing these changes.

```powershell
python scripts/retrieval/check_environment_lock.py --skip-ollama --skip-benchmark-toolchain
python scripts/retrieval/check_environment_lock.py
```

The first command checks Python, the SHA-256 of the package lock and all 109
locked package versions. The second also requires the exact Ollama version and
model digest plus the Java/Maven benchmark toolchain.

## Dataset roles

The three templates are in `configs/datasets/manifests/`:

| Template | `source_split` | `usage_role` | Indexable |
|---|---|---|---:|
| retrieval | `train` | `retrieval` | yes, after audit |
| pilot validation | `validation` | `pilot_validation` | no |
| final benchmark | `test` | `benchmark` | no |

The fields are not aliases. For example, imported external benchmark data may
have a source-defined split name while its usage role remains `benchmark`.

## Group-safe split policy

Method-level random splitting is not accepted for the controlled experiment.

- Methods2Test derives a project/repository identity from the parent corpus
  directory. Preparation fails if that identity occurs in more than one of the
  official train/eval/test directories. Baseline input remains `src_fm`.
- ML4Refactoring assigns whole projects to a split. All commits and cases from a
  project therefore remain together.
- MaRV assigns whole `(repository, commit_sha)` groups. Multiple related cases
  from one commit cannot cross splits.
- Cross-dataset auditing can be run at project, repository or commit level and
  compares retrieval, pilot-validation and benchmark manifests before indexing.

Example:

```powershell
python scripts/data/audit_group_splits.py `
  --partition configs/datasets/manifests/retrieval.yaml=data/processed/retrieval.jsonl `
  --partition configs/datasets/manifests/pilot_validation.yaml=data/processed/pilot.jsonl `
  --partition configs/datasets/manifests/final_benchmark.yaml=data/processed/benchmark.jsonl `
  --group-level repository `
  --output artifacts/split_audits/repository_audit.json
```

The command returns a non-zero status for overlaps or records without the
required group identity. Code-hash leakage checks remain a second, independent
control; passing a group audit does not replace fingerprint checks.

## Local TestBench checkout

`benchmarks/TestBench-main/` is explicitly ignored. It is a large local
benchmark checkout still under review and is not part of the repository's
committable experimental inputs.
