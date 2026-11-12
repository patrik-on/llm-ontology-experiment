# Three real Defects4J cases, full-class-v2 (2026-11-12)

Explicit opt-in protocol/config: defects4j_three_case_full_class_v2. Historical
baselines, old run artifacts, canonical templates and default runtime config are
unchanged. No training, index rebuild, full benchmark/regression suite, paid calls
or push. This is an exploratory systems comparison; overlap audit was explicitly
deferred by the user. No new overlap investigation is part of this run.

## Preregistered scope

Run: artifacts/evaluation/runs/real-d4j-fullclass-v2-20261112/.
selection.json predates any new model output. Active official IDs: Lang-24,
Lang-26, Lang-27. All are Commons Lang, a pragmatic small same-project sample,
not a representative multi-project estimate. Lang-24 was previously explored;
there is no same-case old/new condition or causal improvement estimate here.

Focal APIs independently resolved from fixed production Java with existing
JavaParser, without original tests/patches/trigger/expected bug values:

- Lang-24: org.apache.commons.lang3.math.NumberUtils.isNumber(String).
- Lang-26: org.apache.commons.lang3.time.FastDateFormat.getDateTimeInstance(int,
  int, TimeZone, Locale).
- Lang-27: org.apache.commons.lang3.math.NumberUtils.createNumber(String).

Preparation uses existing Defects4J prepare, separate fixed/buggy checkouts and
binaries, pinned Temurin Java 11/Jupiter 1.11.4 and exported production-only
classpaths. Only two bounded official git revision pairs were fetched into the
existing local bare subject repository (depth=2), no all-project initialization.
Build review reused the existing Lang.pm/Lang.build.xml/Ant path; official generated
Ant files and production source snapshots are in
/home/patrik/benchmark-work/provenance/pilot-v2/. Framework remains official
Defects4J v3.0.1 commit 6d54320e0db5a357f9ab38a8e4d2e5aead7e1c09.
Apache Commons Lang remains Apache-2.0, framework MIT; per-checkout notice/license
hashes and toolchain hashes are recorded in prepared.json.

Preparation compiles both production revisions plus existing developer tests as
required by defects4j compile, but does not execute their regression suites.
One model-free class-loading/Jupiter health test is run per revision (not a gold
fault oracle). Existing pinned evaluator lifecycle/abnormal-exit controls are
reused from the prior defects4j_jupiter_v1 final-QA report; no redundant full
control matrix per case. Nonindexable benchmark manifests bind each prepared file.

## Frozen generation and evaluation

Exactly 3 cases x ft_testing/rag_single/rag_multi, one attempt per cell, maximum
9 local generation calls including failures. No retries, replacement calls,
manual output repair, prompt tuning after output, or deletion of failed attempts.
Atomic exclusive attempt directories prevent resume duplication; job_plan.json
lists all nine cells. freeze.json binds actual source/config/profile, prepared
files and precomposed per-case/envelope prompts before generation.

All arms use unchanged substantive testing-full-class-v2 requirements and the
same compiled Labels demonstration, seed 42, greedy/temperature 0, top-p .9,
4096 new tokens and the same visible fixed-production focal context. Opt-in real
case construction also includes parsed visible public API signatures, never gold
reference tests, patches, buggy source or expected bug outcomes. FT uses existing
load_eval_model/generate_prediction with unchanged PEFT adapter and NF4 raw-Java
instruction envelope; its three cases reuse one loaded model sequentially.
RAG uses existing RagExperimentRunner, canonical TestingAnswer JSON, zero structured
retries, original V3 mixed or testing_db+refactoring_db/RRF retrieval, shared
Ollama provider and unchanged index. Ollama Q4 instruct rendering vs HF NF4/raw
are explicit backend differences, not an isolated fine-tuning ablation.

Review every generated Java source before evaluate --reviewed-local-execution.
No OS sandbox is claimed. Existing scrubbed environments/resource/process-group
limits and evaluator rules remain unchanged (container failures/aborts/zero tests
reject; abnormal exits including 137 are not bug detections).

