# Refactoring N/all and automatic evaluator controls — 2026-11-13

## Implemented

The existing `scripts/benchmarks/run_refactoring_matrix.py` remains the sole
refactoring entry runner. Its config path is unchanged; protocol is now
`swe_refactoring_matrix_v2`. Default remains five cases. No training, generation,
new model, embedding, retrieval index or frozen-run rewrite is part of this change.

- `--cases N`: exact number of accepted cases, up to the static supported pool size.
  All five arms receive the SAME selected cohort. Shortfall blocks generation;
  the script returns 2 rather than silently reducing N.
- `--cases all`: scan the whole supported pool, accept all QA survivors, require
  at least one survivor AND complete pool exhaustion. Generation budget becomes
  five times the actual selected count, not the requested upper bound.
- `--dry-run`: no writes/providers/builds, includes ordered pool IDs, exclusions,
  dataset/audit hashes and budget; `all` labels its budget as an upper bound.
- Exact resume plan/case-count checks remain. Completed accepted/rejected
  preparation evidence can be reused; interrupted partial evidence cannot.

## Pool and explicit limits

Existing SWE data: 1,099 records. Existing overlap audit flags 125 records (PMD).
After those flags, 974 are candidates across all refactoring types, not a certified
unseen holdout. The existing single-file evaluator supports Extract/Inline only:
451 before path filtering, **224 single-production-file candidates** after it.
The exclusion breakdown is 125 overlap flags, 523 unsupported operations and
227 non-single-production-file cases. Five known controls lead the order, followed
by official dataset order. No selection observes model performance.

55 of these 224 candidates request Java 21, which is not installed/mapped on the
current host. Those are rejected before fetching, never silently run on Java 17.
Other failures may be absent Maven root POM (Gradle/Ant-only), failed historical
dependencies/builds, timeouts, ambiguous method overloads, insufficient tests,
reference operation mismatch, too-large prompts/outputs or surviving mutants.
Thus 224 is NOT the number of operational evaluation cases. Cross-file Move,
Extract-and-Move, Move-and-Inline and Move-and-Rename are not newly supported.

New candidates use the full root Maven reactor unit-test command; known-five
overrides retain their predeclared focused test suites. Actual command/scope is
stored per case and listed in final reports. This is not a claim of running all
integration tests or proving semantic equivalence. Do not execute dataset-provided
shell command strings; repository ownership and JDK mapping are explicit config.

## Per-case gate before acceptance

1. Require unflagged audit membership and the current audited dataset hash.
2. Fetch exact developer commit/first parent; compare the complete original file
   with the parent checkout. No build/test files are imported from the gold commit.
3. Count complete base/skills prompts and gold JSON output with the local exact
   tokenizer. Reject over-budget files rather than truncate or repair.
4. Build/run original tests twice in fresh archives; require stable individual
   test identities/statuses, nonempty valid fresh Surefire results and exit status.
5. Apply gold to parent, detect the requested RefactoringMiner 3.0.10 operation
   bound to path/class/method/location, compile/test twice and require stable passes.
6. Reject lexical no-op; reject deliberately invalid Java through compilation.
7. Require a compiled behavior mutant to fail the SAME original test identity
   multiset twice, with unchanged skips and matching individual failed outcomes.
   Known controls keep predeclared changes. Other cases try up to eight deterministic
   AST mutations of changed/new methods within the gold refactored-method context,
   replacing a body with an unconditional AssertionError. Unchanged/unrelated
   methods are not candidates. Persist every tried mutant and outcome.

A syntax/build error, changed/missing test set, timeout or infrastructure problem
does not count as killing the behavior mutant. A killed mutant establishes some
test sensitivity only; it is not broad mutation coverage or a proof of equivalence.

After acceptance, existing freezing still checks actual HF/model/adapter/index
identities, stale FT/RAG audit inputs, exact RAG evidence and prompt budgets,
source snapshots and frozen hashes. A freeze failure blocks generation, with no
silent RAG-to-baseline fallback or output-driven cohort replacement.

## Verification

- Full regression suite during implementation: **311 passed, 2 skipped**.
- Final expanded refactoring-specific suite: **47 passed**.
- Repository-wide Ruff: passed.
- Offline numeric-six and all-pool dry runs: covered by tests, no runtime/writes.
- Regression coverage includes unchanged-test failure requirements, compile errors,
  surviving/unstable mutants, focused AST mutation, missing Java 21 before fetch,
  all-pool exhaustion, incomplete numeric cohorts, partial interruption and stale
  audited dataset identity.
- Real automatic mutation smoke test against the cached Commons IO IOSupplier
  project: the AST mutant compiled twice, failed one actual regression test on
  each repeat and produced identical individual test signatures. Evidence:
  `artifacts/evaluation/runs/refactoring-pool-v2-qa6-20261113/automutation-smoke/`.
- Bounded model-free preparation (`--cases 6 --prepare-only`) was deliberately
  stopped after **four fully accepted cases and one completed rejection**, during
  the next Checkstyle baseline build, rather than scanning the whole remaining
  pool as part of implementation verification. The new checks correctly rejected
  the known JUnit candidate because its compiled behavior mutant changes the
  test identity multiset (extra initialization-error test entries), even though
  both repeats fail. Controls were not weakened to recover the previous five.
  No `selection.json` was released, no model was called, and this diagnostic run
  is NOT an execution-ready six-case cohort. Partial evidence is preserved; use a
  NEW run ID for execution. Final receipt is `validation_summary.json` in that run.
- The entire 224-case pool was NOT built or certified operational. Real Java
  evidence establishes the completed controls and the automatic mutation smoke;
  larger N/all selection/shortfall/exhaustion behavior is regression-tested.

## Commands (WSL from repository root)

```bash
# Safe preview, no models/builds/writes:
.venv_wsl/bin/python scripts/benchmarks/run_refactoring_matrix.py \
  --run-id refactoring-n20-v2 --cases 20 --dry-run

# Project builds and full evaluator controls only; can fetch Git/Maven inputs:
.venv_wsl/bin/python scripts/benchmarks/run_refactoring_matrix.py \
  --run-id refactoring-n20-v2 --cases 20 --prepare-only

# Alternatively scan all 224 supported candidates, accepting only QA survivors:
.venv_wsl/bin/python scripts/benchmarks/run_refactoring_matrix.py \
  --run-id refactoring-all-v2 --cases all --prepare-only
```

Removing `--prepare-only` permits freezing, generation and evaluation. `--freeze-only`
permits metadata/embeddings but not response generation. A larger N means 5N
generations plus repeated fresh project builds. Keep a new run ID for changed N,
config or controlled source code; existing frozen preparations were not rewritten.

Preserved build workspaces consume disk; timeouts apply per command, not to the
whole preparation. The final sample remains convenience/build/test filtered, with
correlated cases per project/commit and unresolved provenance caveats from the
original overlap audit. A larger N alone does not remove those scientific limits.
