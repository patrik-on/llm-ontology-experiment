# Repository architecture, data and benchmark audit — 2026-11-12

## 1. Scope, evidence and verdict

This audit records read-only investigation of the repository on Windows MSI, with runtime inspection and selected tests inside Ubuntu WSL. Repository HEAD at inspection: `e020e50` (`Merge repository reorganization and preserve SI context eval bridge`). The final experimental runtime remains WSL/Linux; Windows is the host OS only.

**Verdict:** the shared inference/retrieval architecture is substantial and tested, but the repository is not ready for defensible final TestBench/SWE-Refactor comparisons. Missing external data is only one blocker. The benchmark command currently bypasses the controlled runner, has incompatible raw-Java/JSON output requirements, and lacks full executable evaluation. Materialized fine-tuning data has independently verified train/test leakage. The only local Chroma index is V3, while existing baseline and UI defaults point to a missing older root.

### Evidence labels

- **Observed:** directly read local source/config/artifacts, live runtime inspection, or an executed lightweight inspection/test.
- **Stored claim:** an existing document/report states this; it was not independently reproduced end-to-end.
- **Proposal:** a recommended future change, not something implemented or executed by this audit.

The initial investigation changed no repository files. This document is the sole subsequently authorized documentation addition. No installations, model generation, paid APIs, external project builds, configuration/scheduler changes, commits or pushes were performed. Unit tests used temporary fixtures, disabled bytecode writes and disabled pytest cache updates.

### Protected existing working-tree changes

The following were already dirty and were not modified or committed:

```text
 M .gitignore
?? docs/datasets/data_audit_report.md
?? docs/datasets/handcrafted_smoke_all_cases.md
?? docs/datasets/raw_record_examples.md
?? scripts/datasets/build_presentation_data_docs.py
```

The three untracked dataset documents were inspected read-only. The audit document target was confirmed absent before creation.

## 2. Architecture and active research areas

Entry documents inspected first: `devinfo.md` and `README.md`. Additional architecture/methodology sources include `docs/architecture/project_map.md`, `docs/experiments/design.md`, `docs/experiments/baseline_v1.md`, `docs/retrieval/rag_v3.md`, `docs/experiments/testbench_runbook.md`, `docs/finetuning/v2_runbook.md` and `docs/evaluation/v2_runbook.md`.

| Area | Source boundary | Observed responsibility |
|---|---|---|
| Dataset preparation | `src/llm_ontology/datasets/` | Methods2Test/ML4Refactoring/MaRV parsing, normalization, split/group logic and mixtures |
| Fine-tuning | `finetuning/`, `finetuning/training/`, `models/` | HF/PEFT LoRA/QLoRA, masked labels, checkpoint/resume, adapter handoff |
| Ingestion | `ingestion/` | Role manifests, identity/fingerprint checks, Java/pair documents, production corpus selection |
| Persistence | `vectorstore/` | Chroma abstraction, collection manifests and explicit index lifecycle |
| Retrieval | `retrieval/pipeline.py` | Direct bypass, Single RAG, parallel MultiRAG, deduplication, RRF, global top-k and initial context selection |
| Inference | `inference/experiment_runner.py` | Shared prompt construction, token budgeting, structured generation and experiment records |
| Evaluation | `evaluation/` | Prediction normalization, proxy metrics, aggregation/reporting and evaluation layouts |
| Experiments | `experiments/smoke_runner.py` | Resumable smoke matrix, baseline identity/preflight, fairness and reports |
| Benchmarks | `benchmarks/` | Normalized case loaders, direct prompt runner and TestBench Maven execution |
| UI | `ui/service.py` | Shared service/runner composition and environment status |

Fine-tuning, retrieval, inference, evaluation, experiments and UI are active areas; lack of use in one smoke configuration does not make an area obsolete. Ontology/GraphRAG and literature are not part of the observed baseline.

The `scripts/experiments/benchmarks/context_eval_bridge.py` entrypoint bridges the sibling `si-context-eval` project. Its data and outcomes are separate from TestBench and SWE-Refactor. Existing SI-context analysis artifacts must not be merged into those benchmark results.

### Two active prompt/execution families

