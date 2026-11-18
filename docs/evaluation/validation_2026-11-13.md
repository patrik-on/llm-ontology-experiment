# Current matrix validation (2026-11-13)

Only two evaluation CLIs and two entry scripts remain: Methods2Test testing and
SWE refactoring. Only their current preparation directories remain under
`artifacts/evaluation/runs/`. Legacy pilot/full/smoke frameworks, their configs,
wrappers, temporary scripts and outputs have been removed recoverably from the
active repository. Training, model provenance, datasets and RAG indexes are
separate from this lifecycle.

## Verification

- Full remaining suite: **288 passed, 2 skipped**.
- Ruff across source/scripts/tests: passed.
- Diff whitespace check: passed.
- Both runners: offline dry-run, fresh freeze-only and report-only passed.
- Frozen task prompts: **30/30 byte-identical** to before consolidation.
- Neither source freeze references retired evaluation modules.
- Both model-answer dispatch counts remain **zero**.

| Current preparation | Cases | Variants/prompts | Model calls |
|---|---:|---:|---:|
| `testing-matrix-preparation-check-20261113` | 1 | 5 | 0 |
| `refactoring-ready-v2-clean-20261113` | 5 | 25 | 0 |

These are preparations/evaluator checks, not model scores. New-run defaults are
five cases for each matrix. Prior explored Methods2Test IDs remain excluded in
the current configuration without keeping obsolete model outputs. Existing
preparation execution logs were not rewritten; only the zero-dispatch source
freezes were explicitly rebuilt after infrastructure extraction.

Each run has `readiness/consolidation-verification.json` and freeze/report logs.
The source snapshot contains current library code, not another runnable eval
protocol. The common helpers expose no standalone CLI.
