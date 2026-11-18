# Project map

## Active evaluation boundary

| Component | Responsibility |
|---|---|
| `scripts/benchmarks/run_testing_matrix.py` | Methods2Test matrix entry point |
| `scripts/benchmarks/run_refactoring_matrix.py` | Mixed SWE/MaRV/ML4Ref matrix entry point |
| `benchmarks/testing_matrix.py` | Testing plan, prompt freeze, dispatch, resume, reporting |
| `benchmarks/refactoring_matrix.py` | Refactoring plan, prompt freeze, dispatch, reporting |
| `benchmarks/matrix_support.py` | Internal persistence, locks, transport and prompt helpers |
| `benchmarks/methods2test_selection.py` | Model-free Methods2Test selection and reference preparation |
| `benchmarks/methods2test_execution.py` | Source review and repeated execution |
| `benchmarks/methods2test_metrics.py`, `methods2test_statistics.py` | Coverage, outcomes and paired statistics |
| `benchmarks/refactoring_prepare.py`, `refactoring_execution.py` | SWE checkout/QA and operation/build/test evaluation |
| `benchmarks/refactoring_context.py`, `refactoring_structural.py` | Context-aligned Java units and concrete-target-only structural scoring |
| `benchmarks/refactoring_candidates.py`, `refactoring_mixed_prepare.py`, `refactoring_cohort.py` | Audited reservoir, 100-task quota release and deterministic filtered subsets |
| `benchmarks/java_execution.py`, `evaluation/coverage_runner.py` | Bounded Java/Jupiter execution and JaCoCo |
| `benchmarks/evaluation_generation.py`, `evaluation/hf_inference.py` | Existing local model generation primitives |
| `evaluation/experiment_log.py` | Shared inference/UI/retrieval trace records |

Only the two matrix modules expose eval CLIs. Helpers are not independent
benchmark workflows. Outputs are owned by the corresponding matrix under
`artifacts/evaluation/runs/`.

## Other project areas

- [`thesis_materials/`](../../thesis_materials/README.md): writing-oriented
  methodology reports and archived handcrafted skills/AGENTS results. Historical
  source snapshots are evidence, not additional supported runnable protocols.

- `datasets`, `ingestion`: source data preparation, identity, manifests and audits.
- `finetuning`, `models`: training and local model/adapter loading/provenance.
- `retrieval`, `vectorstore`, `providers`: embeddings, existing index access and RAG.
- `inference`, `approaches`: shared prompts, structured boundaries and generation.
- `ui`: interactive demonstrations and diagnostics, not experiment evaluation.

Training checkpoints, datasets and RAG indexes are preserved independently of
evaluation lifecycle. Dataset-only handcrafted fixtures can remain as explanatory
source material, but there is no active smoke evaluator for them.