**Observed:** controlled Ollama Direct/RAG/MultiRAG uses the canonical JSON task contract from `inference/prompting/canonical.py`, exposed through `ApproachPromptBuilder`. The only intended approach-dependent prompt block is retrieved evidence.

HF training/internal evaluation uses `inference/prompting/instruction.py`:

```text
### Instruction:
...
### Input:
...
### Response:
```

`finetuning/prompt_formatter.py` is a compatibility import of that instruction formatter, not the canonical JSON builder. Existing fine-tuning and Ollama experiments therefore cannot be assumed to have identical prompt/runtime controls merely because some utilities are shared.

**Proposal:** declare prompt format, quantization/runtime, model/adapter identity and evaluation contract explicitly when composing the fine-tuning and retrieval research axes. Preserve existing historical contracts rather than silently rewriting them.

## 3. Dataset roles and provenance

### Source-to-record mapping

| Source | Input | Target/output | Current uses and limitations |
|---|---|---|---|
| Methods2Test | Usually `src_fm` focal Java method | Developer-written `target` JUnit test | Training, internal evaluation and retrieval demonstrations; method-only inputs often omit imports/class/build context |
| ML4Refactoring | Before-refactoring Java file | Corresponding after-refactoring file | Repurposed historical refactoring source for generation; may be whole-file and contain additional changes |
| MaRV | `code_before` | `code_after` | Refactoring mixture with reviewer votes preserved but not quality-filtered |
| Handcrafted smoke | Versioned source/requirements | Hidden validation expectations/reference fixtures | Pipeline/regression/smoke evaluation only; no training/indexing |
| TestBench | Parser-produced source/context variants | Generated test, assessed executably | External benchmark data not locally available at configured root |
| SWE-Refactor | Pure-refactoring before code/type | Generated transformation, reference after code kept hidden | External benchmark data not locally available at configured root |

Implementation sources: `datasets/methods2test.py`, `datasets/ml4refactoring.py`, `datasets/marv.py`, `datasets/final_datasets.py`, `benchmarks/smoke.py`, `benchmarks/testbench.py`, `benchmarks/swe_refactor.py`.

### Independently verified materialized counts and leakage

**Observed:** a read-only Python inspection loaded each processed JSONL and compared exact `(input, output)` pairs. Duplicate counts below mean excess rows beyond unique exact pairs. Cross-split overlap means unique pairs present in both train and test.

| Dataset directory under `data/processed/` | Train / val / test | Train excess exact pairs | Train/test exact-pair overlap |
|---|---:|---:|---:|
| `testing` | 4000 / 500 / 500 | 8 | 0 |
| `refactoring_ml4ref` | 4000 / 500 / 500 | 1325 | **188** |
| `refactoring_marv` | 478 / 100 / 108 | 1 | 0 |
| `refactoring` | 4478 / 600 / 608 | 1326 | **188** |
| `combined` | 8000 / 1000 / 1000 | 1333 | **188** |

ML4Refactoring, final refactoring and combined each share **11 explicitly populated project names between train and test**. For Methods2Test/MaRV, absence of populated `project` overlap alone is not proof of repository disjointness: older records do not consistently materialize that field.

Observed train SHA-256 values:

```text
testing/train.jsonl
6a2ebc5d0dbbfd2f2dbc4b653a45ec9fdc4f9ae836da3a64f1f44e8d5f09b401
refactoring_ml4ref/train.jsonl
453132a5777cf08f38d6a09b511e2c1167cb4a3a78e8c3723c608534c1f0ca19
refactoring_marv/train.jsonl
410657fed2781a02ca823ba068b12fadb39ad0b0147f1e15576fffb8a4e79b43
refactoring/train.jsonl
f70853aa924a9d212d5701f31af14f34b8e2f2232b61700a8c2590a13a64aabb
combined/train.jsonl
3aa28a139a03b6785d021d7699bb3f0ad02f8b029e0b227c71cb41738d1cc875
```

These results support the warnings in the untracked `docs/datasets/data_audit_report.md`: materialized data does not satisfy the stronger group-aware contract in current preparation code. The 188 shared pairs are a direct final-evaluation blocker for affected fine-tuned models, not merely a documentation concern.

### Current preprocessing gaps

