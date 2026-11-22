# Mixed-source refactoring matrix (current protocol v5, ontology arms)

The only refactoring entry point remains `scripts/benchmarks/run_refactoring_matrix.py`.
Configuration stays `configs/benchmarks/refactoring_matrix_v1.json`; the protocol
is `mixed_refactoring_ontology_v5`. Use NEW run IDs; v4 runs are reproduced from their
original commit. Methods2Test is unchanged.

## Arms (v5)

`qwen_base`, `onto_project`, `skills`, `skills_onto` and `rag_single` run on Ollama;
`ft_refactoring` (adapter `b2_refactoring_v3`), `ft_v3_onto` (`b2_refactoring_v3` + block)
and `ft_onto` (`b2_refactoring_onto` + block) run on HF. `rag_multi` is gone. The block is
built at freeze from public inputs only (`before`, operation, target lines, request) by
`ontology.refactoring_context`, stored in `cases/<id>/ontology/`, and inserted by
`ontology.with_ontology` after the contract and any skill text, the same function the
`v3_onto` training data uses. Each FT arm re-hashes its own `hf_identity/<adapter>.json`
before loading, and the ledger compares the string the tokenizer received with the frozen
prompt. The report tests only the predeclared `primary_pairs` (Holm across them) and
gives the A−B difference in percentage points; cross-backend pairs are descriptive.

## Scope and endpoint

**MaRV and ML4Ref use contextual Java excerpts, not necessarily full original
files or pure single-change commits. Score ONLY the requested concrete
refactoring operation and target. Other changes/detected operations do not
invalidate that endpoint and are not independently scored.**

SWE retains the whole original production file, parent project builds/tests and
its strict behavior-mutant controls. Reports separate structural success from
SWE project-verified success; neither is a proof of semantic equivalence.
Do not compare v4 success rates directly with the earlier v3 isolated-change gate.

## Cohort and release gate

| Source | Operation | Required |
|---|---|---:|
| SWE | Extract/Inline Method, project validated | 5 total |
| MaRV | Extract Method | 9 |
| MaRV | Rename Method | 9 |
| MaRV | Rename Variable | 9 |
| MaRV | Remove Parameter | 8 |
| ML4Ref | Extract Variable | 10 |
| ML4Ref | Inline Variable | 10 |
| ML4Ref | Rename Parameter | 10 |
| ML4Ref | Rename Class | 10 |
| ML4Ref | Parameterize Variable | 10 |
| ML4Ref | Replace Variable With Attribute | 10 |

`data/validation/refactoring_mixed_v1/manifest.json` is released only after all
100 cases pass their applicable reference, budget and negative-control gates.
Before release, all generation is blocked, including smaller/filtered runs.
Default after release: 100 cases x 8 arms = at most 800 generation calls.
Preparation itself makes ZERO model-generation calls.

Current receipt: [v4 context preparation](../archive/evaluation/refactoring_context_v4_2026-11-13.md).
The [v3 receipt](../archive/evaluation/refactoring_mixed_v3_2026-11-13.md) records an earlier policy and
is NOT the final availability count under this corrected protocol.

## Context construction and concrete targets

1. Read held-out positive-vote MaRV records and unused/raw ML4Ref pairs. Keep
   project/archive/member/commit provenance. Screen exact normalized code and
   commits against actual train, validation/checkpoint-selection and stored RAG
   pairs from BOTH domains. Do not rebuild training data or retrieval indexes.
2. MaRV: acquire the actual full file at the pinned commit's first parent and at
   the pinned developer commit. Raw diff snippets are not presented as code.
   Full historical files are preparation inputs; their length is NOT a reason
   to reject a much smaller model context.
3. Detect the original event with pinned RefactoringMiner 3.0.10. For MaRV, match
   its supplied target description (reject ambiguous/mismatching matches). For
   ML4Ref, declare a deterministic concrete event of the labelled type using
   original position/description order. Never select based on model performance.
4. AST-select complete target members and related locations. Retain nearby
   members (one neighbor on each side), class fields, original class/ancestor
   headers, package and imports. Union logical before/after member identities so
   counterparts and added/removed/renamed methods stay aligned. Rename Class can
   retain a whole target class. Do not sever expressions, method bodies or braces.
5. Re-run Miner on the resulting before/after contexts and require the SAME
   selected target description/entity. Reject lost or ambiguous targets. Original
   and context sizes, source locations, full files and detector events remain in
   preparation evidence. Excerpts preserve original class headers; they are Java
   syntax units, not claims of independent compilation or complete dependencies.
