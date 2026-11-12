# SWE-Refactor: pinned Zenodo acquisition (2026-11-12)

**DATASET_READY for local loading and prompt-only inspection; EXECUTION_NOT_READY for Java evaluation or final experiments.** Acquisition base: Git `8ea004c`; inspection/runtime checks: existing WSL Ubuntu `.venv_wsl`, Python 3.13.11. Windows was used only to download public bytes and manage files.

## Source correction and attribution

The user-selected source replaces the earlier unauthenticated GitHub-copy source for this preparation. It is the **same SWE-Refactor benchmark**, not permission to delete reusable adapters, research history, or unrelated SWE material. The configured old data root was absent before acquisition; there was nothing old to delete or replace. No research history was removed.

- Exact requested record: <https://zenodo.org/records/17196850>
- API snapshot: <https://zenodo.org/api/records/17196850>
- DOI: **10.5281/zenodo.17196850** (published 2025-09-25).
- Title: *SWE-Refactor: A Repository-Aware Benchmark for Evaluating LLMs on Real-World Code Refactoring*.
- Deposited creator: **anonymous**. Cite that depositor and the DOI; this evidence does **not** independently authenticate the deposit as an author-endorsed release or establish its exact relationship to the later paper revision.
- Record license: **CC-BY-4.0**, <https://creativecommons.org/licenses/by/4.0/>. This supplies explicit deposit-level reuse/attribution evidence missing from the previous GitHub-copy audit. It is not a blanket relicensing of all underlying Java projects/tools; preserve their licenses/notices when acquiring subjects or redistributing code.
- No README or LICENSE member, Maven POM, or Gradle build file was found anywhere in this exact ZIP inventory. The captured record HTML/API description supplies its documentation/license evidence; do not invent missing archive files.
- Latest-version endpoint was checked only for awareness: record **23194601**, DOI **10.5281/zenodo.23194601**, ZIP 233,357,896 bytes, published MD5 `1490e8c840c52a26355d701831f32baf`. Its metadata was saved but its ZIP was **not downloaded**. The explicitly requested **17196850** version remains pinned; no silent latest-version substitution occurred.

## Download and integrity

Public unauthenticated download (no credentials):
<https://zenodo.org/api/records/17196850/files/SWE-Refactor.zip/content>

Local ignored download/evidence directory:
`benchmarks/swe-refactor/downloads/zenodo-17196850/`.

| Artifact | Bytes | Digest |
|---|---|---|
| SWE-Refactor.zip | 207329781 | published + locally matched MD5: `f06ee0ce4c8034d57d4d2d1b4c32a24d` |
| SWE-Refactor.zip | 207329781 | computed SHA-256: `e1bd6eedcdf65c4c6cf4454cf07d3db558cd4ba1706419a409489297f8ea6a65` |
| pure_refactoring_data.json | 67505459 | computed SHA-256: `69e1846e6f1624cb693262de2648c973470ee2ce8a753e38d1666f5d620c3fdc` |

Preflight found about 212 GiB free (227,193,221,120 bytes). Download used resumable curl with bounded retries (3, 10-second delay), a 30-second connection timeout and 600-second transfer limit; it completed successfully on the first transfer. Byte length and published MD5 were checked **before extraction**, then SHA-256 computed locally. Selected ZIP members were read through the ZIP library, which checked their CRCs; no claim is made to have decompressed/CRC-tested excluded members.

Inventory: **685 entries**, **1,400,569,523 uncompressed bytes**. Before extraction, all entries were checked for absolute/traversal/backslash paths, drive-like root names, symlinks, duplicate names, encryption, entry count, aggregate/single-member size and compression ratio. Conservative limits: fewer than 100,000 entries, total below 5 GiB, each below 300 MiB, ratio below 10,000. 216 names contain colons in excluded model-result paths/macOS sidecars: inventory-only, never extracted (Windows ADS/nonportable-name risk). Selected paths additionally reject colons anywhere, resolve under the canonical root, and are allowlisted UTF-8 files below 100 MiB. Existing different files would not be overwritten. No ZIP-wide extract-all was used.

## Selected files