- **Methods2Test:** `corpus_files()` sorts paths; `collect_subset()` stops at the first valid records up to each limit. `require_project_disjoint_official_splits()` checks official source partitions, but sampling remains lexicographic rather than seeded representative sampling. Current code adds project/repository identity; existing processed records reflect older preparation.
- **ML4Refactoring:** projects and files are traversed in sorted order with an early global sample cap. Refactoring type is inferred by filename substring; unsupported types become `unknown`. Current `split_records()` requests project-level grouped splitting, but existing JSONL overlaps. Simply rerunning without an explicit deduplication/sampling/label protocol is not sufficient.
- **MaRV:** `build_instruction_records()` filters content/length but not reviewer quality. `stratified_split()` now delegates to commit grouping; the name does not itself demonstrate type-stratified or repository-disjoint sampling.
- **Mixtures:** `final_datasets.py` hardcodes expected counts. Combined contains Methods2Test plus ML4Refactoring only, not MaRV. Equal row counts do not control token volume or optimization exposure.

**Observed MaRV votes across all 686 processed records:** 321 `(1,1)`, 79 `(0,0)`, 3 `(-1,-1)`, 278 conflicting two-vote records, 5 single-vote records. The negative and uncertain examples are currently used as ordinary positive generation examples.

### Raw/local availability

**Observed:**

- `data/raw/methods2test` exists with expanded corpus directories. A complete new raw-corpus recount/checksum was not performed.
- `data/raw/ML 4 Refactoring dataset/all.zip` exists and is **40,783,884,999 bytes**.
- `/mnt/c/datasets/ml4refactoring/all/dataset` contains **11,150 project ZIPs**.
- `data/raw/marv` exists.
- All five processed dataset directories listed above exist.
- `benchmarks/TestBench-main` and `benchmarks/swe-refactor/SWE-Refactor` do not exist. A bounded depth-five search under `/home/patrik` and the GitHub workspace found no matching directories. This is not an exhaustive search of all disks.

### Fine-tuning truncation

`finetuning/training/finetuning.py:258–279` appends EOS and masks prompt labels with `-100`. On overflow, it retains the **end of the prompt** and **beginning of the output**. Therefore it can remove instructions/class context or truncate the target Java source. `DataCollatorForSeq2Seq` uses `label_pad_token_id=-100`.

**Stored claim, implementation corroborated but token audit not rerun:** the untracked audit reports 1327/4000 ML4Refactoring train examples above 2048 tokens and 162 truncated target outputs. It also reports approximately 85% pre-truncation token contribution from ML4Refactoring in the row-balanced combined mixture.

**Proposal:** version a tokenizer-aware preparation report and target-completeness policy before retraining. Retrieval filtering cannot repair contaminated training splits or retroactively clean adapters.

## 4. Retrieval/index contracts and observed index state

### Implemented controls

- `ingestion/manifest.py::DatasetManifest.require_indexable()` requires explicit indexing permission and retrieval role. Source split and experiment usage role are distinct concepts.
- `ingestion/production.py::build_production_indexes()` verifies hashes/counts, excludes benchmark identities/fingerprints, reruns audits and requires safe reports before writing indexes.
- `vectorstore/manifest.py` and `vectorstore/lifecycle.py` enforce embedding identity and explicit rebuilds; reads must not silently migrate or rebuild.
- `retrieval/pipeline.py::VectorRetriever` bypasses vector search for Direct. MultiRAG queries configured collections in parallel, deduplicates evidence, applies RRF and takes one global top-k.
- `docs/retrieval/rag_v3.md` and `configs/retrieval/ollama_bge_m3_v3.yaml` define task-aware queries, input-side embeddings, candidate pool 12, deterministic code-aware reranking and final top-k 3. Paired reference outputs remain retrievable demonstrations but do not determine V3 embedding/reranking similarity.

### Independently observed SQLite counts

SQLite was opened using a read-only URI (`mode=ro`), not through a potentially initializing Chroma client. The query joined `collections`, `segments` and `embeddings`:

```sql
SELECT c.name, COUNT(e.id)
FROM collections c
JOIN segments s ON s.collection = c.id
JOIN embeddings e ON e.segment_id = s.id
GROUP BY c.name;
```

| Collection | Actual documents | Dimension |
|---|---:|---:|
| `mixed` | 5739 | 1024 |
| `testing_db` | 3978 | 1024 |
| `refactoring_db` | 1761 | 1024 |

