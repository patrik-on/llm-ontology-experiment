# Java refactoring benchmark selection — 2026-11-12

## Decision

**Select SWE-Refactor (Xu, Yang, Chen; arXiv:2602.03712v1) as the primary benchmark integration target.** Its real Java projects, named atomic/compound refactorings, developer references, project tests, and structural verification match this project's research question better than the alternatives screened below.

This is a viable scientific choice, **not a claim that the current checkout or the discovered public evaluator is executable-ready**. Proceed first with artifact/provenance clarification and one model-free executable canary. Do not launch full generation or label existing similarity/proxy metrics as refactoring correctness.

The bounded follow-up search found an author-confirmed **paper**, but did not establish an author-confirmed **dataset/code release**. Missing license information is an unresolved provenance/reuse question, not a conclusion that private research use is unlawful. Institutional rules, upstream project terms, intended redistribution, and author clarification are separate considerations. No legal conclusion is made here.

**Current status:** adapter implemented; local SWE data absent; prompt preparation supported after acquisition; SWE-specific executable evaluator and readiness checks missing; public-copy evaluator has serious verification bypasses. No model or Java project was executed during this audit.

## Scope and evidence rules

- Sources checked live on 2026-11-12; local base commit: e020e50a2694586041644bb3831194e32d4fa849.
- Read devinfo.md, README.md, then relevant benchmark, evaluation, split, and frozen-baseline documentation before inspection.
- Final experiments remain WSL/Linux only; Ollama remains exactly http://localhost:11434 inside WSL.
- Preserve the shared prompt builder, inference/provider boundaries, evaluator interface, reproducibility records, and controlled Direct/RAG/MultiRAG comparison.
- Benchmark cases and evaluator-only material must never enter retrieval indexes or training. A source-defined train split is not permission to index a benchmark.
- Network inspection was read-only: paper/repository pages, small source files/previews, and remote refs. No bulk dataset/model downloads, dependency installs, untrusted builds, generation, paid model calls, config changes, commits, or pushes.
- Only this new documentation file was authorized for writing. Existing user changes were left untouched.
- Distinguish paper claims, inspected source behavior, local observations, and proposed work. No full-corpus correctness result is claimed.

## 1. Local SWE-Refactor readiness audit

### 1.1 What exists and what does not

| Layer | Observed state |
|---|---|
| Data adapter | Implemented in src/llm_ontology/benchmarks/swe_refactor.py |
| Expected dataset | pure_refactoring_data.json, configured expected count 1,099 |
| Local benchmark directory/data | Missing; existence checks returned false |
| Adapter tests | Small synthetic fixtures; not evidence about the real dataset |
| Prompt preparation | Generic direct prompt-only route exists once data is present |
| Complete controlled experiment | Needs shared-runner integration, manifests, executable evaluator, and recorded assets |
| SWE-specific readiness checker | Not present; existing readiness command is TestBench-specific |
| Executable Java refactoring evaluation | Not implemented locally for SWE |
| External SWE leakage audit | Not possible without the external artifact; not established |
| Dataset license/version/checksum | Not established in a local SWE manifest |

Existence checks from the repository root:

~~~text
benchmarks                                                       False
benchmarks/swe-refactor/SWE-Refactor                              False
benchmarks/swe-refactor/SWE-Refactor/pure_refactoring_data.json     False
.venv_wsl/bin/python                                             True
~~~

The 1,099 count in local docs/config is an expected upstream count, not an observed local inventory.

### 1.2 Adapter limitations

Evidence: src/llm_ontology/benchmarks/swe_refactor.py, contracts.py, tests/experiments/test_benchmarks.py, and test_benchmark_edge_cases.py.