6. Exact local tokenizer checks apply to final base/skills context prompts and
   the reference JSON output. No arbitrary truncation, generated filler code,
   reference-body prompt leakage or output repair. Initialize the tokenizer once
   before concurrent downloads; missing dependencies are infrastructure blockers.

The scored identity pins the original path, primary declaration/expression
location and original entity. Requested new names are checked where applicable;
incidental reference-use lists and unrelated resulting signatures are not an
exact-gold-output requirement. Extract Variable additionally checks the precise
requested initializer expression, not merely whether some expression was assigned
to the requested new variable name. No-op and wrong-target changes remain failures.

The legacy `within_scope` purity diagnostic is not the active admission/scoring
gate. Tests deliberately accept the requested operation alongside another rename
or behavior change while NOT calling that behavioral correctness. A change of
only the wrong target still fails.

## Model-free controls

Every non-SWE case must pass actual reference detection, no-op rejection, invalid-
Java rejection and mismatching-target-identity rejection. Real-Miner regression
checks also cover an actual wrong method/parameter, unrelated additional changes,
multiple detected events, aligned contextual neighbors, parameter-list delimiters
and the wrong extraction expression with the same requested variable name.

SWE additionally requires original tests twice, gold compilation/tests twice,
matching nonempty individual Surefire identities/statuses and a compiled behavior
mutant killed twice without changing test identities/skips. Missing dependencies,
timeouts, changed test sets and compile failures are not killed mutants. JDKs,
commands, scope and source/tool hashes are explicit. No gold test/build files are
imported into the original parent checkout. The previously rejected JUnit control
is not counted as a pass; a different declared candidate is prepared instead.

## Commands (WSL, repository root)

```bash
# Preview, no providers/builds/writes; includes generation_allowed status.
.venv_wsl/bin/python scripts/benchmarks/run_refactoring_matrix.py \
  --run-id context-preview --dry-run

# Full cohort preparation: downloads/source detection/builds, NO model answers.
.venv_wsl/bin/python scripts/benchmarks/run_refactoring_matrix.py \
  --run-id NEW_CONTEXT_POOL_PREPARATION --prepare-pool

# AFTER full-cohort release only (current release: pool run mixed-context-pool-v5-20261121;
# current frozen run: refactoring-matrix-20261121, all 100 cases):
.venv_wsl/bin/python scripts/benchmarks/run_refactoring_matrix.py \
  --run-id context-n20 --cases 20 --prepare-only
.venv_wsl/bin/python scripts/benchmarks/run_refactoring_matrix.py \
  --run-id context-all --cases all --freeze-only
.venv_wsl/bin/python scripts/benchmarks/run_refactoring_matrix.py \
  --run-id context-marv-rename --source marv --operation 'Rename Variable' \
  --cases all --prepare-only
```

Omitting a safe mode permits actual generation/evaluation. `--prepare-pool` cannot
be combined with cohort size/source/operation filters. Filtered runs default to
all matching released cases. N uses deterministic round-robin source/type strata
and stable SHA-ID order. N below the number of strata cannot cover every type.
All eight model arms receive the SAME tasks, one attempt each, no retry/repair.

## Freeze, results and limits

Existing exact model/adapter/index/provider identities, train-only RAG,
pre-generation prompt freeze, exclusive charged dispatch ledger, cross-matrix GPU
lock and serial GPU loading remain. The existing index is read, never rebuilt.
No source/tool/config drift, changed cohort or partial preparation is silently
resumed. Use fresh run IDs; historical evidence is not rewritten.

Each response is exactly one JSON object containing `file_path` and the COMPLETE
supplied context unit in `refactored_code` (whole file for SWE). Duplicate/extra
keys, wrong paths, empty/non-string or truncated output and Markdown are rejected.

`reports/aggregate.json` and `reports/summary.md` report target-bound structural
success by source AND operation, plus separately SWE project-verified success and
its own denominator. Non-SWE build/test fields are null, not failures/passes.
`verified_success` stays false for structural-only cases; the common paired
comparison uses `structural_success`. Pending/infra/malformed cells stay in the
planned denominators. Extra changes are unscored, NOT certified safe or correct.

Cases can be correlated by project/commit. Selection is a bounded convenience
reservoir, not a random census of all raw archives. Exact code/commit screening is
not a near-clone or model-pretraining contamination certificate. Context scoring
does not check missing cross-file callers or filename/project consistency after
Rename Class; syntax acceptance is not project compilation.