Only `data/chroma/ollama_bge_m3_v3/chroma.sqlite3` was present; size **305,373,184 bytes**. Its manifests specify WSL, Ollama `bge-m3`, embedding template `2`, chunker/pipeline `rag-v3`, and digest `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`.

### Stored production report

`artifacts/retrieval/indexes/ollama_bge_m3_v3_production_report.json` states:

| Domain | Original train | Identity exclusions | Fingerprint exclusions | Safe candidates | Unique indexed |
|---|---:|---:|---:|---:|---:|
| testing | 4000 | 0 | 14 | 3986 | 3978 |
| refactoring | 4478 | 2382 | 53 | 2043 | 1761 |

It reports equivalent Single/Multi corpus and literature not indexed. Current V3 dataset-manifest IDs are `65566aa4b7dae00e08bbda4df18ea382e4614673367dac2f61a37b7c5f5da48f` and `cee3de073f7d5736379cda3db66d9252183f68138827ff6dcb08f4528009b00d`. The report is historical builder evidence; this audit verified counts, not a complete regeneration of its exclusions or vector equality.

### Gaps and stale claims

1. General `IndexingPipeline.run(..., manifest=None)` permits absent manifests. Split checks alone cannot stop benchmark cases relabeled as train. The production builder is stronger than the generic API.
2. Production reservation currently concerns internal testing/refactoring test manifests, not the absent external benchmarks. External project/commit/code fingerprints must be reserved against training, retrieval and tuning data.
3. `data/smoke/leakage_report.json` is dated 2026-08-20 and refers to older dataset manifest IDs (`86640657…`, `6dcbeeff…`), not current V3 IDs.
4. `experiments/smoke_runner.py:457–460` checks `overall_safe` but does not fully bind that report to current collection/fingerprint identities.
5. `configs/datasets/manifests/refactoring_retrieval.yaml` is named `ml4refactoring_retrieval` although its source contains ML4Refactoring and MaRV. Its declared method grouping can reduce to a coarser project/commit identity when method IDs are absent.
6. Explicit validation-role exclusion/audit remains necessary; train-only retrieval selection is not by itself proof of cross-role source disjointness.

## 5. Runtime, models and configuration drift

### Live WSL observations

| Component | Observed value |
|---|---|
| Runtime | Ubuntu WSL2 on MSI |
| Kernel | `6.18.54.1-microsoft-standard-WSL2` |
| `.venv_wsl` Python | 3.13.11 |
| Java | OpenJDK 17.0.20.1 |
| Maven | 3.9.16, `/home/patrik/.local/opt/apache-maven-3.9.16` |
| GPU | NVIDIA GeForce RTX 3080 Laptop GPU, 16384 MiB |
| GPU driver | 596.36 |
| Package metadata | torch 2.11.0; transformers 4.57.6; peft 0.19.1; bitsandbytes 0.49.2; chromadb 1.5.9; pytest 9.0.3 |

Package metadata availability does not prove every CUDA/training path works. No model was loaded or generated.

`curl -sf --max-time 5 http://localhost:11434/api/tags` inside WSL succeeded. Relevant live identities:

```text
qwen2.5-coder:7b
dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364
bge-m3:latest
7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab
```

Both match the frozen digest values in existing baseline configs. The endpoint was only inspected; generation/embedding requests were not issued.

The HF base config `/mnt/c/models/huggingface/Qwen2.5-Coder-7B-Instruct/config.json` and each V2 adapter config under `/home/patrik/experiments/llm-ontology-v2/{b1_shared,b2_testing,b2_refactoring}/checkpoints/final_adapter/adapter_config.json` exist. This confirms config-file presence, not complete weights, valid training provenance or loadability.

`TESTBENCH_JAVA8_HOME` and `TESTBENCH_JAVA17_HOME` were unset. Standard `/usr/lib/jvm` listing showed JDK17, not JDK8. JDK8 availability elsewhere was not exhaustively checked.

### Observed path/version drift

