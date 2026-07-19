# RAG phase 1

Phase 1 adds an executable, provider-neutral RAG foundation without changing
the existing direct inference, fine-tuning or evaluation workflows.

## Architectural boundaries

```text
llm_ontology.data          existing dataset preparation and split ownership
        |
llm_ontology.ingestion     loaders, chunking and train-only indexing policy
        |
llm_ontology.vectorstore   ChromaDB-specific persistence adapter
        |
llm_ontology.retrieval     provider-neutral requests, filtering and traces
        |
llm_ontology.approaches    direct/RAG prompt construction and injection boundary
        |
llm_ontology.inference     LLM invocation and generation orchestration
        |
llm_ontology.evaluation    metrics and reproducible experiment records
```

Retrieval does not import model generation or task metrics. ChromaDB never
owns the embedding model: vectors are produced by `EmbeddingProvider` and are
passed explicitly to the store. This keeps embedding versions controllable in
experiments and permits a later backend replacement.

## Implemented

- Pydantic schemas for source documents, chunks, requests, hits, traces and
  structured answers;
- explicit `LLMProvider`, `EmbeddingProvider`, `DocumentLoader`,
  `ChunkingStrategy`, `Retriever`, `Reranker`, `PromptBuilder` and
  `ResponseEvaluator` protocols;
- normalized testing/refactoring dataset loader and TXT/Markdown literature
  loader;
- deterministic IDs, normalized SHA-256 content hashes and collection-local
  duplicate suppression;
- separately configured ChromaDB collections;
- `no_rag`, `single_collection_rag` and `metadata_rag` execution;
- mandatory allowed-split filters in both indexing and retrieval;
- scores, filters, selected documents, token estimate and step latency in every
  retrieval trace;
- JSONL experiment records;
- deterministic mock embeddings and mock LLM for offline tests.

## Safety and reproducibility

Only the `train` split is allowed by the default configuration. Indexing a
different split fails before the vector store is mutated. Retrieval always
adds an allowed-split constraint, and a metadata filter cannot override it.

Retrieved documents are rendered as untrusted reference data. Instructions
inside retrieved source code, comments or prose are not system instructions.
Sanitization does not rewrite retrieved code.

The deterministic hash embedding provider is deliberately non-semantic. It is
useful for plumbing tests only and must be replaced by a version-pinned real
embedding provider before collecting thesis results.

## CLI example

Install the RAG dependencies:

```powershell
python -m pip install -e ".[dev,rag]"
```

Index the bundled samples into separate collections:

```powershell
python -m llm_ontology.cli.rag --config configs/retrieval/base.yaml index `
  --loader dataset `
  --input data/samples/testing_methods2test_sample.json `
  --dataset methods2test-sample-v1 `
  --collection test_examples `
  --split train

python -m llm_ontology.cli.rag --config configs/retrieval/base.yaml index `
  --loader dataset `
  --input data/samples/refactoring_ml4ref_sample.json `
  --dataset ml4refactoring-sample-v1 `
  --collection refactoring_examples `
  --split train
```

Query one collection with a metadata filter:

```powershell
python -m llm_ontology.cli.rag --config configs/retrieval/base.yaml query `
  --mode metadata_rag `
  --collection refactoring_examples `
  --query "Rename a misleading Java method" `
  --filter "refactoring_type=Rename Method" `
  --top-k 3
```

The command prints the retrieved documents together with the complete trace.
Re-indexing the same source is idempotent by content hash.

## Superseded limitations

- the mock embedding provider is not suitable for semantic evaluation;
- HTML and ontology loaders are not implemented; the PDF loader and its synthetic
  fixture tests are implemented in phase 2, but no unapproved literature is indexed;
- Java-aware parsing and pair-preserving chunking are implemented in phase 2;
- query routing, multi-collection fusion, ontology expansion and reranking are
  not implemented and raise explicit errors where applicable;
- query routing, multi-collection fusion and ontology expansion remain future work.

The current controlled baseline design is documented in
[RAG phases 2 and 3](rag_phase2.md).
