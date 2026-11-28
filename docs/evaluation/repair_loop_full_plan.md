# Repair loop C / D1 / D2 on the full refactoring matrix (plan, 2026-11-28)

Goal: run the repair loop in the same mode as the refactoring matrix `refactoring-matrix-20261121`
(same 100 tasks, same model and settings, same final evaluator), so the loop's results can be put
next to the matrix arms. The first attempt is the matrix's `onto_project` prompt, so S@1 must
reproduce the `onto_project` arm task by task; S@2 and S@3 show what feedback adds.

D2 is not tuned further to compensate for a small model. Only changes already known to help
all variants (or to remove known defects) go in before the run; then everything is frozen.

## What the pilots showed

- R1 v1 was misleading when the requested method is not in the input (fixed: R1 v2).
- The model ignores feedback: attempt 2 repeated attempt 1 in 6–8 of 10 tasks, attempt 3
  repeated attempt 2 in 9–10 of 10 (`repair-pv-pilot-r1v2-20261127`). The repair prompt shows the
  whole previous answer and says "Keep everything else unchanged".
- With R1 v2, the handwritten rules reported the main error in all 29 failed Parameterize
  Variable answers (pilot + development set), so D2 had nothing to add there.
- The fact extractor and R2 handle only Parameterize Variable; for every other operation D1 and
  D2 would get no rule reports.

## Changes before the run

P0 – repair prompt, identical for C, D1 and D2 (`repair-feedback-v2`)
- Say first that the previous answer was rejected and why; show the previous answer after the
  feedback, as a reference, not as a template; drop "keep everything else unchanged" in favour
  of "perform exactly the requested operation; do not change unrelated members".
- A repeated answer (identical to an earlier attempt after whitespace normalisation) is marked
  in the next feedback ("attempt k is identical to attempt j and was rejected again").
- Quick check: attempt 2 for the 10 pilot tasks, C and D1 (20 calls), repetition rate before/after.

P1 – rules and facts for every operation
- Request parsing for all RefactoringMiner descriptions in the matrix (Extract/Inline Method,
  Rename Method/Variable/Parameter/Class, Remove Parameter, Extract/Inline Variable, Replace
  Variable With Attribute, Parameterize Variable).
- R1 (scope, modifiers, requested method present) for every operation; members named in the
  request are outside the scope check. R2 stays Parameterize Variable only. No new
  operation-specific D1 rules (D1 stays the handwritten base we already have).
- D2 catalogue: unchanged (c2); for other operations the model can still answer none or revise
  R1. D2 is measured as is.
- Fix `analysis_prompt_version` in the config (it still says v2).

P2 – loop over the whole matrix
- `RefactoringTask` over all structural tasks of the matrix (95 ml4refactoring + MaRV tasks);
  the 5 SWE project tasks need the project build of the matrix and are reported separately
  (first: excluded and listed, as their evaluator is the project test run).
- Verification pool from the stored matrix outputs of all 8 arms (labels: final evaluator,
  development use, stated in the methodology), excluding the trigger task as before.
- Sanity check before the run: S@1 per task equals the matrix `onto_project` result.

P3 – run and comparison
- One run, fixed order, max 3 attempts, one analysis per variant and task, D2 frozen at the
  end. Report: S@1..3 per variant and per operation, McNemar D1 vs C and D2 vs D1, costs, D2
  proposals; next to the matrix arms (qwen_base, onto_project, skills, rag, fine-tuned).
- Cost estimate: ~45 failed first answers x 3 variants x (2 repairs + 1 analysis) + 100 first
  answers, roughly 500 calls, 4–6 h.

## Known limits (stated, not fixed)

- The 10 pilot and 20 development Parameterize Variable tasks shaped R1 v2 and the prompts;
  10 of them are in the matrix, so for Parameterize Variable the run is not independent.
- 10 tasks per operation: per-operation differences are descriptive; McNemar on all tasks.
- One seed, temperature 0; no variance estimate.
- Diagnoses are checked for form, not meaning; a manual sample is reviewed afterwards.
- The testing matrix (test generation) has no loop adapter yet; out of scope for this run.

## Decisions after the small tests (2026-11-28)

- **First attempt reused from the matrix** (`--reuse-first-attempt`): the loop's first-attempt prompt is
  identical to the matrix `onto_project` prompt for all 95 tasks, but regenerating it reproduced the
  stored answer in only 8 of 10 pilot tasks (Ollama is not bit-exact at temperature 0). Reusing the stored
  answer makes S@1 equal to the matrix arm by construction and saves 95 calls; the report checks it.
- **Repair prompt stays v1** (plus one line when an answer repeats an earlier attempt). Attempt 2 on the
  10 pilot tasks: v2 text changed repetitions from C 8 → 6 and D1 6 → 6 of 10 and lost D1's one success;
  v1 with repair temperature 0.7 gave C 8 → 6, D1 6 → 6, success 1 → 1. Neither is a clear gain, so the
  run keeps temperature 0 (`--repair-temperature` and `--feedback repair-feedback-v2` remain available).
- **Public checker fix**: the checker compared detected events with the whole request, but Extract
  Variable requests carry a second line ("Extract exactly this original expression: ..."), so 34 correct
  Extract Variable outputs were rejected. It now compares with the first line.
- **SWE project tasks** (5) are not in the run: their evaluator is the project build and tests.

## Command (WSL, repository root; Ollama with qwen2.5-coder:7b running)

```bash
P=.venv_wsl/bin/python; R=scripts/benchmarks/run_repair_loop.py; ID=repair-full-c-d1-d2-20261128
A="--operation all-structural --reuse-first-attempt --catalogue c2"
$P $R --run-id $ID $A --build-pool            # already done for this ID (dev_pool.json)
$P $R --run-id $ID $A --check-public-checker  # already done for this ID (public_checker.json)
$P $R --run-id $ID $A --dry-run               # plan: 95 tasks, hashes
nohup $P $R --run-id $ID $A > artifacts/evaluation/runs/$ID/run.log 2>&1 &   # the run; same command resumes
$P $R --run-id $ID $A --freeze-d2             # after the run
$P $R --run-id $ID $A --report-only           # loop_report.md, loop_summary.json
```

Trial on 4 tasks (`repair-full-trial-20261128`): runs end to end over four operations, S@1 equals the
matrix in 4 of 4.
