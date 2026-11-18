# Mixed refactoring v3: implementation and data-readiness receipt

**Historical v3 admission policy, superseded by [v4 contextual scoring](refactoring_context_v4_2026-11-13.md).
The current v4 cohort has 100 accepted tasks. The 35-task result below records the
older isolated-change gate and is not the current dataset-readiness status.**

Date: 2026-11-13. **Status: IMPLEMENTED / COHORT_NOT_READY.**
The approved 100-task dataset has NOT been released. There is no model result,
training run, new retrieval index or generated answer in this work.

## What changed

The existing refactoring entry runner and configuration were extended, not
replaced by a third eval workflow. Internal modules now handle candidate discovery,
whole-file materialization, target-bound RefactoringMiner events, deterministic
source/type-stratified selection, source/operation filters, quota-gated release,
structural-only evaluation and separate SWE project metrics. The Methods2Test
runner, training data, model adapters, RAG corpora/indexes and skill files were
not changed. Existing dirty repository changes were preserved; no commit/push.

Raw ML4Ref operation parsing now recognizes all six selected types and gives
compound names precedence over their simple substrings. The Java bridge still
uses installed RefactoringMiner 3.0.10, now also exporting left/right CodeRanges.
The local Maven tool was rebuilt successfully. No new library was needed.

## Completed measured preparation

Discovery: `artifacts/evaluation/refactoring-mixed-discovery-v1/discovery.json`.
The private reservoir contains **956 distinct candidate pairs**: 56 MaRV held-out,
both-votes-positive pairs and 900 ML4Ref pairs (150 per requested type), after the
initial exact-code/commit and duplicate screen. Raw discovery scanned 46 eligible
archives before reaching its reservoir caps. This is NOT an exhaustive scan of
all 11,150 raw archives, nor a count of independent commits.

After full-file materialization, isolated-event admission, exact prompt/output
budgets and actual reference/negative-control QA, the completed preparation
`artifacts/evaluation/runs/mixed-pool-qa-v3-final-20261113/pool-preparation.json`
accepted **35 non-SWE tasks**, all with passing reference/no-op/syntax/target
controls. Their private references, detector events, QA checks, prompt sizes and
hash identities are under that run's `preparation/` directory.
The earlier completed `mixed-pool-verified-20261113` preparation had the same 35.

| Source | Operation | Approved | QA accepted | Deficit |
|---|---|---:|---:|---:|
| MaRV | Extract Method | 9 | 4 | 5 |
| MaRV | Rename Method | 9 | 1 | 8 |
| MaRV | Rename Variable | 9 | 1 | 8 |
| MaRV | Remove Parameter | 8 | 1 | 7 |
| ML4Ref | Extract Variable | 10 | 4 | 6 |
| ML4Ref | Inline Variable | 10 | 10 | 0 |
| ML4Ref | Rename Parameter | 10 | 7 | 3 |
| ML4Ref | Rename Class | 10 | 5 | 5 |
| ML4Ref | Parameterize Variable | 10 | 0 | 10 |
| ML4Ref | Replace Variable With Attribute | 10 | 2 | 8 |
| **Non-SWE total** | | **95** | **35** | **60** |

The pre-QA screen also found 16 additional Inline Variable references beyond its
quota of ten; those are reserves, not substitutes for missing types and not 16
additional final-QA passes. The large drop from earlier conversational candidate
counts is real: those were prefilters, not validated executable/refactoring tasks.

**SWE:** the current mixed-pool builder defers expensive project preparation until
all 95 structural-task quotas can be met. It has NOT newly accepted five SWE
cases. Four cases had previously passed the deeper v2 controls; the fifth JUnit
case was rejected because its behavior mutant changed test identities. Those
facts are preserved, not silently upgraded to a ready five-case v3 cohort.
Consequently, this is neither 100 tasks nor a released 40-task mixed benchmark.

## Why cases were rejected, and what this does NOT establish

Most candidates failed the requirement for one isolated, target-bound event
within its declared edit ranges: mixed changes, multiple refactorings, missing
expected detection or edits not fully covered by RM's ranges. Other reasons
include complete-file token budgets, full-file duplicates/exposure and ambiguous
extraction initializers. The exact rejection list is `reference-screen.json` in
the discovery directory. It is diagnostic data, not model performance.

RM ranges are not always a complete edit set. The admission filter deliberately
has false negatives, so zero admitted Parameterize Variable examples does NOT
prove none exist in the original dataset. A real-Miner synthetic regression does
pass a simple parameterization with another existing parameter; necessary comma
insertion/removal is treated as part of changing a parameter list. A tokenizer
lazy-import concurrency issue encountered during materialization was corrected:
initialize it before worker downloads, treat dependency errors as run-level
infrastructure blockers, and retain the original rejection evidence when retrying.
The four affected full files were rechecked after the fix: no dependency errors
remain and the screened source/type counts are unchanged. Evidence:
`artifacts/evaluation/refactoring-mixed-discovery-v1/tokenizer-recheck.log`.

The next data work is to inspect/expand the unused raw reservoir and, if adopted
as a benchmark-design change, construct independently checked minimal references
from mixed developer commits. Current code does not fabricate replacements,
automatically rewrite gold, loosen checks, change quotas, import training cases,
or pretend this bounded failure establishes global dataset unavailability.

Structural-only cases validate full Java syntax, a single allowed file, requested
operation and exact entity identities/ranges. They do not compile a reconstructed
historical project, verify cross-file callers, prove behavior, or establish that a
Rename Class file has the correct filename for project compilation. SWE retains
its separately reported project build/test/mutant checks. Correlated cases from
the same commit/project are possible; no claim of 100 independent commits is made.

## Verification

- Full regression suite: **329 passed, 2 skipped** (74.27 seconds).
- Refactoring-specific suite before the final parameter-delimiter regression:
  **61 passed**; mixed-source suite including that real-Miner regression:
  **15 passed**.
- Scoped Ruff passed; tracked whitespace check passed.
- Actual RefactoringMiner checks include reference acceptance, no-op rejection,
  the wrong same-named target, a second unwanted rename, an unrelated behavior
  change during a rename, exact entity/range binding and parameter-list punctuation.
- Reports distinguish structural successes from SWE project-verified successes;
  non-SWE compile/test values are null, with a separate project denominator.
- Offline N/all previews make zero writes/provider calls and explicitly report
  `generation_allowed=false` until all quotas are released.
- No 100-task manifest was written. No model generation, training, embedding
  generation or index rebuild was performed. A passing parser/detector test is
  not proof of semantic equivalence.
- Final preparation and the tokenizer recheck have ended; no background
  refactoring preparation/detector process was left running.

Some intermediate QA preparations were stopped while fixing the evaluator. They
are preserved as diagnostics, not usable selections. Source/tool identity changes
require a NEW run ID; do not reuse an interrupted or stale preparation directory.
The runbook is [refactoring_matrix_v1.md](refactoring_matrix_v1.md).
