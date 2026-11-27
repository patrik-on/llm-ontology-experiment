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
- **D2 proposals.** The model picks a template from a closed list (`rules.TEMPLATES`), its
  parameters, an exception and a message; `rules.render` turns it into SHACL deterministically. No
  free-form SHACL runs. `verify.verify` checks: loads, vocabulary, flags the triggering answer, no
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
```

Checks: `python -m pytest -q tests/repair` (scripted model; needs the `repair` extra).

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
