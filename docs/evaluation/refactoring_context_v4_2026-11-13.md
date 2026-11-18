# Contextual refactoring v4 — preparation receipt

Task started 2026-11-13; completed 2026-11-14. **Status: 100/100 ACCEPTED AND
RELEASED: 5 SWE + 35 MaRV + 60 ML4Ref.** No model answers or training runs were
performed. All five SWE cases passed the deeper original-project controls.

- Released manifest: `data/validation/refactoring_mixed_v1/manifest.json`.
- Human-readable 100-task list: `data/validation/refactoring_mixed_v1/catalogue.csv`.
- Source/type counts: `data/validation/refactoring_mixed_v1/summary.json`.
- Actual current-runner all-case preparation (zero dispatches):
  `artifacts/evaluation/runs/refactoring-context-v4-ready-20261114/`.

## User-directed correction

MaRV/ML4Ref do not need full historical projects or pure whole-file commits.
Retain reasonable surrounding context, and score ONLY the requested concrete
refactoring and target. Other changes/events are not independently scored and
are not a reason to reject the requested refactoring. SWE retains project tests.

This supersedes the v3 isolated-change admission policy. Its earlier 35-task
result measured that overly conservative gate, not the availability under v4.
The [v3 receipt](archive/refactoring_mixed_v3_2026-11-13.md) remains historical evidence.

## Measured source availability

Same bounded initial reservoir: 956 pairs (56 distinct positive-vote held-out
MaRV and 900 ML4Ref pairs, 150 per type). Raw discovery scanned 46 eligible
archives, not the full set of 11,150 archives. Existing train/validation and stored
RAG code/commit screens are retained; training data and indexes were not changed.

AST assembly produced 878 aligned contextual before/after units. Re-running the
actual Miner on those contexts admitted the following preliminary references:

| Source | Operation | Preliminary references | Required / final contextual QA |
|---|---|---:|---:|
| MaRV | Extract Method | 11 | 9 / 9 |
| MaRV | Rename Method | 11 | 9 / 9 |
| MaRV | Rename Variable | 14 | 9 / 9 |
| MaRV | Remove Parameter | 13 | 8 / 8 |
| ML4Ref | Extract Variable | 126 | 10 / 10 |
| ML4Ref | Inline Variable | 135 | 10 / 10 |
| ML4Ref | Rename Parameter | 131 | 10 / 10 |
| ML4Ref | Rename Class | 140 | 10 / 10 |
| ML4Ref | Parameterize Variable | 119 | 10 / 10 |
| ML4Ref | Replace Variable With Attribute | 132 | 10 / 10 |

**All 95 non-SWE quotas passed actual reference/no-op/syntax/target QA and exact
local tokenizer budgets.** Preliminary counts above are NOT extra final-QA
passes and are not counts of independent commits. No model output was used to
choose the cohort. Cases may be correlated by project/commit.

## What context means

`refactoring_context.py` selects complete target members and event-related uses,
retaining neighboring members on either side, fields, package/imports and class/
ancestor headers. The union of logical before/after member identities retains
corresponding context and added/removed/renamed members. Rename Class may keep
an entire target class. There are no blind line cuts or generated filler bodies.

The same specific original event is reidentified after context construction.
Original full files, selected descriptions, source ranges, context sizes, before/
after contexts and detector events are retained. Full historical-file size is
not applied as a model-output budget before selecting context. Syntax parsing
is not a claim that the excerpt has all dependencies for compilation.

`refactoring_structural.py` binds the original primary declaration location/entity
and requested resulting name where applicable, not every incidental use or edit
from the reference commit. Extract Variable additionally pins its exact original
initializer expression. A no-op, only the wrong target, missing requested event
or wrong expression is rejected. The requested event plus another rename or
behavior change can pass THIS endpoint; other edits are unscored, not certified
correct. There are no non-SWE project build/test claims.

## SWE preparation and controls

The original four known cases were freshly re-prepared with the existing strict
checks. The earlier JUnit candidate remains rejected, not restored as a pass.
An attempted Commons Lang replacement (`4949adec...`, ReflectionDiffBuilder)
passed baseline project tests but failed exact target matching: dataset metadata
requested an extraction from setExcludeFieldNames, while Miner detected extraction
of a constructor. Its gold was therefore NOT counted as an accepted SWE case.

Additional Commons IO candidates were screened using the actual detector before
project preparation. Only candidates matching operation, class, method and original
location were prioritized. Completed QA evidence is reusable only with unchanged
case/tool/source identity; interrupted unselected candidates remain diagnostics.
No controls were weakened and no model-generation calls were made.

The successful fifth SWE case is Commons IO `UncheckedFilterReader.skip`, commit
`d269f164b3e24a92cc33d759d8bcf3eedb37f576`. It passed all baseline/reference/
syntax/no-op/compiled-mutant checks. The selected SWE set contains four Extract
Method cases and one Inline Method case. The unused interrupted Checkstyle
attempt and rejected ReflectionDiffBuilder case are not selected tasks.

Each accepted SWE case requires stable original tests twice, matching reference
compilation/tests twice, no-op and invalid-source rejection, and a compiled
behavior mutant killed twice with unchanged test-identity/skip multisets and stable
individual failed outcomes. Maven exit codes alone are not sufficient.

## Evidence and verification

- Discovery, full sources and contexts:
  `artifacts/evaluation/runs/refactoring-context-data-v4-20261113/`.
- Final QA and SWE evidence:
  `artifacts/evaluation/runs/mixed-context-pool-v4-20261113/`.
- Preparation stdout:
  `artifacts/evaluation/context-v4-preparation.log` and
  `context-v4-preparation-resume.log` (interrupted diagnostic attempt retained).
- Real-Miner SWE preflight: `artifacts/evaluation/context-swe-preflight.log`.
- Final full regression: **332 passed, 2 skipped**, 114.04 seconds.
- Refactoring suite: **64 passed** before the last new extraction-expression test.
- Latest mixed-source tests: **18 passed**, including wrong extraction expression
  with the same requested variable name, actual wrong target, unrelated changes,
  multiple events, contextual neighbors and parameter-list punctuation.
- Scoped Ruff and tracked whitespace checks passed.
- Actual `--cases 7 --prepare-only`: ready, 7 selected, zero model calls.
- Actual `--cases all --prepare-only`: ready, 100 selected, zero model calls.
- Actual filtered preview for ML4Ref Parameterize Variable: 10 tasks, maximum
  50 future generation calls, zero actual calls and zero program writes.
- All 100 selected QA receipts passed; the manifest contains 100 unique IDs.
- The final canonical all-case run contains no charged dispatches/model answers.

The two existing entry runners remain the only active workflows. No training,
model-answer generation, new retrieval index or embedding generation occurred.
No commit/push was performed; unrelated existing dirty-tree changes were preserved.

See the current [runbook](refactoring_matrix_v1.md) for N/all, filters, preparation,
freeze and execution commands. Removing safe-mode flags permits actual inference;
it was NOT done during this work. RAG prompt freezing remains a separate explicit
stage using the existing local providers/index, not part of these zero-call scores.
