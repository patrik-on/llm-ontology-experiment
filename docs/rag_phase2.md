# Controlled RAG baseline: phases 2 and 3

This implementation keeps the repository's existing boundaries and adds the
controlled baseline on top of them. Existing metadata-RAG and MultiRAG enums and
templates remain available, but the new experiment runner accepts only `no_rag`
and one explicitly named collection.

## Controlled corpora

`ThreeCollectionCorpusBuilder` constructs exactly these corpora:

| Collection | Refactoring pairs | Testing pairs | Shared literature |
|---|---:|---:|---:|
| `refactor` | yes | no | yes |
| `tests` | no | yes | yes |
| `mixed` | yes | yes | yes |

Literature is materialized from collection-independent `KnowledgeDocument`
objects. Consequently, its document IDs, chunks, metadata, content hashes and
embedding-template version are identical in all three collections. Collection
membership is a storage concern and is excluded from document identity.

Dataset manifests independently record `source_split`, `usage_role` and
`allowed_for_indexing`. Indexing is refused unless a manifest is explicitly
indexable and has retrieval usage. Literature paths and approval therefore live
in the manifest; the repository currently contains no approved final PDF corpus.

Leakage checks compare the input-code hash, normalized focal-method hash,
full-document hash and structured case identity. Methods2Test keeps its original
context level in metadata. The baseline input field is `src_fm`; changing the
loader configuration to `src_fm_fc` is an explicit ablation and requires no code
change.

## Parsing and ingestion

- Java parsing uses tree-sitter and records package, imports, classes, fields,
  methods, constructors, annotations, comments and line spans.
- Before/after and production/test pairs remain atomic retrieval examples.
- Parse failures use a traceable whole-document fallback.
- The page-aware PDF loader removes repeated headers and footers, preserves page
  provenance, isolates corrupt documents and reports pages that require OCR.
- PDF behavior is tested with small generated PDFs only. No final literature
  index is created by tests or configuration loading.

## Embeddings and index lifecycle

The primary baseline candidate is
`jinaai/jina-embeddings-v2-base-code`, not a final choice for every experiment.
Both model artifacts and the separate remote-code repository are pinned:

- model revision: `516f4baf13dec4ddddda8631e019b5737c8bc250`;
- remote-code revision: `3baf9e3ac750e76e8edd3019170176884695fb94`;
- embedding dimension: 768;
- normalized vectors: enabled.

The real CPU sanity test embeds two short documents and verifies that a
refactoring query ranks the refactoring document above a testing document. It
passed before any full-corpus indexing. The test also exposed that the model's
remote code is incompatible with Transformers 5.x, so the RAG dependency is
constrained to Transformers 4.x.

Every persistent collection has a sidecar manifest containing model and code
revisions, dimension, normalization, embedding-template version, chunker and
pipeline versions, dataset manifest IDs and runtime library versions. Querying
through `CollectionIndexLifecycle` rejects a missing or stale manifest. Rebuild
is explicit and replaces only the exactly named collection.

## Generation and reproducibility

`OllamaProvider` records the installed model digest, seed, generation options,
client latency and Ollama token/timing counters. It sends the task-specific
Pydantic JSON Schema to Ollama and the structured-output layer performs only a
bounded number of format-repair retries.

Input context is budgeted with the pinned Qwen tokenizer:

- tokenizer: `Qwen/Qwen2.5-Coder-7B-Instruct`;
- revision: `c03e6d358207e414f1eca0bb1891e29f1db0e242`.

The character-based counter remains available only as an explicitly labelled
test/fallback method. Each record stores token method, tokenizer revision,
fixed-prompt tokens, selected/truncated/dropped documents, retrieval tokens,
output reserve and safety margin.

The runner stores the requested task alias and canonical task, retrieval mode,
collection, dataset manifest IDs, embedding/code revisions, LLM digest, prompt
artifact path and hash, retrieval trace, structured attempts and response.

## Experiment matrix

The six configurations are under `configs/experiments/rag_v2/`:

- refactoring: `no_rag`, `refactor`, `mixed`;
- testing: `no_rag`, `tests`, `mixed`.

They are intentionally `enabled: false` while dataset manifest IDs are empty.
They must be populated from approved datasets and approved literature manifests
before execution. This prevents a test PDF or an unreviewed document from being
silently promoted into the research index.
