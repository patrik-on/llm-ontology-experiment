# Current evaluation handoff

Writing-oriented materials now have a dedicated home:
[thesis_materials](../../thesis_materials/README.md). Start with the
[current evaluation design report](../../thesis_materials/reports/evaluation_design_2026-11-13.md)
and the [historical handcrafted archive](../../thesis_materials/handcrafted_skills/README.md).
This page remains a compact operational/reproducibility handoff.

The supported experiment implementation consists of the
[Methods2Test matrix](../evaluation/testing_matrix_v1.md) and the
[SWE refactoring matrix](../evaluation/refactoring_matrix_v1.md).

Each uses the same eight arms (baseline, ontology block, skill, skill + block,
Single-RAG, v3 adapter, v3 adapter + block, adapter trained with the block). The
full run is 100 cases × 8 arms, one response each, no repair/retry.
Final runs: `testing-matrix-20261122-rag2` and `refactoring-matrix-20261121`; reports in
[docs/results](../results/), replication steps in the root README. Do not report
infrastructure QA as model performance.

Methods2Test measures generated-test validity, execution, focal invocation and
coverage in an extracted-method harness. It does not claim original-project
builds or real-bug detection. SWE refactoring requires the requested operation
on the target method, compilation and stable existing tests; that is not a
universal proof of behavior equivalence.

Reproduction uses source/input/model/tool/index hashes, saved actual prompts,
dispatch ledgers and per-case logs under the relevant run root. Different
Ollama/HF quantization and output backends are explicitly recorded; comparisons
are system-level, not isolated adapter ablations. Source or manifest changes
require a new pre-generation freeze; never silently re-sign completed results.

The old standalone full/smoke/pilot evaluations and their scores are no longer
part of the active project. Training provenance, datasets and index metadata
remain separately available; see the [project map](../architecture/project_map.md).
