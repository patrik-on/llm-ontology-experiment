# Repository map before reorganization

This document records the repository state before any organizational move in
this task. Classification is based on repository-wide import, CLI, config, test,
documentation, data, and artifact reference searches. A move marked `no` is a
deliberate decision to preserve a useful boundary or avoid changing an uncertain
mixed-ownership component.

## Source packages

| Current path | Purpose | Owning area | Main users | Proposed target | Move |
|---|---|---|---|---|---|
| `src/llm_ontology/core/` | YAML/config helpers, paths, logging, canonical task names, environment lock verification | shared | all CLI and runtime areas | unchanged | no |
| `src/llm_ontology/providers/` | typed external runtime boundaries for Ollama, embeddings, and test mocks | shared | retrieval, inference, UI | unchanged | no |
| `src/llm_ontology/data/` | Methods2Test, MARV, ML4Refactoring preparation, normalized IO, splitting, group safety | datasets | dataset scripts, ingestion, dataset tests | `src/llm_ontology/datasets/` | yes |
| `src/llm_ontology/benchmarks/` | TestBench/SWE-Refactor/smoke contracts and loaders plus TestBench execution/readiness | datasets + experiments | benchmark scripts/tests, smoke validation | unchanged | no — mixed but cohesive benchmark abstraction |
| `src/llm_ontology/finetuning/` | instruction dataset loading and training prompt/model compatibility interfaces | finetuning | training, inference evaluation, tests | unchanged | no |
| `src/llm_ontology/training/` | LoRA/QLoRA execution, readiness, setup, dependency compatibility | finetuning | training scripts and tests | `src/llm_ontology/finetuning/training/` | yes |
| `src/llm_ontology/models/` | lazy HF model/tokenizer/LoRA loading shared by training and model evaluation | shared between finetuning and inference | fine-tuning compatibility layer | unchanged | no — `classification: uncertain` |
| `src/llm_ontology/ingestion/` | dataset manifests, identity/leakage checks, chunking, production corpus and index build | retrieval | retrieval builder, vector store, tests | unchanged | no — explicit retrieval sub-boundary |
| `src/llm_ontology/vectorstore/` | Chroma adapter, collection lifecycle and identity sidecars | retrieval | ingestion, retrieval factory, UI | unchanged | no — explicit persistence boundary |
| `src/llm_ontology/retrieval/` | retrieval config/contracts, factories, single/MultiRAG pipeline, RRF, token budget | retrieval | inference runner, CLI, UI, tests | unchanged | no |
| `src/llm_ontology/approaches/` | Direct/RAG/MultiRAG prompt preparation strategies and context rendering | inference | benchmark runner, inference helpers | unchanged | no — stable strategy boundary; cleanup relationship is uncertain |
| `src/llm_ontology/inference/` | generation clients, prompt formatting, structured output, RAG/shared runners | inference | UI, benchmark runner, retrieval factory, tests | unchanged | no |
| `src/llm_ontology/evaluation/` | prediction IO, testing/refactoring metrics, inference evaluation, coverage, aggregation/reporting | evaluation | evaluation scripts/tests, inference/UI records | unchanged | no |
| `src/llm_ontology/ui/` | Gradio presentation, environment status and interactive adapter | ui | `python -m llm_ontology.ui`, UI tests | unchanged | no |
| `src/llm_ontology/cli/` | manual RAG index/query entrypoint | retrieval | operator CLI, RAG documentation | unchanged | no — public entrypoint |
| `src/llm_ontology/env/` | read-only environment command | shared | operator CLI | unchanged | no |
| `src/llm_ontology/experiments/` | not present in the current commit | experiments | n/a | future experiment orchestration package | no new behavior added in this task |

## Configurations

| Current path | Purpose | Owning area | Main users | Proposed target | Move |
|---|---|---|---|---|---|
| `configs/base.yaml` | shared dataset preparation defaults | shared + datasets | `scripts/data/prepare_data.py` | `configs/shared/base.yaml` | yes |
| `configs/models/` | HF and Ollama model/runtime definitions | shared | finetuning, inference, experiment templates, tests | `configs/shared/models/` | yes |
| `configs/environment/` | reproducibility lock and dependency lock | shared | maintenance check, reproducibility tests/docs | `configs/shared/environment/` | yes |
| `configs/datasets/` | dataset processing and role manifests | datasets | ingestion, index builder, tests | unchanged | no — area is already explicit |
| `configs/finetuning/` | LoRA and task-specific training definitions | finetuning | training code/scripts/docs | unchanged | no |
| `configs/retrieval/` | Chroma, embedding, LLM, Single/MultiRAG runtime | retrieval | CLI, UI, environment command, tests | unchanged | no |
| `configs/embeddings/` | standalone embedding contract | retrieval | documentation/config comparison | unchanged | no — possible consolidation is uncertain |
| `configs/inference/` | standalone Ollama inference definition | inference | Ollama baseline script | unchanged | no |
| `configs/evaluation/` | model matrix and task evaluation runs | evaluation + experiments | evaluation scripts/docs | unchanged | no |
| `configs/benchmarks/` | TestBench and SWE-Refactor settings | datasets + experiments | benchmark scripts/docs | unchanged | no |
| `configs/experiments/` | Direct/RAG/MultiRAG comparison cells | experiments | inference runner/UI/tests | unchanged | no |
| `configs/ui/` | UI composition and defaults | ui | UI service/app | unchanged | no |