- `configs/retrieval/ollama_bge_m3.yaml` and `configs/retrieval/ollama_bge_m3_v2.yaml` point to missing `data/chroma/ollama_bge_m3`.
- `configs/ui/local.yaml` selects the former configuration.
- Both `data/chroma/ollama_bge_m3` and `data/chroma/ollama_bge_m3_v2` are absent; only V3 exists.
- `configs/retrieval/ollama_bge_m3_v3.yaml` points to the present V3 root.
- `configs/experiments/baseline_v3.yaml` is absent.
- V3 docs describe preserving a V2-specific index root, but actual V2 configuration uses the unversioned root.
- README/devinfo describe older baseline status. Stored `artifacts/experiments/smoke/baseline_v2/report.md` already reports 72 successful recorded cells, versus README describing a six-run pilot and pending full matrix.

**Proposal:** do not redirect frozen V1/V2 configs to V3 in place. Restore historical assets if needed, or define a separately reviewed/frozen contract with current identities and refreshed leakage evidence.

## 6. Benchmark adapters and execution gaps

### 6.1 Shared benchmark CLI is not the controlled experiment runner

`benchmarks/runner.py::run_cases()` prepares direct prompts and optionally calls a string generator. `scripts/experiments/benchmarks/run_benchmark.py` does not load `configs/benchmarks/*.yaml` and does not use `RagExperimentRunner`. Consequently the benchmark YAMLs are not the effective executable contract for that CLI.

Missing there: Direct/RAG/MultiRAG matrix, frozen preflight, prompt artifacts/hashes, model digest recording, token/latency/retrieval trace, shared structured validation and resume. It writes arbitrary `--output` using write mode, rather than the guarded evaluation run layout (`evaluation/run_layout.py`) and immutable run identity.

### 6.2 Confirmed output-contract conflict

`benchmarks/testbench.py:14–18` instructs the model to return only Java. The canonical builder simultaneously requires JSON (`inference/prompting/canonical.py:139`). An in-memory prompt construction confirmed both requirements occur together.

The benchmark CLI stores the raw result of `generate_with_ollama()` as `prediction`. TestBench execution expects Java, not a `TestingAnswer` JSON envelope. Existing tests validate the adapter instruction and builder separately; they do not catch this integrated incompatibility.

**Proposal:** reuse shared structured generation, preserve raw/schema responses, and explicitly extract `generated_tests`/`refactored_code` into an execution-source field. Keep the same approved contract across approaches; do not silently change frozen prompts.

### 6.3 TestBench

**Implemented:** source/simple/full context loading, target package/class/method, project/source/execution metadata, synthetic adapter tests. Real upstream schema/count compatibility was not verified because data is absent.

Adapter gaps: weak required-field validation; missing context silently reduces the effective input; IDs include a record index; uniqueness/overload policy is not pinned; generation does not enforce expected 108 cases.

`benchmarks/testbench_execution.py` has useful safety measures: path containment/traversal rejection, argument-based Maven invocation, optional missing-package repair, project JAVA_HOME, timeout, collision backup/restoration in `finally`, and a dry-run that does not write Java or run Maven.

**Critical confirmed bug:** Maven flags include `-Dsurefire.failIfNoSpecifiedTests=false` and `-DfailIfNoTests=false` (lines 132–133), while `_status_for_process()` returns `accepted` for every zero exit code (lines 170–172). Direct in-memory reproduction:

```text
_status_for_process(0, "Tests run: 0, Failures: 0, Errors: 0")
=> accepted
```

Thus accepted does not establish positive test discovery/execution.

Other gaps:

- No JaCoCo or PIT integration in this evaluator; runbook acknowledges this.
- No baseline project-health gate before scoring a generated candidate.
- No execution sandbox: generated tests and Maven plugins run with host permissions.
- Restoring one source file is not full workspace restoration; build outputs/other side effects remain.
- Regex class/package parsing is limited; an existing wrong package is not checked against metadata.
- Config/CLI defaults differ, including 600 versus 300 seconds timeout.
- Evaluation CLI succeeds despite ordinary compile/test failures; only invalid-record status drives its final nonzero exit. Consumers must read per-case statuses rather than treating command success as candidate correctness.

**Readiness defects:** `benchmarks/readiness.py:98` calls `shutil.disk_usage()` on the missing root after catching loader failure. A read-only call with `backend="prompt-only"` reproduced `FileNotFoundError`. `_ollama_check()` at line 45 accepts another tag in the same model family and does not verify digest. Benchmark readiness does not enforce the shared final WSL environment contract.