Exactly **10 archive members**, **67,599,668 bytes**, were extracted unchanged beneath `benchmarks/swe-refactor/`. The root remains the existing configured `benchmarks/swe-refactor/SWE-Refactor`; no config/count/prompt/runtime/baseline change was needed. Evaluation sources are quarantined **read-only inspection material**, not an enabled evaluator or a complete upstream installation.

| Relative to benchmarks/swe-refactor | Bytes | SHA-256 |
|---|---|---|
| `SWE-Refactor/pure_refactoring_data.json` | 67505459 | `69e1846e6f1624cb693262de2648c973470ee2ce8a753e38d1666f5d620c3fdc` |
| `SWE-Refactor/code/clone.sh` | 175 | `2e6c69f0fe5432a7bd899e774d3014e2792a2a6b8de95a269042b0d44324cb47` |
| `SWE-Refactor/code/repos.txt` | 422 | `bd6192819c0d32edae9866ba8837ea318c6147ab40359c1266cdae6371d5dffa` |
| `SWE-Refactor/code/requirements.txt` | 1824 | `7aa5a948a5fc043ca64aadde0b0804385e9275df95c698270d4b9b6f020cff66` |
| `SWE-Refactor/code/.java-version` | 3 | `54183f4323f377b737433a1e98229ead0fdc686f93bab057ecb612daa94002b5` |
| `SWE-Refactor/code/data/config/compile_command.txt` | 714 | `e713d0b80c550ba7fcedc9d8ac63df6a211a3d03e47b9c47c02b27a53f20b89f` |
| `SWE-Refactor/code/evaluation_for_refactoring.py` | 31488 | `e57de48e7de1fba821e687e7a1ae2d300a9a7e677cef556af286391ccb7e6aca` |
| `SWE-Refactor/code/compile_experiment.py` | 35897 | `fdec0e9f46a6d278533bf05a50a9bca886b13c4437ca62935d86a1baa88e66ec` |
| `SWE-Refactor/code/project_util.py` | 5809 | `65a651a6190847532099e4a107a6b37828f09a30e0aa58a5e5bf235070bd9713` |
| `SWE-Refactor/code/jacoco_util.py` | 17877 | `00d410ec94c7301086d18cb122a031ce7001e1c53e0d8345dfedc539e9edbbdc` |

Selection rationale: the single canonical pure JSON is sufficient for the adapter; clone/repository list and Java/dependency/build-command metadata help plan subject acquisition; four evaluation/compilation/coverage helper sources permit static evaluation-safety inspection. No archive script was imported or executed and no requirements were installed. The clone list has only **10 repositories**, while the actual dataset has **18**; it is neither a complete subject manifest nor a pinned checkout recipe.

Excluded: all `experimental result/` model outputs; per-project duplicate pure datasets; upstream generation/RAG/preprocessing code and prompt templates; `code/config.yaml` (credential-bearing configuration category, unnecessary here); IDE/macOS files and sidecars; temporary code/output; RefactoringMiner launcher/JAR/dependency binaries and tool temporary files. No secrets/env files, credentials, caches, embedded indexes, Git metadata, binaries or upstream model results were extracted. The intact ignored ZIP retains excluded assets without installing them. The unchanged user-edited `.gitignore` already ignores this root; an additive local `.git/info/exclude` rule also protects it independently. No dataset/archive/prompt artifact is staged or committed.

Local-only evidence files include `record.json`, `record.html`, `latest-record.json`, `zip_inventory.json`, `archive_report.json`, `selected_files.json`, `dataset_report.json`, `verification_report.json`, summary files, bounded inspection scripts and `prompt-only.jsonl`. These are preparation artifacts, not generation/evaluation results.

## Actual JSON inventory (not paper claims)

Top level: list of **1,099 objects**, **1,099 unique nonblank uniqueId values**, **18 projects**, **6 operation types**; all records have `isPureRefactoring=true`. No records were filtered out or rewritten. Atomic operations: **922**; compound operations: **177**.

| Value | Cases |
|---|---|
| checkstyle | 91 |
| commons-lang | 59 |
| commons-io | 93 |
| pmd | 125 |
| junit4 | 18 |
| junit5 | 105 |
| hibernate-orm | 63 |
| hibernate-search | 89 |
| mockito | 4 |
| javaparser | 56 |
| gson | 21 |
| guava | 300 |
| hertzbeat | 9 |
| jadx | 18 |
| shardingsphere-elasticjob | 3 |
| shenyu | 22 |
| shiro | 2 |
| zxing | 21 |

