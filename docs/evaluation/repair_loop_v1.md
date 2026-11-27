# Repair loop C / D1 / D2 (pilot, protocol `repair_loop_c_d1_d2_v1`)

Follow-up pilot on the finished refactoring run `refactoring-matrix-20261121`. Same model,
backend and decoding as `qwen_base` (Ollama `qwen2.5-coder:7b`, temperature 0, top_p 0.9,
seed 42); nothing is trained. Code: `src/llm_ontology/repair/`, config
`configs/benchmarks/repair_loop_v1.json`.

| Variant | Feedback after a failure | Carried to the next task |
|---|---|---|
| C | own answer + RefactoringMiner/parser output + diagnosis | nothing |
| D1 | the same + reports of the handwritten rules (`configs/repair/rules_d1/`) | fixed D1 base |
| D2 | the same + reports of the current D2 version; the analysis may propose one rule change | verified changes only (D2 starts as an exact copy of D1) |

## Protocol

- **Attempt 1 is shared.** One generation per task from the `onto_project` prompt (instruction +
  project-ontology block), handed to C, D1 and D2. All variants repair the same first error.
- **Budget.** At most 3 attempts per task and variant (including the shared one) and one analysis
  call after the first repairable failure. The analysis has the same token limit
  (`analysis_max_new_tokens`) in every variant; only D2 has the extra optional `rule_proposal` field.
  The diagnosis goes into the repair prompt of every variant.
- **Stop.** Only the public checker decides: `FileAnswer` parses, Java parses, not a no-op, and
  RefactoringMiner reports an event whose description equals the request text. `target_event` is
  used only by the final evaluator (`refactoring_structural.evaluate`), which scores the answer
  after 1, 2 and 3 attempts once the loop is over.
- **D2 proposals** (`proposal.py`, prompt version `d2-rule-template-v2`). The analysis prompt
  contains a rule template generated from the active base and the extracted vocabulary: conditions
  (`must_hold`), the relations each reads, exceptions (`except_when`), operations (`applies_when`)
  and active rule IDs. The JSON schema is generated from the same catalogue, so the model sees
  exactly the values the validator accepts. Three answers: `add` (evidence, applies_when,
  must_hold, except_when, message), `revise` (the same plus `target_rule`) and `none` (`reason`;
  `missing_facts` defers the case). `evidence.snippet` must occur in the current answer, and a
  logging condition must quote a logging call. `required_facts` and the SHACL shape are derived in
  code; no free-form SHACL runs. Every variant's analysis prompt also shows the parsed answer with
  line numbers. `verify.verify` checks: loads, vocabulary, flags the triggering answer, no
  new false positive on correct examples, no regression of the modified rule, and at least one
  held-out defective example that the current base does not catch. Examples of the triggering
  task's group are never used. Not enough examples → `pending`; unknown facts → `deferred`.
- **Activation.** An accepted change becomes active at the next task of a different group; the
  current task is repaired with the version it started with. `--freeze-d2` stops all later changes.
- **State.** `<run>/rulebase_d2/ledger.jsonl` is append-only and is the source of truth on resume;
  stored responses are reused, so no call or change is counted twice.
- **Labels.** `--build-pool` labels stored matrix outputs with the final evaluator
  (`label_source = final_evaluator`); manual labels in `configs/repair/manual_labels_refactoring.json`
  override them. Using evaluator labels to accept rules brings gold information into the D2 base;
  this is allowed on the development set only and must be stated in the methodology.

## Commands (WSL, repository root)