- Lines 10 and 24 specify the absent benchmark root and JSON filename.
- Lines 40–41 select method-level before/after fields and independently fall back to whole-file fields. This can mix input/reference granularities and must be validated on real records.
- Lines 60–63 preserve historical compilation/test flags as metadata; these flags do not verify a new candidate.
- The normalized prompt supplies the operation type but omits much of the repository/target context needed for move and compound operations.
- Execution-critical information such as per-case compileJDK, target-file context, caller/callee context, build details, and coverage information is not preserved comprehensively.
- Unique case IDs and configured expected count are not enforced by the loader.
- Null values can become the nonempty string None in _first_text, preventing the intended fallback.
- Reference after-code remains outside the direct prompt-building call, which is good; keep it evaluator-only when integrating the dataset.

These are integration gaps, not proof that the underlying benchmark is unsuitable.

### 1.3 Runner, schema, and evaluation gaps

- src/llm_ontology/benchmarks/runner.py:13–30 calls prepare_prompt for direct mode. It does not retrieve or execute Java.
- scripts/experiments/benchmarks/run_benchmark.py supports prompt-only and Ollama, but is not the complete frozen experiment path. It does not consume the SWE YAML as an enforced complete protocol; its output is not the full digest/manifest/prompt-artifact/retrieval-trace record required for final comparisons.
- configs/benchmarks/swe_refactor.yaml explicitly sets backend: prompt-only.
- scripts/experiments/benchmarks/check_readiness.py:14,28 invokes check_testbench_readiness. It must not be presented as a SWE readiness proof.
- src/llm_ontology/evaluation/refactoring_metrics.py:35–44 combines edit similarity and code-health/cohesion/coupling proxies. It does not establish compilation, behavior preservation, or the requested refactoring.
- That evaluator reads expected_output at line 49; BenchmarkCase.as_record() exposes reference_output. An explicit conversion is needed before feeding benchmark records into that metrics pipeline. This is a schema-boundary hazard, not a claim about a completed SWE evaluation run.
- configs/datasets/manifests/refactoring_benchmark.yaml describes the 608-case internal ML4Refactoring/MaRV test mixture, not SWE-Refactor. Do not relabel it as the external benchmark manifest.

### 1.4 Actual WSL prerequisites

Read-only checks inside Ubuntu established:

- OpenJDK and javac **17.0.20.1**;
- Apache Maven **3.9.16**;
- python3, g++, git, and ollama on PATH;
- pmd and docker not found on the inspected PATH.

This is not a full-corpus toolchain proof. Project-specific JDKs, Gradle distributions, dependencies, test viability, and offline cache completeness were not tested. Dated Windows environment-lock documentation is not evidence of current WSL tool availability.

### 1.5 Training/retrieval leakage is a separate gate

The existing user-authored, untracked docs/datasets/data_audit_report.md reports stale materialized splits and substantial ML4Refactoring cross-split overlap. Those counts were read, not independently recomputed here.

A clean retrieval audit does not establish clean fine-tuning exposure. Audit external SWE records against specialist/shared fine-tuning data, retrieval source records, actual indexed content, validation/internal tests, and derived sources. Use repository/project identity, related commits, and normalized before/after fingerprints. Already-trained adapters cannot be decontaminated merely by filtering an index later.

## 2. Candidate comparison

| Candidate | Correctness signal | Fit and cost | Decision |
|---|---|---|---|
| **SWE-Refactor** | Paper: compilation/tests plus requested-refactoring detection; CodeBLEU secondary | Best fit for named Java source refactorings, including compound changes; needs artifact confirmation and trustworthy evaluation | **Primary selection; canary gate before generation** |
| **LintEval, Java subset** | Generated-input/oracle execution plus PMD alert improvement | 51 Java cases in lite; file-level competitive-programming lint refactoring; concrete data/harness issues found | Secondary candidate, not a silent replacement |
| **ScarfBench** | Compile, container deployment, observable-interface tests | Enterprise Java framework migration; Docker/framework preparation and repository-editing agent contract needed | Future separate study, not current baseline |

### 2.1 SWE-Refactor: scientific protocol and release identity

Paper: Xu, Yang, Chen, **SWE-Refactor: A Repository-Level Benchmark for Real-World LLM-Based Code Refactoring**, arXiv:2602.03712v1, submitted 2026-02-03.

