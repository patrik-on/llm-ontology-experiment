# Agent guide: llm-ontology-experiment

Master's thesis experiment: Qwen2.5-Coder-7B on Java test generation and
refactoring, comparing baseline, LoRA fine-tuning, Single-RAG, MultiRAG and a
process skill. Read this file first; it lists the only active versions.

## Active entry points (the only two eval runners)

| Task | Runner | Orchestration | Config |
|---|---|---|---|
| Testing (Methods2Test) | `scripts/benchmarks/run_testing_matrix.py` | `src/llm_ontology/benchmarks/testing_matrix.py` | `configs/benchmarks/testing_matrix_v1.json` |
| Refactoring (SWE + MaRV + ML4Ref) | `scripts/benchmarks/run_refactoring_matrix.py` | `src/llm_ontology/benchmarks/refactoring_matrix.py` | `configs/benchmarks/refactoring_matrix_v1.json` |

Shared helpers: `benchmarks/matrix_support.py`; statistics:
`benchmarks/methods2test_statistics.py`, `benchmarks/paired_tests.py`.

## One active version of everything

A version suffix in a name is an identity, not an alternative. Use these:

| Area | Active | Notes |
|---|---|---|
| Testing prompt profile | `inference/prompting/testing_bodies_one_shot_v2.py` | builds on `testing_bodies_v1.py` and `testing_full_class_v2.py` (shared helpers, not separate profiles) |
| Retrieval | `configs/retrieval/ollama_bge_m3_v3.yaml`, `docs/retrieval/rag_v3.md` | `base.yaml` is a mock config for unit tests |
| Adapters | `b2_testing_v2`, `b2_refactoring_v2`, `b1_shared_v2` | trained with `configs/finetuning/training_*_wsl.yaml` |
| HF model config | `configs/shared/models/qwen25_coder_7b_hf_wsl.yaml` | Ollama: `qwen25_coder_7b_ollama.yaml` |
| Skills arm | `configs/skills/{testing,refactoring}/SKILL.md` | pinned, hash-guarded; never edit |
| Fine-tuning scripts | `scripts/finetuning/` | runbook `docs/finetuning/v2_runbook.md` |
| Runtime check | `python -m llm_ontology.env check` | `src/llm_ontology/env/status.py`; there is no UI |

## Do not read unless asked (historical, large or local-only)

- `docs/evaluation/archive/`, `docs/retrieval/archive/`, `thesis_materials/`
  (writing material and historical reports, not code to change)
- `thesis_materials/handcrafted_skills/archive_manifest.json` (4 MB)
- `data/`, `artifacts/`, `benchmarks/` (data and outputs, mostly Git-ignored)
- dated docs `*_2026-*.md` are point-in-time receipts, not current instructions

## Rules

- Runtime is WSL with `.venv_wsl`; machine paths come from `${LLM_ONTOLOGY_*}`
  placeholders (`src/llm_ontology/core/paths.py`, `.env.example`).
- Never change a frozen run, prompt bytes or `SKILL.md`; a changed experiment
  needs a new run ID. One attempt per cell, no retries or repairs.
- Do not add new version files next to old ones. Change the active file, and if
  the old behaviour must stay reproducible, rely on Git history and the frozen run.
- Checks: `python -m pytest -q -rs` and `ruff check src scripts tests`. Tests
  marked `local_data` / `rag` skip when local data or chromadb is missing.