| Value | Cases |
|---|---|
| Inline Method | 71 |
| Extract And Move Method | 142 |
| Extract Method | 441 |
| Move Method | 410 |
| Move And Rename Method | 21 |
| Move And Inline Method | 14 |

All 1,099 records have nonblank full before/after code and nonblank primary after code. Primary before code is blank for **3 Move And Inline Method** cases (pmd, hibernate-search, javaparser); existing whole-file fallback yields nonempty inputs. Those three inputs are whole-file while references remain primary snippets: prompt-only loadability is not a validated application/granularity contract. **121** records change file path. There are **no explicit top-level JSON nulls** in this pinned dataset; optional-field absence must not be mistaken for an explicit null. The previously audited null-to-`None` loader defect was nevertheless fixed narrowly, with regression coverage for null/empty/whitespace before and after fallback. Non-null real inputs and the canonical prompt contract are unchanged.

Schema observed across the entire JSON (types are Python inspection names; present/null counts distinguish absence):

| Field | Present | Explicit null | Observed type counts |
|---|---|---|---|
| `callGraph` | 262 | 0 | dict: 262 |
| `callInfo` | 1099 | 0 | str: 1099 |
| `classNameBefore` | 1099 | 0 | str: 1099 |
| `classNameBeforeSet` | 1099 | 0 | list: 1099 |
| `classSignatureBefore` | 1099 | 0 | str: 1099 |
| `classSignatureBeforeSet` | 1099 | 0 | list: 1099 |
| `commitId` | 1099 | 0 | str: 1099 |
| `compileCommand` | 1099 | 0 | str: 1099 |
| `compileJDK` | 1099 | 0 | int: 994, float: 105 |
| `compileResultBefore` | 1099 | 0 | bool: 1099 |
| `compileResultCurrent` | 1099 | 0 | bool: 1099 |
| `coverageInfo` | 1099 | 0 | dict: 1099 |
| `description` | 1099 | 0 | str: 1099 |
| `diffLocations` | 1099 | 0 | list: 1099 |
| `diffSourceCode` | 1099 | 0 | str: 1099 |
| `diffSourceCodeSet` | 1099 | 0 | list: 1099 |
| `filePathAfter` | 1099 | 0 | str: 1099 |
| `filePathBefore` | 1099 | 0 | str: 1099 |
| `hasTestC` | 1 | 0 | bool: 1 |
| `invokedMethodSet` | 1099 | 0 | list: 1099 |
| `isPureRefactoring` | 1099 | 0 | bool: 1099 |
| `methodNameBefore` | 1099 | 0 | str: 1099 |
| `methodNameBeforeSet` | 1099 | 0 | list: 1099 |
| `moveFileExist` | 1099 | 0 | bool: 1099 |
| `packageNameBefore` | 1099 | 0 | str: 1099 |
| `projectName` | 1099 | 0 | str: 1099 |
| `purityCheckResultList` | 1099 | 0 | list: 1099 |
| `sourceCodeAfterForWhole` | 1099 | 0 | str: 1099 |
| `sourceCodeAfterRefactoring` | 1099 | 0 | str: 1099 |
| `sourceCodeBeforeForWhole` | 1099 | 0 | str: 1099 |
| `sourceCodeBeforeRefactoring` | 1099 | 0 | str: 1099 |
| `testResult` | 1098 | 0 | bool: 1098 |
| `type` | 1099 | 0 | str: 1099 |
| `uniqueId` | 1099 | 0 | str: 1099 |

### Build/test/coverage metadata caveats