Identical unchanged generated source is independently compiled/executed twice on
each revision. Functional success requires compiled positive fixed execution and
fixed class pass. Genuine bug detection additionally requires stable buggy
assertion failures, never compile/setup/infrastructure errors. Requested 2-4 test
methods is prompt adherence only, never a functional acceptance gate. Coverage
is not instrumented or reported.

## Commands

Run inside WSL repository .venv_wsl only:

~~~bash
python -m llm_ontology.benchmarks.defects4j_pilot prepare --run-id real-d4j-fullclass-v2-20261112 --reviewed-local-execution
python -m llm_ontology.benchmarks.defects4j_pilot generate --run-id real-d4j-fullclass-v2-20261112 --arm ft_testing --diagnostic
# Inspect every generated.java before local execution.
python -m llm_ontology.benchmarks.defects4j_pilot evaluate --run-id real-d4j-fullclass-v2-20261112 --arm ft_testing --reviewed-local-execution
# Repeat generate/review/evaluate once each for rag_single and rag_multi.
python -m llm_ontology.benchmarks.defects4j_pilot report --run-id real-d4j-fullclass-v2-20261112
~~~

Full runtime artifacts (prompts/raw/schema/source/hashes/model+adapter+index
identities/logs/XML/tokens/finish/repeats) stay ignored under the run directory,
not committed. A small aggregate JSON and this report are committed selectively.

## Model-free preparation result

All three cases built both revisions successfully: production class counts
Lang-24 143/143, Lang-26 139/139, Lang-27 140/140 (fixed/buggy).
All six revision class-loading/Jupiter canaries pass with one started/succeeded
test each. A first Lang-26 checkout failed before any model call because shallow
fetched commits lacked reachable local refs; official fixed refs were added,
failed directories/logs retained, and preparation resumed. No case substitution.

## Generation/evaluation results

All results below retain failed attempts; no generated source was repaired.
Fixed and buggy each have two independent evaluations per candidate.

FT produced method snippets rather than complete classes on all three real cases.
Lang-24 and Lang-27 reached the 4096-token limit; Lang-26 stopped at EOS (49
output tokens) but was still only a snippet. The shared evaluator classified all
three as invalid_source on both repetitions of both revisions, before javac.
No generated FT test actually started. This is an observed output failure, not
an infrastructure blocker or a reason to replace a case.

Single RAG produced schema-valid, nontruncated JSON for all three cases, but all
three Java candidates failed compilation on both revisions and both repetitions:
Lang-24 omitted method return types; Lang-26 omitted Locale/TimeZone imports and
misused overloaded API arguments; Lang-27 omitted the Jupiter Test import.
No generated Single-RAG test actually started. Valid JSON is not Java validity.

MultiRAG likewise returned schema-valid, nontruncated JSON for every case, but
all three Java candidates failed javac on both revisions/repeats: Lang-24 omitted
return types (and the Test import), Lang-26 emitted invalid "group void" declarations
and unavailable API names, and Lang-27 omitted the Jupiter Test import.

### Aggregate (all attempts retained)

| Arm | Attempted / generated | Compiled | Fixed class pass | Genuine bug detection | Source-invalid / javac failures | Truncated |
|---|---:|---:|---:|---:|---:|---:|
| FT testing | 3 / 3 | 0/3 | 0/3 | 0/3 | 3 / 0 | 2/3 |
| Single RAG | 3 / 3 | 0/3 | 0/3 | 0/3 | 0 / 3 | 0/3 |
| MultiRAG | 3 / 3 | 0/3 | 0/3 | 0/3 | 0 / 3 | 0/3 |
| Overall | 9 / 9 | 0/9 | 0/9 | 0/9 | 3 / 6 | 2/9 |

Exactly **9 actual local generation calls**, one per cell, no retries or repairs.
All six RAG JSON envelopes validate (one structured attempt each); schema failures
0/9 and generation/evaluation infrastructure failures 0/9. The resolved pre-generation
checkout issue is separate from model outcomes. "Generated" means nonempty extracted
source, not a valid complete Java class. Truncation overlaps source-invalid failures.