- Abstract/version history: <https://arxiv.org/abs/2602.03712>
- Full HTML: <https://arxiv.org/html/2602.03712v1>
- DOI: <https://doi.org/10.48550/arXiv.2602.03712>

The paper reports **1,099 developer-written refactorings from 18 Java projects**, comprising **922 atomic and 177 compound** instances. Operations: Extract Method, Move Method, Inline Method, Extract-and-Move, Move-and-Inline, and Move-and-Rename. It describes compilation/test verification, coverage-based filtering, AST/refactoring analysis, and richer repository context than the local adapter currently exposes.

The intended evaluation distinguishes:

1. compilation and project-test success;
2. detection of the requested refactoring;
3. CodeBLEU as secondary similarity/human-likeness, not correctness.

Tests and detectors provide evidence, not a proof of semantic equivalence. Passing tests without a structural change must not count as successful refactoring.

#### Bounded author-confirmation follow-up

The current abstract page still exposes **v1 only**. Full live HTML and its external links were inspected, not only the truncated introductory extraction. Appendix A says:

> Our SWE-Refactor benchmark and experimental results ... are available on the following platform: To be released.

No dataset/repository release URL was present there.

Additional live checks:

- Corresponding author's site <https://petertsehsun.github.io/> explicitly lists SWE-Refactor and links the arXiv paper, but no corresponding code/data link was found in the inspected page.
- That site links the first author's site <https://xuyisen.github.io/>. Its publication page <https://xuyisen.github.io/publications/> did not expose a SWE release.
- The first-author site links <https://github.com/xuyisen>. Its inspected repository-list page did not establish a release. This was a bounded page check, not proof that all current/private repositories are absent.
- <https://jinqiuyang.github.io/> and <https://jinqiuyang.github.io/publications/> did not establish a release.
- GitHub exact-name search found the public copy below and the distinct Einsia migration benchmark, but no author-confirmed release in the inspected results. Name-based GitHub user-search hits alone were not accepted as author identity.

**Conclusion:** author-confirmed paper, public matching copy, but no established author-to-artifact provenance chain. This does not prove no official release exists elsewhere.

#### Public copy found, not authenticated as the author release