### 6.4 SWE-Refactor

`benchmarks/swe_refactor.py` loads a list from `pure_refactoring_data.json`, filters `isPureRefactoring`, keeps before/reference-after code, type/project/commit/path and upstream compile/test metadata, and supports whole-file fallback. Existing tests cover synthetic records and an empty-string fallback.

**Confirmed edge bug:** `_first_text()` converts JSON null to literal `"None"`, preventing valid fallback. In-memory reproduction with null primary code and nonempty whole-file code returned `"None"`. This verifies a code defect, not the prevalence of nulls in absent real data.

Missing repository-level evaluation/application contract:

- pinned parent checkout/worktree preparation;
- method/file replacement location and conflict checks;
- after-path/multi-file mapping for move/compound cases;
- compilation and tests for the generated solution;
- automated detection of the requested refactoring;
- executable behavior-preservation success gate;
- SWE-specific readiness/evaluation command.

`compileResultBefore`, `compileResultCurrent` and `hasTestC` are upstream metadata, not evaluation of generated code. Current support is accurately described as a loader/prompt-preparation adapter, not a completed executable benchmark integration.

The canonical refactoring prompt requests complete Java source while preserving public method signatures. Repository-level move/compound edits require an explicit approved output/application contract; one returned source string is not automatically sufficient. A contract adjustment must be shared across compared approaches and versioned, not made implicitly during integration.

## 7. What current evaluation can and cannot establish

`experiments/smoke_runner.py:581–599` extracts code and calls `compute_testing_metrics()` or `compute_refactoring_metrics()`. It does not compile/execute generated output.

- `evaluation/test_metrics.py` scores annotations, assertions, invocation-name occurrence, exception markers and triviality indicators. Coverage proxy is the same heuristic score as test quality, not measured coverage.
- `evaluation/refactoring_metrics.py` combines edit similarity and structural proxies. It does not prove behavior preservation or the requested transformation.
- `benchmarks/smoke_validation.py` validates dataset/reference fixtures. Correct reference fixtures do not establish generated-candidate correctness.
- Structured JSON validation checks fields and nonempty code strings. It does not establish Java syntax/type correctness. Format-only repair is a prompt policy, not a verified invariant that code semantics remain unchanged.

**Stored claim:** `artifacts/experiments/smoke/baseline_v2/report.md` reports 72/72 successful, fairness PASS. Interpret this as completed pipeline/structured generation with proxy metrics, not 72 executable-correct Java solutions. It shows identical testing proxy aggregates across modes, illustrating why those metrics cannot alone distinguish semantic quality.

`artifacts/experiments/testing_v2_analysis_20261006.md` documents useful model failure examples from separate SI-context experiments: incorrect assertions/fixtures, missed state/boundary sequences, partial compiler repairs and one output-limit degeneration. Those observations motivate robust executable checks but are not TestBench/SWE results.

## 8. Executed lightweight validation

All commands below ran inside Ubuntu WSL from:

```text
/mnt/c/Users/patri/OneDrive/Dokumenty/GitHub/llm-ontology-experiment
```

### Benchmark, architecture, data and fairness tests

```bash
PYTHONDONTWRITEBYTECODE=1 .venv_wsl/bin/python -B -m pytest \
  -p no:cacheprovider \
  tests/test_architecture.py \
  tests/experiments/test_benchmarks.py \
  tests/experiments/test_benchmark_edge_cases.py \
  tests/experiments/test_testbench_prompt.py \
  tests/experiments/test_testbench_execution.py \
  tests/inference/test_prompt_fairness.py \
  tests/datasets/test_reproducibility_and_group_splits.py \
  tests/evaluation/test_metrics.py -q
```

**Observed result:** `29 passed in 4.69s`, exit code 0.

### Shared runner, V3 relevance and WSL contract tests

```bash
PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
.venv_wsl/bin/python -B -m pytest -p no:cacheprovider \
  tests/inference/test_rag_stage3_runner.py \
  tests/retrieval/test_rag_v3_relevance.py \
  tests/experiments/test_smoke_runner.py \
  tests/retrieval/test_wsl_runtime.py -q
```

