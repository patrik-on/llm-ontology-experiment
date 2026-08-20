# Commit readiness

Validated on 2026-08-20 in the canonical WSL/Linux runtime.

## Current baseline

- Active modes: Direct (`no_rag`), RAG (`single_collection_rag`) and router-free
  MultiRAG (`multi_collection_rag`, RRF `k=60`).
- Generation: Ollama `qwen2.5-coder:7b`.
- Embeddings: Ollama `bge-m3`, dimension 1024.
- Collections: `mixed=5739`, `testing_db=3978`, `refactoring_db=1761`.
- Literature is not part of the current baseline.

## Validation

- Editable install and package imports: passed.
- Environment check: `READY`; Ollama, model digests, Chroma and all three
  collections were detected.
- Gradio startup: passed with an HTTP 200 response on a temporary local port.
- `ruff check .`: passed.
- `python -m compileall -q src`: passed.
- `pytest -q -rs`: 115 passed, 2 skipped. The skips are opt-in Ollama and model
  download integration tests; their HTTP/model boundaries are covered offline.
- `git diff --check`: passed.

## Repository and artifact policy

| Class | Policy |
|---|---|
| TRACK IN GIT | source, tests, configs, dataset manifests, docs, small audit manifests/checksums |
| GITIGNORE | virtualenvs, caches, raw/processed data, Chroma, UI history, prompts, smoke/sanity output, benchmark/evaluation output |
| REMOVE FROM GIT | three approximately 38 MB adapter ZIPs; local copies remain ignored and verified by tracked SHA-256 files |
| KEEP AS DOCUMENTED ARTIFACT | local production indexes, corpus/build/smoke reports and external adapter packages |

Production Chroma data remains under ignored `data/chroma/ollama_bge_m3/` and
must not enter Git history. Large handoff/evaluation artifacts should be
published externally with a small manifest and checksum committed here.

## Known limitations

- No approved literature collection, ontology, GraphRAG, router or reranker.
- Full Direct/RAG/MultiRAG batch evaluation has not been run in this cleanup.
- JaCoCo/PIT project-level evaluation remains future work.
- Historical Windows, Hugging Face and Jina configs remain as
  `legacy_not_final` for provenance and backward compatibility.

## Recommended commit scope

Commit the current source, tests, WSL/Ollama configs, dataset manifests,
documentation, `.env.example`, metadata and removal of obsolete/large tracked
files as one baseline-completion and repository-cleanup change. Do not add any
ignored runtime artifact with `git add -f`.
