# Production RAG and MultiRAG baseline

The controlled baseline uses one WSL runtime, Ollama `bge-m3` embeddings,
ChromaDB, and Qwen generation. Direct, Single RAG, and MultiRAG share
`RagExperimentRunner`, prompt construction, structured-output repair, model
configuration, logging, and output records.

## Leakage-safe corpus

Source manifests under `configs/datasets/manifests/` pin the original train and
benchmark files by SHA-256 and sample count. The production builder first
reserves benchmark identities and conservative Java/full-document fingerprints.
It creates derived retrieval manifests after excluding every overlap; benchmark
records are never passed to the corpus builder or vector store.

The official ML4Refactoring partitions share projects, commits, and some grouped
refactoring identities. The builder therefore records the unsafe pre-filter
audit and creates a method-identity-disjoint derived corpus. Methods2Test uses
project identities. Both tasks then pass a second exact code-fingerprint audit.

Build command:

```bash
source .venv_wsl/bin/activate
python scripts/retrieval/build_production_indexes.py
```

2026-08-20 production inventory:

| Collection | Received pairs | Unique vectors | Duplicates | Source types |
|---|---:|---:|---:|---|
| `testing_db` | 3,986 | 3,978 | 8 | testing |
| `refactoring_db` | 2,043 | 1,761 | 282 | refactoring |
| `mixed` | 6,029 | 5,739 | 290 | testing + refactoring |

`mixed` is asserted equivalent to the union of the disjoint collections before
and after indexing. Literature is not duplicated into specialized stores; an
optional `literature_db` is created only when approved literature exists. No
such source was available for this build.

## Pair-aware ingestion and lifecycle

`ProductionCorpusBuilder` keeps production/test and before/after pairs atomic,
uses the versioned embedding-text builders, and records Java signature metadata.
Untrusted diff or oversized inputs use an explicit auditable fallback. Native
Tree-sitter remains available for ordinary Java ingestion; the production batch
uses the non-native conservative Java signature parser to avoid a reproducible
Tree-sitter crash on malformed diff records.

Every physical collection has a sidecar manifest containing provider, model,
runtime digest, dimension, chunker/pipeline version, derived dataset manifest
IDs, library versions, and final count. Rebuilds replace only the exact named
collection. `mixed` reuses the already produced bge-m3 vectors from the
disjoint stores and writes them in bounded Chroma batches; it does not create a
different embedding space.

## MultiRAG

MultiRAG has no router. Every configured collection is queried in parallel,
then the shared retrieval layer performs:

1. Reciprocal-rank fusion: `sum(1 / (rrf_k + rank))`, default `rrf_k=60`.
2. Deduplication by document ID, normalized content hash, and pair identities.
3. At most one RRF contribution per physical collection for each deduplicated
   document.
4. One global top-k and the same `ContextBudgeter` used by Single RAG.
5. The normal RAG prompt and shared Ollama structured-output path.

The trace preserves collection-local rank/score, source collection, RRF score,
final rank, candidate counts before/after deduplication, selected document IDs,
token counts, and per-step latency. The UI only renders this trace; it contains
no fusion logic.

## Experiment matrix

Eight disabled batch configurations live under `configs/experiments/rag_v2/`:

| Task | Direct | RAG mixed | MultiRAG all | Specialized ablation |
|---|---|---|---|---|
| testing | `testing_no_rag` | `testing_mixed` | `testing_multi` | `testing_tests` |
| refactoring | `refactoring_no_rag` | `refactoring_mixed` | `refactoring_multi` | `refactoring_refactor` |

The main comparison is Direct vs `mixed` Single RAG vs all-collection
MultiRAG. Specialized configurations remain explicit ablations. Batch configs
stay disabled until an evaluation command intentionally enables a run; the UI
copies the same configs and enables only the current interactive request.

## Validation artifacts

`scripts/retrieval/smoke_ui_rag_modes.py` exercises testing/refactoring with
Single RAG and MultiRAG through the real UI service/shared runner. It records
top-k evidence, source types, prompt hash/path, token counts, model digest,
generation success, and the fusion trace under `artifacts/smoke/`.

Ontology augmentation, GraphRAG, routers, rerankers, model changes, and
benchmark composition changes are intentionally outside this baseline.