```bash
.venv_wsl/bin/pip install -e ".[repair]"
# the finished run must be in artifacts/evaluation/runs/ (Zenodo 10.5281/zenodo.24446129)
tar --zstd -xf refactoring-matrix-20261121.tar.zst -C artifacts/evaluation/runs/

P=.venv_wsl/bin/python; R=scripts/benchmarks/run_repair_loop.py; ID=repair-pv-pilot-YYYYMMDD
$P $R --run-id repair-mechanism-YYYYMMDD --mock      # mechanism check, no model, no Java
$P $R --run-id $ID --check-public-checker            # L5: public checker vs structural_success
$P $R --run-id $ID --build-pool                      # labelled dev examples (after manual labels)
$P $R --run-id $ID --dry-run                         # plan: order, hashes
$P $R --run-id $ID                                   # pilot with Qwen (10 Parameterize Variable tasks)
$P $R --run-id $ID --report-only                     # loop_summary.json, loop_report.md
$P $R --run-id $ID --freeze-d2                       # before any evaluation on new projects
$P $R --run-id repair-d2-replay-YYYYMMDD --replay-d2-from $ID   # only the D2 analysis, on $ID's first answers
```

Checks: `python -m pytest -q tests/repair` (scripted model; needs the `repair` extra).

The replay writes `replay_report.md`, `replay_summary.json`, `manual_review.json` and per case
`cases/<id>/{prompt.txt,raw.txt,result.json,review.md}`; the source run is not changed. Fill
`manual_review.json` (`diagnosis_fits`, `condition_fits_error`) and run the same command again:
stored responses are reused and the table counts the reviewed cases.

### R1 v2 and catalogue c2 (2026-11-27)

The first replay showed that in 8 of 10 pilot tasks the method named in the request is not in the
supplied input, while R1 v1 said "it must keep its name". `configs/repair/rules_d1/refactoring_v2.ttl`
replaces `R1_TargetMethodPresent` with two constraints on new facts (`java_facts` v2:
`lo:targetMethodInInput`, `lo:targetSignatureInOutput`, `lo:requestedSignature`): "declared in the input
but not found in your output" and "not found in the supplied input, and your output does not declare a
method with this signature either". The v1 file and its base hash are unchanged. It is a D1 change, so
it applies to C (shadow), D1 and D2 alike; select it with `--rules-d1`.

`--catalogue c2` (prepared by a person) adds general conditions (`target_method_missing_in_input`,
`requested_signature_missing_in_output`, `variable_kept_local_in_source_method`); a rule may combine at
most two of them (all must hold). `c1` is the first pilot's catalogue. Prompt `d2-rule-template-v3`: a
`none` that claims an active rule already reports the error must cite that report in `covered_by`
(rule ID and text); the validator checks that this rule produced that report for the answer. It cannot
check whether the reason restates the report correctly.

```bash
$P $R --run-id repair-d2-replay-r1v2-c1-YYYYMMDD --replay-d2-from $ID \
      --rules-d1 configs/repair/rules_d1/refactoring_v2.ttl --catalogue c1 --development-cases
$P $R --run-id repair-d2-replay-r1v2-c2-YYYYMMDD --replay-d2-from $ID \
      --rules-d1 configs/repair/rules_d1/refactoring_v2.ttl --catalogue c2 --development-cases
```

With `--rules-d1` the replay recomputes the rule reports on the stored answers (`cases/<id>/rules.json`).
The 10 pilot tasks shaped these changes and are marked as development cases.

## Run directory

```
loop_plan.json  calls.jsonl  dev_pool.json  public_checker.json  loop_summary.json  loop_report.md
rulebase_d2/  versions/v0000.json (= D1) ... vNNNN.json, ledger.jsonl
cases/<id>/shared/attempt-1/       prompt.txt raw.txt generation.json
cases/<id>/<C|D1|D2>/attempt-k/    check.json rules.json [feedback.txt prompt.txt raw.txt]
cases/<id>/<C|D1|D2>/analysis/     prompt.txt raw.txt diagnosis.json [proposal.json]
cases/<id>/scores.json             final evaluator, one entry per distinct answer
```

C also stores `rules.json` (D1 rules as a shadow measurement); its prompts never contain them.

## Limits of the pilot

Only refactoring (Parameterize Variable, 10 tasks) runs with the model. For testing, only the
mechanism is covered (T3 on TTL fixtures); a testing adapter for the loop does not exist yet. With
10 tasks, D2 vs D1 and D1 vs C are descriptive. New projects for the independent evaluation are
chosen before the main run, after freezing D2, D1, prompts and settings.