Every candidate received four fresh evaluator attempts: twice fixed, twice buggy,
**36 total**. The three FT snippets were rejected before javac (12 invalid-source
outcomes); the six RAG classes reached javac and failed all **24 compilation attempts**.
Therefore **zero generated Jupiter launches**, and every fixed/buggy per-repeat count
is: started=0, succeeded=0, failed=0, aborted=0, skipped=0. Compiler failures are NOT
failed executed tests. Candidate class failures are 9/9; genuine bug detections 0/9.
There is no generated-test XML because no generated candidate reached Jupiter;
all six independent model-free revision health checks have fresh passing XML.
Repeated failure statuses agree; this is not evidence of passing behavioral stability.

Source Test-annotation counts (FT / Single / Multi) are 1/3/3 for Lang-24,
1/4/4 for Lang-26, and 1/6/6 for Lang-27. These are explicitly syntax/adherence
proxies, not valid-method or executed-test counts. Requested 2-4 is never used
as an acceptance gate. Coverage was not measured.

### Per-case exact generation outcomes

| Case | Arm | Input/output tokens | Finish | Fixed / buggy class status (both repeats) |
|---|---|---:|---|---|
| Lang-24 | FT | 2298 / 4096 | length | invalid_source / invalid_source |
| Lang-26 | FT | 1523 / 49 | eos | invalid_source / invalid_source |
| Lang-27 | FT | 2791 / 4096 | length | invalid_source / invalid_source |
| Lang-24 | Single RAG | 5764 / 528 | stop | compile_failure / compile_failure |
| Lang-26 | Single RAG | 4774 / 361 | stop | compile_failure / compile_failure |
| Lang-27 | Single RAG | 4557 / 601 | stop | compile_failure / compile_failure |
| Lang-24 | MultiRAG | 8243 / 585 | stop | compile_failure / compile_failure |
| Lang-26 | MultiRAG | 10624 / 362 | stop | compile_failure / compile_failure |
| Lang-27 | MultiRAG | 12179 / 629 | stop | compile_failure / compile_failure |

The complete small aggregate is
[defects4j_three_case_full_class_v2_results.json](defects4j_three_case_full_class_v2_results.json).
It includes per-cell/per-arm per-repeat test counts, source/prompt/schema/raw hashes,
model/adapter/index identities and separate source-invalid/javac/truncation categories.
HF retains the unchanged b2_testing_v2 adapter/NF4 raw envelope; Ollama reports
Q4_K_M and canonical JSON. Single/Multi normalized-prompt hashes match per case.

Evidence under the run root:

- selection.json, job_plan.json, freeze.json: case preregistration, nine-call cap,
  frozen actual source/config/toolchain/profile/prepared prompt identities.
- cases/<ID>/prepared.json and benchmark_manifest.json: active upstream revisions,
  distinct synthetic checkout commits, production/dependency/toolchain identities,
  nonindexable benchmark role.
- cases/<ID>/predictions/<arm>/: atomic attempt, exact prompts/raw/schema, original
  extracted source, generation/finish/token metadata, model/index identities, review.
- cases/<ID>/metrics/<arm>/: four independent evaluator results and actual javac logs.
- cases/<ID>/health/: fresh model-free launcher logs/XML; reused evaluator/demo
  control provenance is linked separately, not included in benchmark scores.
- reports/aggregate.json, artifact_inventory.json and analysis/finalize_report.py:
  independently cross-checked 9-call/source/prompt/schema/repeat evidence and hashes.

Verification: **38 targeted tests passed** (one pre-existing harmless Pydantic
collection warning), scoped Ruff clean, changed modules py_compile clean, git diff
--check clean. No full regression suite was run. Frozen identities and all nine
source hashes match; no source edits occurred between generation/review/evaluation.

**Conclusion:** real subject preparation and evaluator rejection paths are operational,
but this bounded new-profile sample produced **no executable generated candidate**
from any arm. It does not establish improvement or support a final benchmark claim.
The prior tiny synthetic format-validation success does not transfer to these real
production contexts. These negative functional results complete the authorized pilot;
no additional generation, retraining or automatic repair was started.
