# Developer / Agent Information

> **IMPORTANT FOR FUTURE AGENTS:**
> Read this file before making architectural or experiment-related changes.
> Do not assume that a technically cleaner change is methodologically acceptable.
> Preserve experiment comparability and reproducibility.

This is internal technical context, not a replacement for `README.md`.

## PROJECT AREA OWNERSHIP

- Fine-tuning: **ACTIVE**
- Retrieval/RAG/MultiRAG: **ACTIVE**
- Inference: **ACTIVE**
- Evaluation: **ACTIVE**
- Experiments: **ACTIVE**
- UI: **ACTIVE**

Do not treat a module as legacy only because it is not used by the current
smoke experiment. Fine-tuning, retrieval, inference, evaluation, and experiment
execution are separate active research areas.

Do not delete project-area functionality during organizational refactors.
Before deleting any module in a dedicated cleanup task:

1. Identify its owning project area.
2. Search all code, config, script, test, documentation, and external CLI references.
3. Verify replacement functionality and result equivalence.
4. Document the deletion reason and migration impact.

The repository ownership map is `docs/architecture/project_map.md`; the
pre-reorganization inventory is
`docs/architecture/repository_map_before.md`.

## Project Goal

The project compares Direct LLM, RAG, MultiRAG, and later ontology/GraphRAG
approaches for Java testing and Java refactoring. Comparisons must differ only
in the declared experimental variable; runtime, task contract, data roles, and
reproducibility metadata stay controlled.

## Canonical Task Names

The only internal task names are `testing` and `refactoring`. The aliases in
`llm_ontology.core.task_mode.TASK_ALIASES` are `test_generation` → `testing`
and `refactor` → `refactoring`; the canonical names themselves are also valid.
Do not add task auto-routing unless an experiment explicitly requires it.

## Experimental Runtime

The primary and only final-experiment environment is WSL/Linux. Python,
ChromaDB, Ollama, ingestion, retrieval, runners, evaluation, and the Gradio UI
must run inside that same WSL environment. Ollama runs inside WSL at exactly
`http://localhost:11434`. Do not use a Windows host IP, forwarding, discovery,
or fallback. Windows is only the host/user OS. Windows Ollama may be used for
personal tests, but its results must never be mixed with final experiments.

Canonical setup (the repository virtual environment is `.venv_wsl`):

```bash
ollama serve
ollama pull bge-m3
ollama pull qwen2.5-coder:7b
ollama list
curl http://localhost:11434/api/tags

source .venv_wsl/bin/activate
python -m llm_ontology.env check
python -m llm_ontology.ui
```

The current runtime contract is `configs/retrieval/ollama_bge_m3.yaml` and the
UI selects it through `configs/ui/local.yaml`. Environment checks and UI status
share `llm_ontology.ui.service.EnvironmentStatusService`; do not create a
parallel checker. `python -m llm_ontology.env check` is only a CLI adapter over
that service.

## Models

Embedding uses provider `ollama`, model `bge-m3`, and dimension 1024 through
`llm_ontology.providers.ollama.OllamaEmbeddingProvider`. Generation uses
provider `ollama` and model `qwen2.5-coder:7b` through
`llm_ontology.inference.ollama_client.OllamaProvider`. Both digests must be read
from WSL Ollama `/api/tags` at runtime. The embedding digest is stored in every
collection manifest; the generation digest is stored in every experiment
record. A model tag alone is not a reproducible identity.

The Jina/Sentence Transformers provider remains available for controlled legacy
comparison. Hugging Face and Windows-era configurations are retained as
`legacy_not_final`; they are not current final-experiment baselines.

## Embedding Policy

Use one embedding provider/model/digest/dimension/runtime per index. Never mix
embedding spaces. Changing any embedding setting requires an explicit Chroma
rebuild through `llm_ontology.vectorstore.lifecycle.CollectionIndexLifecycle`.
`CollectionManifestStore` compares provider, model, digest, dimension, and
`ollama_runtime`; stale-manifest protection must not be bypassed and reads must
never silently rebuild or migrate an index.

## Vector Stores

Chroma is configured by `RagConfig`/`VectorStoreSettings` and accessed through
`ChromaVectorStore`; the current baseline root is
`data/chroma/ollama_bge_m3`. Production indexes were built on 2026-08-20.

- `mixed`: 5,739 unique documents for the controlled single-RAG baseline.
- `refactoring_db`: 1,761 unique refactoring documents; logical key `refactor`.
- `testing_db`: 3,978 unique testing documents; logical key `tests`.
- `literature_db`: optional future approved literature corpus; the current
  logical key is `software_engineering_literature`.