- `compileResultBefore=true`: **1,099**. `compileResultCurrent=true`: **1,097**; **2 false**, both checkstyle Extract Method at commit `50a9a64b6d70aa722dcf754ad5d46e37784f5b05`. Their IDs are `50a9a64b6d70aa722dcf754ad5d46e37784f5b05_154_199_201_217_154_183` and `50a9a64b6d70aa722dcf754ad5d46e37784f5b05_154_199_185_199_154_183`.
- `compileJDK`: Java 8 represented as float **1.8: 105**; **11: 482**, **17: 318**, **21: 194**. Do not blindly parse all values as integer major versions.
- `testResult=true`: **1,098**, absent **1**. `hasTestC=true`: **1**, absent **1,098**. The adapter currently retains hasTestC rather than the much more common testResult; missing has_test metadata is not proof that tests are unavailable.
- Compile commands: **909 Maven**, **190 Gradle**. **300 guava** records explicitly contain `-DskipTests`; **93 commons-io** commands have unmatched shell quoting (detected by `shlex.split`, not executed). Other commands exclude tests/checks or allow zero specified tests. Never execute dataset command strings blindly or equate a build exit code with behavior-test coverage.
- `coverageInfo` exists as a dictionary for **1,099** cases, but is heterogeneous: **733** have only `testMethod`; **110** have INSTRUCTION/LINE/COMPLEXITY/METHOD counters; **256** also include BRANCH. Thus standard counter coverage exists in only **366** records. None of these 366 counters reports zero covered for the four common metrics, but stored metadata is neither locally reproduced coverage nor candidate evaluation.
- Deposited evaluator source still contains the dispatcher early return at `evaluation_for_refactoring.py:23`, unconditional Extract Method success at **69** before checkout/application/checks, and further analogous returns. `compile_experiment.py:47-55` actively builds with `-x test`. **Do not run or trust this harness unchanged.** Acquisition does not resolve these evaluator defects.

## Verification actually executed

Using existing WSL dependencies only, from repository root:

~~~bash
.venv_wsl/bin/python -m pytest -q tests/experiments/test_benchmarks.py tests/experiments/test_benchmark_edge_cases.py
.venv_wsl/bin/python scripts/experiments/benchmarks/inspect_benchmarks.py --benchmark swe_refactor
.venv_wsl/bin/python scripts/experiments/benchmarks/run_benchmark.py --benchmark swe_refactor --backend prompt-only --limit 1099 --output benchmarks/swe-refactor/downloads/zenodo-17196850/prompt-only.jsonl
.venv_wsl/bin/python benchmarks/swe-refactor/downloads/zenodo-17196850/verify_preparation.py
git diff --check
~~~

Adapter/edge-case tests: **6 passed**. Real loader: **1,099 cases**, **1,099 references**, **1,099 unique normalized IDs**, **3 fallback flags**, all before/reference fields nonempty and not literal None. Prompt-only CLI: **1,099 records**, every prompt nonempty, **no predictions**, generation model null and backend prompt-only. Reference output remains outside the prompt-builder input contract. This validates local data/schema compatibility and prompt preparation only, not token-budget suitability, repository-level correctness or generation. The prompt-only JSONL retains evaluator-only references as local records and must never be indexed or used for training.

## Remaining executable/final-experiment gates

1. Acquire/pin all 18 subject repositories and parent revisions with their notices; the deposited clone script is incomplete and unpinned. Provision/review JDK 8/11/17/21 and project-specific Maven/Gradle dependencies in WSL without changing frozen baseline identities.
2. Define a reviewed, shared structured-output/application contract (including whole-file versus method snippets, moves/multi-file changes) and safe isolated worktrees. Preserve canonical prompts until a separately approved versioned protocol change.
3. Implement a trustworthy shared SWE executable evaluator/readiness path: original/developer-reference/no-op/syntax-broken/behavior-changing controls; real fresh positive test execution, compilation and requested-operation detection. Repair/review upstream bypasses rather than treating its results as truth.
4. Reserve and leakage-audit the external cases against actual retrieval, training and validation assets; create a separately approved non-indexable benchmark manifest/protocol. Do not relabel the existing 608-case internal refactoring manifest as SWE.
5. Integrate controlled Direct/RAG/MultiRAG through the existing shared runner and complete provenance only after model-free controls pass. No model calls, builds, installs, index reads/writes/rebuilds, spend, pushes or frozen-baseline edits occurred in this task.

Historical audit statements about absent SWE data/unresolved deposit licensing are superseded **only to the bounded extent above** by dated appendices in the four audit/selection documents. Testing-benchmark readiness and previous data-leakage/runtime findings remain unchanged.