## Scripts

| Current path | Purpose | Owning area | Main users | Proposed target | Move |
|---|---|---|---|---|---|
| `scripts/data/` | inspect, prepare, split, and audit datasets | datasets | researchers and dataset docs | `scripts/datasets/` | yes |
| `scripts/training/` | fine-tuning training/readiness/debug commands | finetuning | researchers and runbooks | `scripts/finetuning/` | yes |
| `scripts/benchmarks/` | benchmark inventory, generation, readiness, smoke validation, TestBench execution | experiments + datasets | benchmark runbooks/tests | `scripts/experiments/benchmarks/` | yes |
| `scripts/retrieval/` | production index build and retrieval/runtime checks | retrieval | operators and retrieval docs | unchanged | no |
| `scripts/inference/` | standalone generation/model setup adapters | inference | operators and compatibility tests | unchanged | no |
| `scripts/evaluation/` | evaluation inference, metrics, reports and analyses | evaluation | evaluation runbooks and root wrappers | unchanged | no |
| root script wrappers | compatibility commands for training/evaluation/adapter packaging | mixed | external commands and tests | unchanged | no — `classification: uncertain`, preserve public paths |
| `scripts/experiments/info.md` | experiment-area placeholder documentation | experiments | maintainers | retain and add benchmark subdirectory | no |

## Tests

| Current path/group | Purpose | Owning area | Main users | Proposed target | Move |
|---|---|---|---|---|---|
| `test_data.py`, `test_reproducibility_and_group_splits.py`, `test_smoke_dataset.py` | dataset preparation, role/split/leakage and smoke contracts | datasets | pytest | `tests/datasets/` | yes |
| `test_model_configs.py` | model/training/experiment config integrity | finetuning | pytest | `tests/finetuning/` | yes |
| `test_ollama_embeddings.py`, `test_rag_*`, `test_wsl_runtime.py` | ingestion, vector store, providers, retrieval and runtime | retrieval | pytest | `tests/retrieval/` | yes |
| `test_ollama_client.py` | generation provider contract | inference | pytest | `tests/inference/` | yes |
| `test_metrics.py` | evaluation metrics/report compatibility | evaluation | pytest | `tests/evaluation/` | yes |
| benchmark and TestBench tests | loaders, prompt orchestration and executable evaluation | experiments + datasets | pytest | `tests/experiments/` | yes |
| `test_ui.py` | UI mapping/status/service | ui | pytest | `tests/ui/` | yes |
| architecture/config/import/compatibility/generation tests | cross-area contracts | shared or uncertain | pytest | unchanged | no — avoid artificial ownership |

## Documentation

Current documentation is flat under `docs/`. It covers distinct active areas
but the paths do not reveal ownership. It will be moved with Git history into:

- `docs/architecture/`: system boundaries, repository policy, audits;
- `docs/datasets/`: handcrafted smoke dataset;
- `docs/finetuning/`: design, WSL setup, v2 runbook, adapter downloads;
- `docs/retrieval/`: RAG phases and Ollama embeddings;
- `docs/evaluation/`: v2 evaluation runbook;
- `docs/experiments/`: experiment design/environment, TestBench runbook;
- `docs/thesis/`: reproducible handoff material;
- `docs/ui/`: UI overview.

All links and command paths must be updated after the moves.

## Data and artifacts

| Current path | Purpose | Owning area | Proposed target | Move |
|---|---|---|---|---|
| `data/raw`, `data/processed`, `data/samples` | dataset source/derived/sample layout | datasets | unchanged | no |
| `data/smoke/` | versioned handcrafted smoke cases and Java fixtures | datasets | unchanged | no |
| `data/chroma/` | ignored local persistent vector data | retrieval | unchanged | no |
| `artifacts/adapters/` | LoRA adapter handoff hashes/manifest | finetuning | `artifacts/finetuning/adapters/` | yes |
| `artifacts/checkpoints/` | ignored checkpoint placeholder | finetuning | `artifacts/finetuning/checkpoints/` | yes |
| `artifacts/indexes/` | retrieval index/report placeholder | retrieval | `artifacts/retrieval/indexes/` | yes |
| experiment outputs outside `artifacts/` | generated evaluation/training results | experiments/evaluation | unchanged | no — changing result roots would alter operational behavior |

## Safety conclusion

The planned refactor changes package and documentation ownership paths only. It
does not change dataset content, prompts, model settings, retrieval ranking/RRF,
generation parameters, evaluation semantics, training hyperparameters, or
benchmark methodology. No tracked file is approved for deletion. Suspected
duplicates are recorded separately in `cleanup_candidates.md` and retained.
