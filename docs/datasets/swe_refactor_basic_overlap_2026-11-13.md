# SWE-Refactor: basic overlap audit, 2026-11-13

## Result

Compared **all 1,099 SWE cases** with current materialized FT inputs and actual
documents/metadata in the WSL V3 Chroma SQLite database, opened read-only.

- **0 cases** have an equal nonempty normalized code field in the inspected assets.
- **0 cases** have an equal normalized before/after pair.
- **0 cases** share a recorded full 40-character commit SHA.
- **125 cases** share a known refactoring repository: **PMD**. MaRV contributes
  six PMD records to the current refactoring training file and PMD is present in
  actual `refactoring_db` and `mixed` retrieval documents. This is a project-level
  risk flag, **not 125 proven leaked examples**.
- Excluding all PMD cases leaves **974 candidates from 17 SWE projects**, including
  **386 Extract Method + 65 Inline Method = 451** cases relevant to the proposed
  bounded first protocol. These are not yet executable or certified unseen cases.

## Compared assets

The source-only ML4Refactoring/MaRV split files are represented by their existing
refactoring mixture; shared FT also has its separate combined-file comparison.
Rows across these inputs overlap, so totals must not be summed as unique exposure.

| Current files / collection | Rows | SWE code matches | SWE commit matches | SWE known-project flags |
|---|---:|---:|---:|---:|
| `refactoring/train.jsonl` | 4,478 | 0 | 0 | 125 (PMD) |
| `refactoring/val.jsonl` | 600 | 0 | 0 | 0 |
| `refactoring/test.jsonl` | 608 | 0 | 0 | 0 |
| `testing/train.jsonl` | 4,000 | 0 | 0 | 0 recorded* |
| `testing/val.jsonl` | 500 | 0 | 0 | 0 recorded* |
| `testing/test.jsonl` | 500 | 0 | 0 | 0 recorded* |
| `combined/train.jsonl` | 8,000 | 0 | 0 | 0 recorded* |
| `combined/val.jsonl` | 1,000 | 0 | 0 | 0 recorded* |
| `combined/test.jsonl` | 1,000 | 0 | 0 | 0 recorded* |
| Actual `refactoring_db` | 1,761 | 0 | 0 | 125 (PMD) |
| Actual `testing_db` | 3,978 | 0 | 0 | 0 recorded* |
| Actual `mixed` | 5,739 | 0 | 0 | 125 (PMD) |

File paths in this table are under `data/processed/`. All counts in match columns
are **unique SWE cases**, not number of source matches. Internal test files are
reported separately; they are not described as training exposure.

Actual RAG source counts: `refactoring_db` has 1,283 ML4Refactoring + 478 MaRV;
`testing_db` has 3,978 Methods2Test; `mixed` has those same source counts combined.
All **11,478 collection rows** yielded before/after code sections with the existing
document format, with **0 unparsed documents**. Collections contain shared
documents, not 11,478 independent examples.

\* Methods2Test entries lack a usable repository name and commit SHA in these
materialized/Chroma records. Their code was compared, but repository-disjointness
was **not established**; numeric `source_file` project IDs were not mapped back to
GitHub repositories in this basic audit. The same limitation propagates to mixed
and combined sources. This also limits the meaning of the 974-candidate figure.

## Method

Reused `ingestion.identity.normalize_java_for_hash`: normalize Java token spacing,
remove comments, retain identifiers and string/character literal contents, then
SHA-256. Ignore empty normalized strings. This is lexical comparison, not semantic
or AST equivalence.

All four SWE fields were checked against both input/output sides of every source:

- `sourceCodeBeforeRefactoring`, `sourceCodeAfterRefactoring`;
- `sourceCodeBeforeForWhole`, `sourceCodeAfterForWhole`.

Aligned primary/whole before-after pairs were also compared. Actual RAG documents
were parsed using `Original Java code:` / `Refactored Java code:` or
`Production Java code:` / `Corresponding test code:`. The trailing change-summary
section was excluded; stored input/focal hashes were checked additionally.

Repository basenames were compared case-insensitively after removing URL/git
decoration and an `apache-` prefix. Missing MaRV project names were recovered
from the local raw dataset via **exact commit SHA**, not fuzzy code matching.
Repository basename equality is deliberately a coarse flag, not proof of the same
owner/revision/example. SHA comparisons require full 40-hex values.

## Evidence and verification

Owned local ignored directory: `artifacts/swe_overlap_audit_20261113/`:

- `audit.py`: reproducible read-only comparison, no model/provider calls;
- `report.json`: input SHA-256 identities, row counts, metadata completeness,
  before/after source checks and aggregate match sets;
- `case_matches.json`: per-SWE identifiers and matching record references;
- `unflagged_candidates.json`: the 974 identifiers without a detected flag;
- `verify.py`: count consistency, PMD membership, all-document parsing checks,
  normalization controls and synthetic positive pair/hash checks.

Executed from repository root in WSL using existing `.venv_wsl` dependencies:

```bash
.venv_wsl/bin/python artifacts/swe_overlap_audit_20261113/audit.py
.venv_wsl/bin/python artifacts/swe_overlap_audit_20261113/verify.py
```

Verification passed. PMD appears in `refactoring/train.jsonl` at lines
165, 532, 893, 1918, 2481 and 2921, all from MaRV. All inspected source-file hashes
and mtimes stayed unchanged; database/main WAL size/mtime stamps stayed unchanged.
No Chroma client was instantiated and no index was rebuilt or modified.

## Interpretation and next use

Use the non-PMD candidates as a **screened starting pool**, not a final independent
holdout. Before selecting the pilot, check the exact target methods and context
for partial/contained copies and recover Methods2Test repository identities if
claiming cross-task repository separation. This basic hash pass does **not** catch
a method embedded inside a larger class, renamed clones, or diff-hunk versus
complete-method overlap. Current FT files are not immutable historical training
snapshots; matching training-summary paths/counts do not prove historical bytes or
per-example optimizer exposure. Base-model pretraining contamination is untested.

No generation, training, build, installation, download, final benchmark selection
or inference run was performed. No historical protocols or user files were edited.