**Observed result:** `36 passed in 3.81s`, exit code 0.

**Total: 65 passing targeted tests.** These validate mocked/synthetic contracts, not unavailable upstream datasets or live model generation. No Maven benchmark build, model load or generated-code execution was performed.

Additional inspections: JSONL counts/hashes/exact pair overlaps; read-only SQLite counts; WSL tool/package/file presence; local Ollama tags; in-memory reproductions of null fallback, zero-test acceptance and contradictory prompt requirements; missing-root readiness exception.

`git diff --check` passed after the initial audit, with only a warning that existing `.gitignore` CRLF would be normalized if Git later touched it. The preexisting working-tree status remained unchanged. Because new files are untracked, final documentation verification must also explicitly check this file rather than rely only on default `git diff`.

## 9. Live primary-source checks

The following URLs returned HTTP 200 during this audit on 2026-11-12:

| Source | Live-confirmed information |
|---|---|
| https://arxiv.org/abs/2602.03712 | SWE-Refactor: 1099 developer-written cases, 18 Java projects, 922 atomic and 177 compound; compilation/test/refactoring-detection validation |
| https://arxiv.org/abs/2409.17561 | TestBench: 108 Java programs, nine projects, three contexts; syntax, compilation, correctness, coverage and defect-detection metrics |
| https://github.com/microsoft/methods2test | Methods2Test repository available; focal-method/test dataset source |
| https://zenodo.org/records/3547639 | ML4Refactoring V1; before/after source `all.zip`, 40.8 GB, MD5 `0e26e937b40534466e72724f1aefecda` |
| https://zenodo.org/records/14450098 | MaRV V2; published description states 693 evaluated code pairs from 126 Java repositories |

The SWE paper separates functional correctness from human-likeness; CodeBLEU is not its behavior-preservation proof. Exact benchmark release revisions/checksums, release licenses and real adapter/upstream schema compatibility remain unverified. Paper descriptions are not a substitute for release inspection. The 40 GB local archive was not newly hashed.

## 10. Prioritized integration plan — proposals, not completed work

### P0: correctness and data integrity before final claims

1. Preserve current results/adapters as historical exploratory artifacts. Do not silently repair data beneath their recorded identities.
2. Define and version a new data preparation protocol: deduplicate before splitting; project-safe seeded sampling; explicit MaRV vote policy; complete refactoring type handling; tokenizer-aware truncation/target-completeness reports; source/license/checksum registry.
3. Regenerate affected datasets and retrain models before treating contaminated internal splits as independent final evaluation. Control shared/specialist training size, tokens or steps, or report an explicit size ablation.
4. Acquire pinned official TestBench/SWE releases and inventory them without executing upstream build scripts. Record source revision, license, files/checksums and identity mapping.
5. Reserve external benchmark projects/commits/code fingerprints against every training/retrieval/tuning source. Benchmark manifests must forbid indexing.
6. Fix raw-Java/JSON handoff and require positive TestBench test discovery/execution. Add regression tests for the reproduced failures.

### P1: reuse shared execution, not another pipeline

7. Add benchmark orchestration on top of existing `RagExperimentRunner`, provider factories, canonical prompt builder, structured generation and `ExperimentRecord`. Preserve raw/schema output and extracted execution code separately.
8. Require strict real-data adapter schema/count/unique-ID tests, null-safe SWE fallback and explicit context availability checks.
9. Add baseline project-health checks, isolated working copies/sandboxing, JDK matrix, fixed timeouts/Maven policy and fresh Surefire report parsing. Separate infrastructure failure, compile failure, no tests, skipped tests and candidate failure.
10. Implement SWE repository-level application plus compile/test/refactoring-detection evaluation before presenting SWE success rates.
11. Add pinned JaCoCo/PIT support if claiming the full TestBench metric set; otherwise clearly label a reduced protocol.

### P2: freeze and reproducible experiments

12. Refresh smoke/external leakage evidence bound to current manifests and fingerprint inputs. Strengthen preflight to reject stale reports, not just unsafe booleans.
13. Freeze a separately versioned contract for the actual index/runtime, rather than mutating V1/V2 or pointing them at V3. Resolve documentation/config drift explicitly.
14. Ensure run layout, immutable effective config/environment, prompt hashes, generation/embedding digests, collection/dataset identities, traces, token counts, latencies, raw outputs and evaluator versions are recorded.
15. Validate in stages: synthetic regression tests → real-data inventory → build-only baseline → evaluation planning → explicitly authorized generation canary → controlled small matrix → final batch.

