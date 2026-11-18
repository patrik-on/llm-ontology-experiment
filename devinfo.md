# Current project handoff

There are exactly two evaluation entry points:

1. `scripts/benchmarks/run_testing_matrix.py` — Methods2Test systems/skills matrix.
2. `scripts/benchmarks/run_refactoring_matrix.py` — mixed SWE + MaRV + ML4Ref refactoring matrix.

Use the runbooks in `docs/evaluation/`. Do not restore retired full-evaluation,
TestBench, smoke or earlier five/hundred-case pilot runners or their outputs.

## Boundaries

- Keep training/model provenance, raw/processed datasets, index contents
  separate from evaluation cleanup.
- `matrix_support` contains only helpers used by the current matrices. Selection,
  statistics, source review, HF inference and Java execution helpers have no CLI.
- No training, index rebuild, generated-answer repair or retries in either matrix.
- Preserve source/model/tool/input hashes and exact actual prompts before dispatch.
- The shared GPU lock prevents concurrent matrices from owning the local models.
- Preparation QA is not model performance. Current retained runs have zero calls.
- Local process guards are not an OS security sandbox; keep existing execution
  review and trustworthy testcase-count checks.

## Outputs

Writing material lives in [thesis_materials/](thesis_materials/README.md):
methodological explanations, curated reports and historical handcrafted evidence.
It is not a third evaluation protocol, training source or RAG input. Historical
skills/AGENTS experiments are separate from current matrix scores. Their raw
evidence is local/Git-ignored; active matrix runs stay in the namespace below.

Only `artifacts/evaluation/runs/` holds evaluation runs. Current retained roots
(same list as the README): `testing-matrix-preparation-check-20261113`,
`mixed-context-pool-v4-20261113` and `refactoring-context-v4-ready-20261114`. Their zero-dispatch source freezes are
rebuilt explicitly after infrastructure consolidation; no old model scores or
execution logs are rewritten. Earlier explored Methods2Test IDs remain excluded
through the active matrix configuration, without keeping old model answers.

Dataset audits, model/checkpoint metadata, RAG indexes and tool caches are not
additional evaluation results.

## Machine-specific paths

Configs contain no absolute paths of one computer. They use `${LLM_ONTOLOGY_WORK_ROOT}`
(default `~/benchmark-work`), `${LLM_ONTOLOGY_MODELS_ROOT}` (default `/mnt/c/models`)
and `${LLM_ONTOLOGY_DATASETS_ROOT}` (default `/mnt/c/datasets`), expanded by
`llm_ontology.core.paths.expand_placeholders`. See `.env.example`.
