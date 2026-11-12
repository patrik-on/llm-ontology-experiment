# Methods2Test official EVAL hundred-case four-system evaluation v1

## Authorized protocol (before generation)

Run ID: `methods2test-eval-hundred-v1-20261112` (local ignored artifacts).
Exactly the SAME 100 previously unused official EVAL methods for each of pure
Qwen / active testing FT / Single-RAG / MultiRAG: at most 400 charged calls,
one attempt per cell, including failures. Official TEST is not used.
No retries, repairs, output-driven reselection, training, index rebuild, new model,
model pull, GPT-OSS, spend, or upstream subject project builds.

The opt-in config freezes testing-bodies-one-shot-v2, the unrelated solved Labels
example, two neutral body slots, strict two-string JSON, 4096 output tokens,
temperature zero (FT greedy), seed42, context32768 and two fresh JVM executions
of each immutable assembled output. Existing local Ollama Qwen2.5-Coder7B digest
and existing HF NF4 b2_testing_v2 adapter/raw instruction envelope are reused.
Backend, quantization and output envelope differences make this a SYSTEMS
comparison, not a causal isolated FT adapter ablation. Known retrieval
query/identity/regex/lowercase defects remain unchanged.

## Predeclared selection

Bounded streaming archive order of dataset/eval.tar.bz2, matching corpus/json/eval.
Caps: 80,000 records, 3,000,000,000 aggregate payload bytes, 4,000,000 bytes/member;
4,000-byte focal and 6,000-byte reference screen. At most ten per project.
Previously materialized/explored records (including the old five-case screen),
selected train/validation/checkpoint projects, and normalized exact/contained
focal/reference content in current training/validation plus both actual RAG code
sides are rejected before compilation. Actual named RAG/source project identities
are checked when present. Missing metadata is unknown, not affirmative lineage.
Current source/manifest snapshots are pinned; historical training bytes/base
pretraining remain unknowable here, not a reason to substitute TEST or invent data.

Only public static JDK-compatible methods with simple unchanged @Test references,
qualified focal invocation and lexical assertions qualify. Original focal and
reference method bytes are copied verbatim; package inferred from src/main/java,
required explicit JDK imports and recursively referenced original rich-record
fields only. Missing helper method bodies, dependencies, interfaces/inheritance,
annotation/lifecycle/expected semantics or ambiguous bindings are rejected,
never stubbed or rewritten. Assertion binding reuses pinned Jupiter/AssertJ/Hamcrest.
This is extracted-method execution, not an original-project build. Selection is
convenience/dependency filtered and not representative random sampling.

Each candidate must compile -g under pinned Java11 and pass its original reference
with positive nonaborted execution, actual JaCoCo focal METHOD invocation, valid
line counters and distinct JVM descriptor before any model call. Reference
baseline is independent and never mixed into model coverage. If 100 cannot be
honestly prepared, generation must not silently proceed with a partial cohort.

## Execution / metrics

Exclusive persistent per-cell dispatch ledger plus serialized global cap prevents
duplicate dispatch on resume; uncertain interrupted charged calls are never retried.
Sequential GPU: no overlapping FT/Ollama; FT loads once for the batch. Model-file
hashing occurs once, stable file pins checked before reuse. Frozen inputs/scaffolds,
config/schema/prompts/model/index identities and source snapshot precede calls.
Durable progress, timestamps, remaining cells, raw outputs and failure evidence
remain on disk. A first-cell transport/empty/API anomaly stops only the affected
arm; ordinary schema, syntax, compile and assertion failures stay in all100.

Report schema/truncation/syntax/compilation, positive nonaborted execution,
class/per-test pass, instrumented focal invocation, same-output repeat stability,
real JaCoCo0.8.13 focal method/extracted-wrapper-class lines and branches.
Failed executable coverage is diagnostic only; failed candidate success CREDIT=0
is not measured coverage0. Missing passing coverage=null plus infrastructure
reason. Branchless is N/A and excluded from applicable macro denominator.
All-attempt coverage credit and conditional passing-only coverage are separate,
with actual cohort/applicable denominators and pooled counters. Wilson95% pass
intervals and paired per-case descriptive differences do not claim random-sample
population inference. Coverage/lexical assertion calls do not establish assertion
strength, mutation success or real fault detection; no buggy revision is supplied.
Token/timing fields separate backend loading, prompt processing, decode, retrieval,
and identity hashing where recorded; no fake cross-backend speed ranking.

Execution uses reviewed immutable local source hashes, scrubbed environment,
resource/time limits and original process-group cleanup; NOT an OS sandbox or
whole-tree containment. Old pilot/source snapshots/defaults and user dirty files
remain untouched. Only owned code/config/docs/compact manifests/reports may be
committed; never raw private gold, archives, jars, weights or prompts with gold.

## Operational evidence

Preparation launched with:

~~~text
wsl --cd /mnt/c/Users/patri/OneDrive/Dokumenty/GitHub/llm-ontology-experiment -e .venv_wsl/bin/python -u -m llm_ontology.benchmarks.methods2test_selection --run-id methods2test-eval-hundred-v1-20261112
~~~

Progress: artifacts/evaluation/runs/methods2test-eval-hundred-v1-20261112/preparation_progress.json.
This artifact distinguishes candidate preparation from actual inference; launch
is not completion. Outcomes will be recorded only from the actual ledger/results.

### Model-free implementation checks

Initial targeted verification: 44 selection/pilot/report/real-JaCoCo tests passed
(including actual pinned Java instrumentation controls), plus three immutable
source-review tests. No full regression suite or old benchmark generation rerun.
Broader streaming static census inspected all 78,534 EVAL records / 953 projects
(1,159,852,026 payload bytes); 6,696 meet initial static/annotation/reference-call
criteria, BEFORE dependency compilation/exposure filtering. This is not a claim
that 6,696 are executable. Durable preparation continues with explicit counters.

### Prefreeze independent QA corrections (zero generations)

Read-only review checked 19 ready controls (verbatim focal/reference/fields,
source hashes, positive launcher counts, focal invocation/descriptors/counters)
and ran 66 scoped nonbuild tests. It identified four issues BEFORE any dispatch:
obvious URL/PrintWriter effectful APIs missing from lexical review; gold-only
imports leaking into visible production/scaffold; resume excluding its own IDs;
and unresolved potentially ambiguous JDK names. These were fixed before freeze.

Production imports now derive ONLY from focal method and original required fields;
reference-only imports are evaluator private. Date/Optional and ambiguous functional
interfaces are conservatively excluded without original-import evidence. Original
self-constructor calls are excluded rather than assuming fabricated constructor
semantics. Effectful network/filesystem/process/reflection APIs are rejected by
both preparation and generated-source review. This remains local reviewed execution,
NOT an OS security boundary. Resume excludes other historical cohorts, not itself.

Pre-QA candidate/control bytes remain in ignored candidates-pre-qa-v1 and
cases-pre-qa-v1; changed wrappers are compiled and reference-instrumented afresh,
never silently reused. No generated output existed and no outcome-driven model
reselection occurred. Reference coverage evidence is now frozen with source/class
hash consistency checks. Safety/import policy is rechecked against all selected
raw records immediately before publication/freezing. Twenty focused new/revised
selection/source-review tests passed after these changes.