Do not rename physical collections during an experiment. A name migration is a
new explicit index build with a new manifest.

## RAG Modes

Direct (`no_rag`) performs no retrieval. Single RAG
(`single_collection_rag`) queries one collection, normally `mixed`, through
`llm_ontology.retrieval.pipeline.VectorRetriever`. MultiRAG queries every
configured disjoint collection in parallel without a router, deduplicates by
document ID/content hash/pair identity, applies RRF with configurable `k=60`,
then one global top-k and the same token budget as Single RAG.
`RagExperimentRunner` supports all three controlled modes.

## UI

Gradio is a thin presentation layer in `llm_ontology.ui`. It must never
duplicate retrieval, prompt, inference, environment, or evaluation logic. Runs
go through `UIService`, `ConfiguredInteractiveRunner`, shared provider factories,
and `RagExperimentRunner`. The Environment tab may inspect status but must not
create indexes or search for another Ollama instance.

## Data Safety and Leakage

Benchmark cases must never be indexed. Dataset manifests
(`llm_ontology.ingestion.manifest.DatasetManifest`) control indexing, and final
retrieval indexes accept approved train-role material only. Retrieval,
validation, and benchmark/evaluation roles are distinct. A source dataset split
is not automatically the same as an experiment usage role. Preserve provenance,
group-safe splits, and leakage audits; do not bypass manifest or allowed-split
checks.

The versioned `handcrafted_smoke_v1` dataset lives in `data/smoke/` with 12
testing and 12 refactoring cases. Its role is `smoke_evaluation`, indexing is
explicitly forbidden, and it must never be reused for retrieval or training.
It is intended only for regression/debug checks, evaluator and prompt
validation, manual pipeline checks, and small pilot experiments. Evaluator-only
fields (`expected_process`, expected outputs, validation rules, and behavior
tests) must not be exposed to the model prompt. See
`docs/datasets/handcrafted_smoke.md`.

## Prompt Policy

Direct, RAG, and MultiRAG use the same task-specific prompt contract from
`llm_ontology.approaches.ApproachPromptBuilder`; only retrieved evidence may
differ. Tune prompt changes on validation data, document their methodological
impact, then freeze the final prompt. `RagExperimentRunner` writes the exact
prompt artifact and SHA-256 hash. Do not change prompts as part of runtime or
infrastructure work.

## Experiment Reproducibility

Every run must store at least generation provider/model/digest, embedding
provider/model/digest, the collection manifest identity, complete config,
dataset manifest IDs, prompt hash/artifact, retrieval trace, token counts,
latencies, raw/structured output, and evaluation result. The core record is
`llm_ontology.evaluation.experiment_log.ExperimentRecord`. Sampling parameters
and random seed are part of the config and must also be preserved.

## Do Not Do

- Do not introduce a second retrieval implementation.
- Do not introduce a second Ollama client if the provider boundary can be extended.
- Do not auto-route tasks unless explicitly required by an experiment.
- Do not mix Windows and WSL runtime results.
- Do not silently rebuild, migrate, or relabel Chroma indexes.
- Do not index benchmark cases.
- Do not remove legacy providers while they remain useful for comparison/provenance.
- Do not change experiment definitions without documenting methodological impact.
- Do not bypass manifest, digest, split, leakage, prompt-hash, or trace safeguards.

## Current Status

- Direct UI works through the shared runner.
- Single-RAG and router-free MultiRAG share one retrieval/generation runner.
- WSL Ollama `bge-m3` embeddings work at dimension 1024.
- Production Chroma counts are `mixed=5739`, `testing_db=3978`, and
  `refactoring_db=1761`; collection manifests pin the bge-m3 digest.
- Post-filter project/method and code-fingerprint audits are clean. The derived
  manifests record every excluded identity/fingerprint overlap.
- `handcrafted_smoke_v1` has 24 balanced reference cases; all inputs and
  reference refactorings compile, all behavior fixtures pass before/after, and
  its stored audit has zero overlap with `mixed`, `testing_db`, and
  `refactoring_db`.
- MultiRAG RRF/fusion trace is exposed by the shared runner and UI.
- The literature corpus is not finalized.
- Jina and legacy Windows/Hugging Face configurations remain available but are
  not the current final baseline.

## Next Recommended Steps

1. Freeze the baseline configs, prompts, model digests, manifests, and evaluation protocol.
2. Run the frozen Direct/RAG/MultiRAG batch evaluation matrix.
3. Preserve the production builder report and smoke report with experiment
   outputs.
4. Add `literature_db` only after an approved, versioned retrieval manifest.
5. Keep ontology, GraphRAG, routers and rerankers as separate future work.
