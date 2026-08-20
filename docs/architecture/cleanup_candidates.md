# Cleanup candidates

The original reorganization did not delete these candidates. The dedicated
`baseline_v1` cleanup resolved only the explicit failing compatibility
entrypoints documented below. Every remaining candidate still requires
reference proof and is intentionally kept.

## Compatibility model loader

Module: `src/llm_ontology/finetuning/model_loader.py`  
Area: finetuning  
Why it looks duplicated: it re-exports model-loading functions implemented in
`src/llm_ontology/models/loader.py`.  
Possible replacement: direct imports from `llm_ontology.models.loader`.  
Risk: training/debug scripts and external callers currently use the compatibility
path.  
Recommended future action: inventory external imports, migrate callers, then
decide whether the compatibility API is still required.  
Confidence: high that it is a wrapper; low that deletion is currently safe.

## Root command wrappers

Module: `scripts/train_finetuning.py`, `scripts/check_finetuning_ready.py`,
`scripts/run_inference_eval.py`, `scripts/run_full_evaluation.py`,
`scripts/compute_eval_metrics.py`, `scripts/build_eval_report.py`, and
`scripts/check_v2_adapters.py`  
Area: finetuning / evaluation  
Why it looks duplicated: similarly named commands exist in area-specific script
directories.  
Possible replacement: area-owned script paths.  
Risk: runbooks, automation, user shell history, and tests can depend on the root
entrypoints.  
Recommended future action: define the supported CLI surface first; only then
deprecate wrappers with an announced migration window.  
Confidence: high duplication, high removal risk.

## Resolved: explicit compatibility entrypoints

Removed module: `scripts/inference/generate.py`,
`src/llm_ontology/inference/generate.py`, and
`scripts/evaluation/evaluate.py`
Area: inference / evaluation  
Why it looks duplicated: the files identify themselves as compatibility or
navigation entrypoints and direct users to newer commands.  
Possible replacement: `scripts/evaluation/run_inference_eval.py` and
`scripts/evaluation/run_full_evaluation.py`.  
Resolution: the dedicated CLI cleanup removed these always-failing pointers and
their pointer-only test. Canonical replacements remain
`python -m llm_ontology.experiments.smoke` for Direct/RAG/MultiRAG and the
area-owned evaluation commands for HF evaluation. See
`legacy_cleanup_report.md` for reference evidence and retained risks.

## Evaluation compatibility metrics/report path

Module: `evaluation/metrics.py`, `testing.py`, `refactoring.py`, `report.py`
versus `metrics_runner.py`, task-specific `*_metrics.py`, and `report_writer.py`  
Area: evaluation  
Why it looks duplicated: both groups calculate or aggregate task metrics and
render reports.  
Possible replacement: the normalized prediction-IO plus task-specific metric
runner/report writer path.  
Risk: the older API is covered by tests and may encode a different benchmark
contract. Treating it as equivalent without result comparison could change
evaluation semantics.  
Recommended future action: compare schemas and metric outputs on frozen fixtures
before proposing consolidation.  
Confidence: medium.

## Standalone and full retrieval embedding configs

Module: `configs/embeddings/ollama_bge_m3.yaml` and the embedding section of
`configs/retrieval/ollama_bge_m3.yaml`  
Area: retrieval  
Why it looks duplicated: both describe the same embedding provider/model.  
Possible replacement: a shared included embedding config, if the config loader
gains an explicit composition contract.  
Risk: the standalone config is useful for provider-level checks while the full
retrieval config is executable; silent merging could change effective settings.  
Recommended future action: first define config composition/precedence and add an
effective-config equivalence test.  
Confidence: medium.

## Experiment templates and controlled RAG v2 cells

Module: `configs/experiments/{direct,rag,multi_rag}/` and
`configs/experiments/rag_v2/`  
Area: experiments  
Why it looks duplicated: both sets express Direct/RAG/MultiRAG configurations.  
Possible replacement: one versioned experiment-matrix schema.  
Risk: templates and controlled cells may serve different research phases and
methodological contracts.  
Recommended future action: classify each experiment publication/run that uses
them before considering consolidation.  
Confidence: low to medium.

## Environment status implementations

Module: `core/environment_lock.py` and `ui/service.py::EnvironmentStatusService`  
Area: shared / retrieval / UI  
Why it looks duplicated: both inspect runtime, models, dependencies, and index
state.  
Possible replacement: shared typed probes with separate lock-validation and UI
presentation adapters.  
Risk: one verifies a frozen reproducibility lock while the other reports live UI
status; they are not semantically interchangeable.  
Recommended future action: extract only demonstrably identical low-level probes.
  
Confidence: low.

## Benchmark prompt runner versus shared experiment runner

Module: `benchmarks/runner.py` and `inference/experiment_runner.py`  
Area: experiments / inference  
Why it looks duplicated: both orchestrate cases into prompts and model calls.  
Possible replacement: a benchmark orchestrator over the shared inference runner.
  
Risk: benchmark context-level methodology and retrieval experiment records differ;
an unverified merge could alter published results.  
Recommended future action: specify an adapter contract and prove prompt/output
equivalence on frozen cases before migration.  
Confidence: medium.