### Suggested next validation commands

The two executed pytest commands above are immediately usable without generation. After benchmark data and the missing-root readiness bug are addressed, run the inspected readiness CLI inside WSL:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv_wsl/bin/python -B \
  scripts/experiments/benchmarks/check_readiness.py \
  --backend prompt-only --json
```

The existing smoke `--dry-run` is not a strictly read-only command: the runner writes configuration/environment/report artifacts. It also currently points at unavailable historical index assets. Do not run it as a no-write audit shortcut. The existing TestBench evaluation `--dry-run` avoids Maven/source mutation but still writes the requested output file. No build/generation command in the runbooks should be interpreted as authorization to execute it.

## 11. Final separation of blockers

| Category | Actual blocker |
|---|---|
| Data | Missing external benchmarks; contaminated materialized refactoring/combined splits; quality/sampling/truncation concerns |
| Environment/assets | Historical index roots absent; no frozen V3 experiment; TestBench JDK environment variables unset; JDK8 not seen in standard JVM directory |
| Code | Direct-only benchmark runner; JSON/Java mismatch; zero-test acceptance; missing-root readiness crash; null fallback; incomplete SWE application/evaluator |
| Methodology/reporting | Proxy success confused with executable correctness; stale leakage identity binding; fine-tuning and Ollama prompt/runtime families not automatically comparable |

The recommended integration is conservative: retain the working shared architecture and historical evidence, close the benchmark execution/provenance contracts, repair and version materialized data, and only then run approved final comparisons.

## Dated correction: SWE-Refactor Zenodo acquisition (2026-11-12)

This additive correction supersedes the earlier missing-data/unresolved-deposit-license findings for SWE only; the preceding investigation remains a historical record. The user-selected source is now pinned to <https://zenodo.org/records/17196850>, DOI **10.5281/zenodo.17196850**, deposited by **anonymous**, with explicit **CC-BY-4.0** record licensing. This establishes a licensed deposit, not independently authenticated paper-author endorsement or blanket licensing of underlying Java projects.

The exact 207,329,781-byte ZIP was downloaded and its published MD5 **f06ee0ce4c8034d57d4d2d1b4c32a24d** matched; computed SHA-256 is **e1bd6eedcdf65c4c6cf4454cf07d3db558cd4ba1706419a409489297f8ea6a65**. Only 10 allowlisted dataset/build-metadata/evaluator-inspection files (67,599,668 bytes) were extracted into the existing configured root, including pure_refactoring_data.json. No old SWE data was present to delete, and reusable adapter/research history was preserved. Newer record 23194601 was noted but not substituted.

Actual local inventory: **1,099 unique cases, 18 projects, six operation types**, 922 atomic/177 compound. All cases load with nonempty before/reference code; three use existing whole-file input fallback. A narrow loader fix prevents explicit JSON null becoming literal None and keeps its fallback flag consistent (the pinned real data has no explicit top-level nulls). WSL adapter/edge tests: **6 passed**; all **1,099 prompt-only records** were prepared and checked without model calls. No upstream scripts, Java builds, installs or indexing were run; canonical prompts, frozen baselines and dataset YAML remain unchanged.

Status is now **DATASET_READY (loading/prompt inspection), EXECUTION_NOT_READY**. Stored metadata is not uniformly successful/complete: two current-compilation flags are false; hasTestC is absent from 1,098 cases; coverage has heterogeneous shapes; 300 commands skip tests and 93 have unmatched quoting. The deposited evaluator retains early success/verification bypasses and test-skipping builds. A safe shared application/evaluator contract, pinned subject checkouts/toolchains, actual baseline/test/operation controls, leakage clearance and controlled three-mode runner integration remain outstanding. Testing benchmark and unrelated audit findings are unchanged.

Full source/license/checksum, selected/excluded asset inventory, schema/counts, caveats and executed verification: [SWE-Refactor Zenodo acquisition](../datasets/swe_refactor_zenodo_acquisition_2026-11-12.md).