- Repository: <https://github.com/obieda01/SWE-Refactor>
- Observed HEAD: **40dc9377cfd4b8d420c9b97ad4d35d94f174f154**
- [Pinned commit](https://github.com/obieda01/SWE-Refactor/commit/40dc9377cfd4b8d420c9b97ad4d35d94f174f154)
- [Dataset page](https://github.com/obieda01/SWE-Refactor/blob/40dc9377cfd4b8d420c9b97ad4d35d94f174f154/pure_refactoring_data.json)
- GitHub reports the JSON as **64.4 MB**. It was not downloaded, parsed, counted, or checksummed here.
- Root README and root LICENSE checks returned 404. No explicit benchmark-wide code/data reuse terms were established from the inspected root.
- [Issues page](https://github.com/obieda01/SWE-Refactor/issues) showed zero open issues; this is not a quality/reproducibility endorsement.

Do not label this account an official release or assign an invented license. Retain original Java project notices/terms separately when source checkouts are used.

### 2.2 Public-copy evaluator bypasses: do not run unchanged

Pinned inspected source:

- [evaluation_for_refactoring.py](https://github.com/obieda01/SWE-Refactor/blob/40dc9377cfd4b8d420c9b97ad4d35d94f174f154/code/evaluation_for_refactoring.py)
- [compile_experiment.py](https://github.com/obieda01/SWE-Refactor/blob/40dc9377cfd4b8d420c9b97ad4d35d94f174f154/code/compile_experiment.py)
- [project_util.py](https://github.com/obieda01/SWE-Refactor/blob/40dc9377cfd4b8d420c9b97ad4d35d94f174f154/code/project_util.py)

Observed defects:

1. compile_and_test_refactoring() returns immediately when either saved verification flag is false/missing, contrary to its documented dispatch intention:

   ~~~python
   if not (miner_result and test_result):
       return miner_result, test_result, ""
   ~~~

2. eval_extract_method() returns unconditional success after response parsing and **before** checkout, patch application, RefactoringMiner, and compilation:

   ~~~python
   refactored_method_code = fields['refactored_method_code']
   return True, True, refactored_method_code
   # checkout / structural verification / compilation follow, unreachable here
   ~~~

3. Inline handling has a similar early-return pattern. A no-refactoring response can also be treated as successful on an inspected path.
4. Move-and-Inline dispatch is a constant-failure lambda, not an implemented evaluator.
5. compile_project() invokes ./gradlew clean build -x test; fallback commands also exclude tests. This is not execution of the paper's functional-verification protocol.
6. Hardcoded macOS paths, jenv local changes, shell=True commands, and reset/forced-checkout helpers are inappropriate against the research working tree.
7. RefactoringMiner is hardcoded to **3.0.10** under a local tools directory. The .java-version file says **17**; neither establishes all per-project assets/JDKs.

These findings apply to the pinned public copy, not automatically to an unavailable authors' implementation. Its saved predictions/flags must not be trusted as newly reproduced correctness results.

Reuse established project build/test tooling and a reviewed, pinned refactoring detector through the existing evaluation boundary. Do not import the copy's model/API/RAG scripts or create a parallel inference/retrieval stack. A safe evaluator integration is not the same as inventing a new benchmark.

### 2.3 LintEval Java subset

Authoritative paper-to-code link:

- <https://arxiv.org/abs/2610.20027> (v1, 2026-10-14; accepted-at-Findings claim stated there)
- <https://github.com/6643789wsx/LintEval>
- <https://huggingface.co/datasets/deepbreath7/LintEval>

Observed pins:

- GitHub HEAD: **b65c9f4ad6099d1c53df388f68f21ec698e5539e**
- Hugging Face HEAD: **a3b30492b0c45406632a5105dce9c3834653bcf1**

Documentation reports 13,061 multilingual programs / 171,662 alerts; the 498-case lite dataset contains **51 Java** cases. Task: reduce PMD alerts while retaining competitive-programming input/output behavior, rather than perform a specified repository-level refactoring.

Sources at the inspected GitHub pin:

- [SETUP.md](https://github.com/6643789wsx/LintEval/blob/b65c9f4ad6099d1c53df388f68f21ec698e5539e/SETUP.md)
- [docs/DATA.md](https://github.com/6643789wsx/LintEval/blob/b65c9f4ad6099d1c53df388f68f21ec698e5539e/docs/DATA.md)
- [docs/REPRODUCE.md](https://github.com/6643789wsx/LintEval/blob/b65c9f4ad6099d1c53df388f68f21ec698e5539e/docs/REPRODUCE.md)
- [LICENSE](https://github.com/6643789wsx/LintEval/blob/b65c9f4ad6099d1c53df388f68f21ec698e5539e/LICENSE)
- [src/test_runner_multi.py](https://github.com/6643789wsx/LintEval/blob/b65c9f4ad6099d1c53df388f68f21ec698e5539e/src/test_runner_multi.py)
- [src/linter_java.py](https://github.com/6643789wsx/LintEval/blob/b65c9f4ad6099d1c53df388f68f21ec698e5539e/src/linter_java.py)
- [lite/preview.json](https://github.com/6643789wsx/LintEval/blob/b65c9f4ad6099d1c53df388f68f21ec698e5539e/lite/preview.json)

Useful metrics: Pass@1; Reduction@P = corpus-level alert reduction over passed cases; New@P; changed lines; lines per fixed alert. Always report pass rate with conditional improvement metrics. Copy-original can pass behavior checks while improving nothing.

Local model support exists through vLLM/OpenAI-compatible endpoints. For this project, consume predictions from the shared runner and reuse evaluator components rather than adopting upstream generation/prompts. Java evaluation needs **javac/java, PMD, g++, and testlib** because generators/checkers are C++ tools. Pre-cached assets allow offline evaluation in principle; that was not executed here.

Concrete cautions:

- The small released preview's Java case **p00330_java_0** contains import java.*; but uses unqualified Scanner, which does not import java.util.Scanner. The shown original is not a clean compilable Java refactoring input.
- It also stores compile_ok: false, pass_at_1: false, and validation_error: javac not found -- JDK is not installed. That error belongs to the recorded collection environment, not a current test result. Independently validate originals; do not infer all 51 cases are bad from one preview.
- run_pmd() returns an empty alert list on timeout or missing executable. Fail-closed infrastructure validation is required or failures can masquerade as perfect alert reduction.
- The test runner builds an original-solution oracle and candidate, generates inputs, and checks outputs. Timeouts are not a complete security sandbox. Persist inputs/seeds identically across approaches.
- Runtime summaries and paper-table aggregation must be reconciled: documentation distinguishes corpus-weighted Reduction@P from means of per-case ratios.
- Per-record split is problem-construction provenance, not permission to train/index evaluation cases. The changelog documents an earlier silent 498-to-68 case filtering bug.
- Code has MIT text, but the same LICENSE has a separate **research-purpose-only data statement** for CodeContests+/Codeforces-derived material. HF's license: mit label is not a substitute for reading that statement or checking underlying rights.

Verdict: a possible secondary linter-refactoring experiment after data/harness canaries, not a drop-in replacement for named Java operations. No complete Java subset or current model performance was verified. The attempted HF row-filter service timed out; this is an access limitation, not evidence the dataset is unavailable.

### 2.4 ScarfBench

- [Paper](https://arxiv.org/abs/2605.06754) (latest inspected v2, 2026-05-18)
- [Site](https://scarfbench.info/)
- [Repository](https://github.com/scarfbench/benchmark)
- [Dataset card](https://huggingface.co/datasets/ibm-research/ScarfBench)
- [CLI](https://github.com/scarfbench/scarfbench-cli)

Observed repository HEAD: **a14f86fe995a243be92d6408a3f986c1889a1730**.
Observed v0.1.2 ref: **8e675d650ad4356e27897f34108291043c1b6a6c** (recorded ref; not independently checked as a peeled annotated tag).

Paper reports **34 applications, 102 framework variants, and 204 directed tasks** between Spring, Jakarta EE, and Quarkus. Evaluation compiles, deploys in a target container runtime, and tests observable interfaces. Stronger behavioral evidence than similarity alone, but it requires Docker/images, framework dependencies, services for some applications, and a repository-editing agent/output contract. Local inference is not intrinsically excluded; execution cost and task scope are the mismatch.

README/dataset-card links to a root LICENSE returned 404; a benchmark-wide license was not established. This is a clarification item, not a declaration about private research legality. Individual application/upstream terms also matter.

Open [issue #2](https://github.com/scarfbench/benchmark/issues/2) reports discrepancies between documented contributor workflows and existing concurrency-jobs variants, including missing expected Makefile/smoke files and framework-resource inconsistencies. It is a reporter's observation, not a confirmed defect in every case.

Verdict: future enterprise-migration study, not the current controlled single-source refactoring baseline.

### 2.5 Other screened names: do not substitute by name

- **RefactorEval / Refactor-Eval / RefactoringBench:** bounded exact-name GitHub repository and arXiv searches returned no identified maintained Java benchmark under these names. Absence in those results is not proof of nonexistence; no capabilities/license/release should be invented for these names. Searches: <https://github.com/search?q=RefactorEval&type=repositories>, <https://github.com/search?q=RefactoringBench&type=repositories>, and corresponding exact-name arXiv searches.
- **Microsoft RefactorBench:** [README](https://github.com/microsoft/RefactorBench/blob/main/README.md) describes included Django, Salt, Flask, FastAPI, Celery, Ansible, Requests, Scrapy, and Tornado repositories, with their respective licenses. Not the required Java corpus.
- **Einsia/SWE-Refactor-Bench:** [README](https://github.com/Einsia/SWE-Refactor-Bench/blob/main/README.md), [paper](https://arxiv.org/abs/2608.23564). A different 20-task whole-repository stack-migration benchmark with model-based audit/adversarial grading stages. Its Apache-2.0 license and capabilities do not belong to Xu et al.'s SWE-Refactor.
- **CodeEditorBench:** [README](https://github.com/CodeEditorBench/CodeEditorBench/blob/main/README.md), [dataset](https://huggingface.co/datasets/m-a-p/CodeEditorBench). Includes code_polishment, but polishing/performance editing is not named repository refactoring. README states Apache-2.0 for the root project and GPL-2.0 for its HUSTOJ-derived evaluation module, with Docker evaluation and model-sensitive postprocessing. Not a silent substitute; screened, not fully audited or pinned here.

## 3. Smallest executable pilot: one case, no model first

There is **no existing one-command executable SWE correctness pilot in this checkout**. The following is a proposed acceptance protocol, not a test that already passed.

### 3.1 Artifact and environment preparation

1. Obtain an author-confirmed artifact/version or explicit confirmation of the public copy, its inventory, and intended reuse terms. Record URL, revision, acquisition date, checksum, and source-project notices.
2. Inspect schema/count/unique IDs without importing upstream orchestration. Reserve the external artifact as evaluation-only in a new manifest.
3. Select **one single-file Extract Method case** with an unambiguous before/after patch, exact repository/parent/revision identity, recorded JDK/build command, passing original tests, and tests exercising the changed code. Do not invent a case ID before reading the actual artifact.
4. Audit the case and related project/commit/fingerprints against training and retrieval exposure before evaluating models. If prior fine-tuning contamination is found, quarantine those models/cases or report a separate contaminated exploratory result.
5. Review the selected project's build configuration/scripts. Use disposable WSL/Linux workspaces or isolated containers without credentials/production mounts, with bounded time/memory/processes and no network for actual evaluation.
6. In a separately approved preparation phase, cache exact JDK/build-tool/dependency/detector assets. Record checksums and commands. Offline Maven/Gradle operation is a property to test, not assume.
7. Fail closed on missing tools, absent tests, incomplete patch application, detector errors, wrong JDK, timeouts, or missing assets. Separate infrastructure failures from candidate failures.

### 3.2 Mandatory model-free controls

Apply each candidate to the same frozen before-state in separate disposable workspaces; use identical tests and detector settings.

| Control | Required outcome |
|---|---|
| Original/before baseline | Build/relevant tests pass; requested extraction absent |
| Developer reference patch | Build/tests pass; requested extraction detected |
| Unchanged candidate | Behavior may pass; overall refactoring success must fail |
| Syntax-broken candidate | Compilation failure |
| Behavior-changing mutation | Relevant behavioral test fails; otherwise the oracle is inadequate for that mutation |

Record applied file list/diff, source/detector identities, JDK, exact command/flags, exit codes, timeouts, complete logs, tests discovered/executed/passed, affected-code coverage where available, and detector results. Zero-test runs are not behavioral success. Pin generated test inputs/seeds before approach comparisons.

Success means the evaluator distinguishes these controls, not that the whole dataset is validated. One detector match does not establish absence of extra functional edits; inspect patches and use tests/purity checks as complementary evidence.

### 3.3 Metrics through the shared evaluator

Primary per-case fields must distinguish patch/application validity, compilation, tests, requested-operation detection, and their conjunction. Report infrastructure exclusions/denominators explicitly. Use compilation success; test success with counts/coverage caveats; requested-refactoring detection; joint build + behavior-test + operation success; type/project and atomic/compound breakdowns when scaling. Similarity/CodeBLEU and health proxies remain secondary diagnostics.

Extend the existing evaluation boundary; do not replace shared evaluation with cached public-copy flags or create an independent generation/RAG pipeline. Tests preserve only observed behavior on exercised inputs; detector false positives/negatives remain limitations.

### 3.4 Controlled model pilot, only after controls pass

Run one accepted case across Direct, Single RAG, and MultiRAG using the existing RagExperimentRunner, shared canonical prompt builder, output schema, evaluator, provider/model, sampling, context/token budget, and repair policy. Keep identical source/project context; only retrieved evidence may differ.

Keep gold after-code, expected verification outcomes, hidden tests, and coverage assertions evaluator-only. Store exact prompts/hashes, generation/embedding digests, complete config, dataset/collection identities, retrieval traces, outputs, tokens/latencies, and evaluation logs.

baseline_v1 freezes the 24-case smoke dataset. A SWE experiment needs a **new experiment identity/config**; do not overwrite the frozen smoke contract or silently change prompts. Fine-tuning comparisons use the same uncontaminated cases/evaluator and record base/adapter identity and training provenance.

Existing prompt-only smoke command, usable **after** artifact acquisition:

~~~bash
python scripts/experiments/benchmarks/run_benchmark.py \
  --benchmark swe_refactor \
  --benchmark-root benchmarks/swe-refactor/SWE-Refactor \
  --backend prompt-only \
  --limit 1 \
  --output artifacts/evaluation/runs/swe_prompt_pilot/prompts.jsonl
~~~

This prepares a direct prompt; it does not execute Java, prove leakage safety, or satisfy the full experiment-record contract. The first dataset record is not automatically the selected executable canary.

## 4. Exact minimum external clarification

No outreach was sent. Ask the corresponding author (contact published on paper/site) for:

1. **Artifact identity:** official release URL/version/checksum for the 1,099 cases; whether obieda01/SWE-Refactor at 40dc9377cfd4b8d420c9b97ad4d35d94f174f154 is an accurate/authorized copy; where exact repository revisions, per-case JDK/build/test commands, and reconstruction assets are recorded.
2. **Reuse terms:** intended code/data license or research-use permission, with source-project attribution/redistribution constraints.

Do not insist on the author's original harness if the dataset can be faithfully evaluated through the project's shared evaluator and established build/test/detection tools. However, the inspected public evaluator cannot evidence the published verification protocol without repair/control tests. A documented, institutionally accepted provenance/reuse decision may be sufficient for private pilot work; public redistribution requires separate attention.

## 5. Audit commands and verification record

Read-only commands included:

~~~text
git status --short
git rev-parse HEAD
git ls-files '*swe*' '*refactor*' '*benchmark*'
git grep -n ... -- src/llm_ontology/benchmarks src/llm_ontology/evaluation scripts/experiments/benchmarks
git ls-remote https://github.com/obieda01/SWE-Refactor.git HEAD
git ls-remote https://github.com/6643789wsx/LintEval.git HEAD
git ls-remote https://huggingface.co/datasets/deepbreath7/LintEval HEAD
git ls-remote https://github.com/scarfbench/benchmark.git HEAD refs/tags/v0.1.2
wsl -d Ubuntu -- sh -lc 'java -version; javac -version; mvn -version'
~~~

PowerShell existence checks and in-memory HTTP/HTML/JSON inspection were also used. GitHub's unauthenticated API hit a rate limit; HTML/raw pages and remote refs supplied evidence instead. No credentials were read/exposed. The arXiv tar source was not downloaded: latest-version listing and full HTML/external links supplied the bounded release check.

Initial user dirty state, preserved:

~~~text
 M .gitignore
?? docs/datasets/data_audit_report.md
?? docs/datasets/handcrafted_smoke_all_cases.md
?? docs/datasets/raw_record_examples.md
?? scripts/datasets/build_presentation_data_docs.py
~~~

Only this new selection document is added by this follow-up. No executable tests/builds were run because this lane authorized documentation/research, not untrusted execution, installations, or generation. Verification is limited to document/diff inspection and whitespace checks; runtime readiness does not follow from them.

## Final actionable verdict

**Use SWE-Refactor, not an unrelated benchmark with a similar name.** Its task and correctness protocol suit this project; the local adapter is useful scaffolding. Next resolve artifact identity/reuse terms, then reproduce one real Extract Method case with positive/negative controls through a safe shared evaluator. Only then begin local generation and the controlled three-mode pilot. No screened option is currently proven both locally executable-ready and fully provenance-resolved; do not invent readiness to force a recommendation.
