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

## Dated correction: SWE-Refactor Zenodo acquisition (2026-11-12)

This additive correction supersedes the earlier missing-data/unresolved-deposit-license findings for SWE only; the preceding investigation remains a historical record. The user-selected source is now pinned to <https://zenodo.org/records/17196850>, DOI **10.5281/zenodo.17196850**, deposited by **anonymous**, with explicit **CC-BY-4.0** record licensing. This establishes a licensed deposit, not independently authenticated paper-author endorsement or blanket licensing of underlying Java projects.

The exact 207,329,781-byte ZIP was downloaded and its published MD5 **f06ee0ce4c8034d57d4d2d1b4c32a24d** matched; computed SHA-256 is **e1bd6eedcdf65c4c6cf4454cf07d3db558cd4ba1706419a409489297f8ea6a65**. Only 10 allowlisted dataset/build-metadata/evaluator-inspection files (67,599,668 bytes) were extracted into the existing configured root, including pure_refactoring_data.json. No old SWE data was present to delete, and reusable adapter/research history was preserved. Newer record 23194601 was noted but not substituted.

Actual local inventory: **1,099 unique cases, 18 projects, six operation types**, 922 atomic/177 compound. All cases load with nonempty before/reference code; three use existing whole-file input fallback. A narrow loader fix prevents explicit JSON null becoming literal None and keeps its fallback flag consistent (the pinned real data has no explicit top-level nulls). WSL adapter/edge tests: **6 passed**; all **1,099 prompt-only records** were prepared and checked without model calls. No upstream scripts, Java builds, installs or indexing were run; canonical prompts, frozen baselines and dataset YAML remain unchanged.

Status is now **DATASET_READY (loading/prompt inspection), EXECUTION_NOT_READY**. Stored metadata is not uniformly successful/complete: two current-compilation flags are false; hasTestC is absent from 1,098 cases; coverage has heterogeneous shapes; 300 commands skip tests and 93 have unmatched quoting. The deposited evaluator retains early success/verification bypasses and test-skipping builds. A safe shared application/evaluator contract, pinned subject checkouts/toolchains, actual baseline/test/operation controls, leakage clearance and controlled three-mode runner integration remain outstanding. Testing benchmark and unrelated audit findings are unchanged.

Full source/license/checksum, selected/excluded asset inventory, schema/counts, caveats and executed verification: [SWE-Refactor Zenodo acquisition](../datasets/swe_refactor_zenodo_acquisition_2026-11-12.md).
