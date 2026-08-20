# Legacy cleanup report

## Scope and method

This cleanup was limited to candidates already listed in
`cleanup_candidates.md`. Every candidate was checked for Python imports,
script/CLI and documentation references, tests, a canonical replacement, and
replacement coverage. Fine-tuning paths and behavior were excluded from the
cleanup.

## Removed components

### Failing legacy inference script

Path: `scripts/inference/generate.py`
Area: inference CLI
Reason: always exited with a legacy-navigation message and performed no
inference.
Canonical replacement: `python -m llm_ontology.experiments.smoke` for the
Direct/RAG/MultiRAG baseline; `scripts/evaluation/run_inference_eval.py` for the
separate HF evaluation workflow.
References checked: repository-wide imports, script names, README, docs, and
tests. Only the legacy pointer module/test and historical fine-tuning design
note referenced it.
Tests covering replacement: `tests/experiments/test_smoke_runner.py` and
`tests/inference/test_rag_stage3_runner.py`; the evaluation command is covered
through the evaluation test suite.
Risk: low. External callers now receive a missing-file error instead of a
deliberate failing pointer. The protected historical note under
`docs/finetuning/` was intentionally not edited.

### Legacy inference message module

Path: `src/llm_ontology/inference/generate.py`
Area: inference compatibility API
Reason: contained only the navigation message and two functions that always
raised `RuntimeError`; no production caller imported either function.
Canonical replacement: `llm_ontology.inference.experiment_runner` and the
canonical smoke CLI.
References checked: all Python imports and symbol references for
`generate_text`, `generate_predictions`, and `LEGACY_GENERATE_MESSAGE`.
Tests covering replacement: shared runner, canonical prompt, retrieval, and
smoke-runner tests.
Risk: low; only unsupported external imports can be affected.

### Failing legacy evaluation script

Path: `scripts/evaluation/evaluate.py`
Area: evaluation CLI
Reason: always exited with a navigation message; it did not calculate metrics
or run a model.
Canonical replacement: area-owned `run_inference_eval.py`,
`compute_eval_metrics.py`, `build_eval_report.py`, and
`run_full_evaluation.py`.
References checked: repository-wide CLI/docs references and tests. Only the
pointer-only test and historical protected design note used the deleted path.
Tests covering replacement: `tests/evaluation/test_metrics.py` plus the
evaluation/inference orchestration tests exercised by the full suite.
Risk: low; unsupported external shell commands must migrate to a real command.

### Pointer-only compatibility test

Path: `tests/test_legacy_entrypoints.py`
Area: tests
Reason: asserted only that the two removed commands failed and printed
navigation text; it did not protect model, prompt, retrieval, or evaluation
behavior.
Canonical replacement: behavior tests for the canonical runners and evaluation
components.
References checked: test discovery and repository-wide references.
Tests covering replacement: `tests/experiments/test_smoke_runner.py`,
`tests/inference/test_rag_stage3_runner.py`, and
`tests/evaluation/test_metrics.py`.
Risk: none to runtime behavior; two intentional-failure assertions are gone.

## Candidates intentionally kept

- All files under `src/llm_ontology/finetuning/`, `configs/finetuning/`,
  `scripts/finetuning/`, `tests/finetuning/`, `docs/finetuning/`, and
  `artifacts/finetuning/`: protected active research area.
- Root evaluation and training wrappers: still referenced by runbooks and may
  be external automation surfaces; several are also fine-tuning-adjacent.
- `scripts/inference/run_ollama_baseline.py`,
  `src/llm_ontology/inference/ollama_baseline.py`, and their config: they use
  fine-tuning dataset/prompt helpers, so uncertainty triggers `KEEP`.
- Evaluation metrics/report API pairs: both contracts are test-covered and
  output equivalence has not been demonstrated.
- Standalone embedding config: retains a provider-check role and there is no
  explicit config composition/precedence contract.
- Direct/RAG/MultiRAG templates and `rag_v2` cells: may reproduce distinct
  controlled research phases; no publication/run inventory proves redundancy.
- Environment lock/UI status implementations: live reporting and frozen lock
  validation are semantically different.
- Benchmark runner versus shared experiment runner: no adapter and prompt/output
  equivalence proof exists yet.
- Compatibility model loader: protected fine-tuning API and external import
  surface.

## Result

Deleted source/CLI files: 3.
Deleted test files: 1.
Total deleted files: 4.

No active Direct/RAG/MultiRAG runner, benchmark, dataset, retrieval, evaluation
implementation, config, or fine-tuning component was deleted.
