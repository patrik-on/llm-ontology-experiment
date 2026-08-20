# Legacy Cleanup Audit

Audit performed before deletion. Candidates were checked with repository-wide
searches across Python imports, tests, CLI wrappers, YAML references, README,
and `docs/`. Classification reflects methodological value, not filename age.

## KEEP

- `llm_ontology.providers.ollama.OllamaEmbeddingProvider` and
  `llm_ontology.inference.ollama_client.OllamaProvider`: distinct embedding and
  generation contracts used by the current WSL runtime.
- `llm_ontology.retrieval`, `llm_ontology.vectorstore`,
  `llm_ontology.ingestion`, `RagExperimentRunner`, and `UIService`: current
  shared RAG runtime and test-covered service boundaries.
- `approaches/{direct,rag,multi_rag}` and the registry: shared prompt contracts;
  the MultiRAG approach remains prompt-only while the implemented RRF/fusion
  belongs to the shared `retrieval` layer.
- `RagGenerationService`: superseded for controlled experiments by
  `RagExperimentRunner`, but still imported and behavior-tested by
  `tests/test_rag_retrieval.py`.
- `configs/retrieval/base.yaml` and the controlled experiment templates: mock
  plumbing and schemas are referenced by tests.
- Canonical scripts under `scripts/{data,evaluation,inference,training}/`: used
  by runbooks, tests, and reproducibility workflows.

## LEGACY

- Jina/Sentence Transformers provider and `jina_qwen_baseline.yaml`:
  `legacy_not_final`, retained for comparison.
- Hugging Face model/fine-tuning configs: `legacy_not_final` for historical
  training reproduction; not used by the WSL Ollama final baseline.
- Windows environment lock and package lock: historical provenance and
  explicitly referenced by tests and environment/split documentation.
- Root-level evaluation/training script wrappers: compatibility entrypoints
  referenced by existing runbooks. Canonical implementations live in their
  namespaced `scripts/` subdirectories.
- `llm_ontology.finetuning`: compatibility package still imported by training,
  evaluation, scripts, and tests.
- `scripts/inference/generate.py` and `scripts/evaluation/evaluate.py`: explicit
  failing legacy pointers tested by `tests/test_legacy_entrypoints.py`.

## REMOVE

- `configs/templates/rag_template.yaml` and its directory note: deprecation-only
  pointer with no import, config, test, CLI, or documentation references; the
  canonical template is `configs/experiments/rag/template.yaml`.
- `scripts/retrieval/rag.py`: zero-reference wrapper around the canonical
  `python -m llm_ontology.cli.rag` entrypoint.
- `src/llm_ontology/models/base_model.py` and `adapters.py`: ignored local
  duplicates with zero imports after `models/loader.py` became the canonical,
  tested loader.
- `scripts/retrieval/sanity_ollama_embeddings.py`: remove only after the
  manifest-gated production builder and smoke validation replace its temporary
  100+100 role; update its sole documentation reference at the same time.
- Local `__pycache__`/`.pyc`: generated artifacts, already ignored; safe to
  discard but not part of the source patch.

No provider wrapper, Windows/HF provenance config, benchmark definition, or
test-referenced compatibility boundary is approved for deletion by this audit.
