# Benchmark selection and readiness — 2026-11-12

## Scope

Repository study and primary-source benchmark research, not a completed benchmark reproduction. Baseline inspected: `e020e50a2694586041644bb3831194e32d4fa849`. No model generation, paid calls, external project builds, dependency installation, index rebuilds, or data repairs were performed. Existing user changes were preserved.

## Selected benchmarks

| Task | Selection | Research status | Execution status |
|---|---|---|---|
| Java testing | Defects4J v3.0.1, commit `6d54320e0db5a357f9ab38a8e4d2e5aead7e1c09` | Recommended | Not installed/integrated or pilot-validated |
| Java refactoring | SWE-Refactor, arXiv 2602.03712v1 | Best task fit, conditional recommendation | Provenance/license unresolved; data absent and executable evaluator missing |

Sources checked on 2026-11-12:

- Defects4J: https://github.com/rjust/defects4j/tree/v3.0.1
- Defects4J framework license: https://github.com/rjust/defects4j/blob/v3.0.1/license.txt
- SWE-Refactor paper: https://arxiv.org/abs/2602.03712
- Public SWE copy (not established as author-endorsed): https://github.com/obieda01/SWE-Refactor/tree/40dc9377cfd4b8d420c9b97ad4d35d94f174f154
- Existing TestBench: https://github.com/iSEngLab/TestBench/tree/6d018f543932c381312d168c7c3ba50abc83f748

### Testing: why Defects4J

The release documents 854 active real Java bugs across 17 projects. Fixed/buggy revision pairs allow a stronger oracle than textual reference similarity: the same generated test must compile on both versions, repeatedly pass on fixed code, and expose a genuine assertion/test failure on buggy code. Infrastructure errors are not detected bugs. Framework MIT licensing does not replace individual project licenses.

Use the project's canonical structured JUnit 5 output unchanged. Defects4J's native generated-test execution is JUnit 4 based, so an explicit pinned Jupiter adapter is necessary. Defects4J v3 requires Java 11, timezone `America/Los_Angeles`, SVN and Perl dependencies; local WSL currently provides Java 17, not the required full toolchain. Coverage/mutation interoperability is not yet validated.

Initial metrics: compile rate, positive non-skipped executed-test rate, fixed-code pass rate, real-bug detection rate, flakiness/timeouts/infrastructure failures; report unconditional as well as conditional denominators. Add actual coverage only after executable integration exists.

### Refactoring: why only conditional SWE-Refactor

The paper describes 1,099 real Java changes across 18 projects, including Extract/Move/Inline and compound operations. This matches the intended named refactoring task better than framework migration or performance-polishing benchmarks. The local loader alone does not apply patches, compile candidates, run behavior tests or detect requested operations.

The paper release inspected does not establish an author-confirmed data endpoint. The matching public copy has no verified benchmark-wide license, and its evaluator includes early verification returns and builds that skip tests. Do not execute or trust that harness unchanged. Unresolved licensing is a provenance/reuse question, not a claim that reading public data is prohibited.

Required metrics: valid application, compilation, baseline-qualified behavior tests, requested-operation detection, joint success. Similarity/CodeBLEU is secondary and cannot establish preserved behavior. A no-op must not count as a successful requested refactoring.

## Confirmed local issues

1. Both configured external benchmark roots are missing. Expected case counts in YAML have not been verified against actual release data.
2. The benchmark CLI is direct-only and does not use the full shared `RagExperimentRunner` provenance/structured-output path. It does not enforce the benchmark YAML as an executable protocol.
3. TestBench instructions request Java-only while the canonical prompt requests JSON; its executor receives raw prediction text rather than schema-extracted `generated_tests`.
4. TestBench accepts process exit zero even when no generated tests execute. Require fresh execution reports and a positive non-skipped count.
5. SWE loading turns explicit JSON null into text `None`, blocking valid fallback; granularity, multi-file application and executable evaluation need explicit contracts.
6. Materialized ML4Refactoring-derived data shares 188 exact input/output pairs between train and test. Clean retrieval filtering does not repair trained-adapter exposure.
7. Only the V3 local Chroma index exists; historical baseline/UI paths target a missing older root. Do not silently relabel/rebuild old experiment identities.
8. Smoke generation success and heuristic coverage/refactoring scores are not evidence that generated Java compiled or preserved behavior.

The architecture audit ran 65 targeted tests successfully using existing WSL dependencies. These used fixtures/mocks; no real external benchmark build was validated.

## Preparation sequence, not yet executed

1. Freeze an external-benchmark protocol separately from historical smoke baselines. Preserve the canonical prompt, shared runner and model/index identities.
2. Pin authoritative releases, license notes, revisions and checksums; inspect build scripts before execution. Resolve SWE source provenance before treating it as the paper benchmark.
3. Reserve benchmark projects/commits and code fingerprints against training, validation and actual retrieval content. Mark benchmark manifests non-indexable. Pre-register any clean subset before model outcomes are observed.
4. Provision the reviewed WSL toolchain; use disposable least-privilege workspaces without credentials. A timeout is not a sandbox.
5. Validate real-data schemas and original build/test baselines. For Jupiter, test passing, failing, compile-error, empty, disabled-only and timeout controls. For refactoring, include original/no-op, developer reference, syntax-broken and behavior-changing candidates.
6. Only after model-free controls pass, run a separately authorized small generation matrix through the existing shared runner, then consider the full benchmark.

## Detailed handoffs

- [Repository architecture/data/runtime audit](../architecture/openclaw_repository_audit_2026-11-12.md)
- [Testing benchmark selection](testing_benchmark_selection_2026-11-12.md)
- [Refactoring benchmark selection](refactoring_benchmark_selection_2026-11-12.md)

**Readiness claim:** benchmark selection and investigation are prepared; neither selection is yet end-to-end execution-ready in this repository. Do not present a proposed command, a loader test, or a paper's result as an executed local benchmark.
