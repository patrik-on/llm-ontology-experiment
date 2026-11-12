# Methods2Test unused-EVAL executable validation pilot v1

## Scope and decision

Run ID: `methods2test-eval-five-v1-20261112` (local ignored artifacts under
`artifacts/evaluation/runs/`). This is an **extracted-method validation pilot**,
not a final scientific held-out benchmark. The user explicitly requested the
existing EVAL folder: official `dataset/eval.tar.bz2` and matching
`corpus/json/eval` were used. Official TEST remains reserved. The earlier
three webauthn4j TEST candidates were not relabeled or substituted.

The repository already has 78,534 official EVAL records, of which 500 are selected
validation/checkpoint-selection examples and 78,034 are unmaterialized. This
pilot does not claim all unmaterialized examples are unseen, unique, or buildable.

## Selection, preparation, and absence checks

Frozen IDs, before any new model output:

| ID | Project | Focal extracted API |
|---|---|---|
| 79160472_49 | episode6/mockspresso | Preconditions.assertNotNull(T,String) |
| 52804523_92 | codice/alliance | Utilities.isNotStringNone(Serializable) |
| 56354946_19 | simonnorberg/klingar | Strings.isBlank(CharSequence) |
| 206427_319 | apache/tika | RegexUtils.extractLinks(String) |
| 206427_280 | apache/tika | EndianUtils.readUE7(InputStream) |

Five distinct focal methods from **four projects**, not five independent projects.
Selection is convenience/dependency filtered, not representative random sampling.
The bounded streaming screen parsed 8,227 JSON records across 73 projects before
the next member exceeded the 150 MiB payload cap (scope counters include that
boundary member: 8,228 / 157,291,571 bytes); 652 met initial syntactic filters.
The fixed manual archive-order dependency shortlist then required JDK-only small
public static methods, qualified actual focal calls and assertions in references,
no missing helpers/fixtures, rich/corpus agreement, current exposure absence, and
positive production compilation/reference execution. No model-result selection.
The NumberHelper candidate 12650679_72 was excluded **before generation** because
its rich reference and corpus target differ; neither side was silently repaired.
Other rejected records require project dependencies, helpers, framework fixtures,
unsupported expected-exception annotations, or map to a different overload.

All five IDs are absent from the 5,000 materialized Methods2Test records; their
projects are absent from current materialized train/validation/checkpoint inputs.
Both focal/reference lexical fingerprints and normalized contained fragments were
checked against all ten current source/mixture train/validation JSONLs and both
actual code sides of all 5,739 unique stored mixed-RAG documents using read-only
SQLite. A supplementary check found no matching named repository/project metadata
in the current ML4Refactoring/MaRV train/validation or actual mixed-RAG identities;
absent metadata is still not affirmative historical lineage proof.
Mixed contains the same unique union as testing_db/refactoring_db; no
Chroma migration/index rebuild was performed. Rich/corpus code agrees. Manifest
and compact selection preserve IDs, repository/file identities, raw archive/member,
corpus, focal/reference and wrapper hashes. Reference bodies remain private and
ignored, never in model prompts or new indexes. The dataset manifest is
`pilot_validation`, `allowed_for_indexing=false`, and its indexability guard rejects it.

These are **today's verified snapshots**, not cryptographic proof of historical
training-time bytes. The active adapter's recorded train/validation paths and
counts corroborate lineage; unknown base pretraining and unrecorded old copies
remain unknown. No giant 40-GB audit or new training was done.

## Executable contract

Original focal method and reference method bodies are copied **verbatim**.
Package names are explicitly inferred from original `src/main/java` paths; only
required explicit JDK imports, deterministic public class wrappers, and original
rich-record fields needed by the focal code are supplied. RegexUtils needs its
two original regex fields. Unrelated members/logger/fixtures are omitted rather
than stubbed. Production is compiled with debug line information (`javac -g`).
Exact source and wrapping policy are retained. This is not an original-project
checkout/build or a revision-specific source claim; the raw records supply no
pinned source commit, imports, or authoritative original dependency versions.

Unchanged simple `@Test` reference methods are bound to Jupiter, with their actual
AssertJ/Hamcrest/Jupiter assertions preserved. There is no conversion of assertion
order or expected-exception/lifecycle semantics. JUnit Platform standalone 1.11.4
(Jupiter 5.11.4), AssertJ 3.27.3 and Hamcrest 2.2 are pinned by SHA-256; the latter
two are small official Maven Central artifacts, not inferred original versions.
Five positive reference tests compile and pass. Their real focal execution and
coverage are measured separately, never added to generated-suite coverage.
Reference tests are useful oracles, not the only valid test solution.

The existing shared Jupiter boundary excludes original test binaries, selects the
actual generated test class and Jupiter only, requires positive non-aborted tests,
zero failed containers and coherent fresh XML/launcher counts, and rejects compile,
no-test, setup, timeout and abnormal-exit failures. Passing/failing/no-test controls
and the unrelated two-test solved Labels body example are executed before dispatch.
Coverage canaries exercise real branch coverage, uninvoked/unloaded focal methods,
failed/no-test/compile outcomes, missing debug lines, and missing counters.

## Frozen four-system protocol

Exactly five same cases x pure Qwen, active testing FT, Single-RAG and MultiRAG;
**maximum 20 actual dispatches**, one per cell. Failed calls consume budget.
Exclusive per-cell ledger files and the finite case/arm set reject repeat dispatch.
There are no retries, source repairs, output-based reselection, training, index
rebuilds, model upgrades/downloads, GPT-OSS calls or full-dataset inference.
Direct case 1 is a transport/schema/parser/compile/positive-execution gate before
the remaining batch; ordinary incorrect assertions are retained, not retried.
An empty/transport/protocol anomaly fail-stops that arm's remaining calls.
GPU use is sequential; FT loads once for its five generations.

All arms share the actual extracted production context, immutable two neutral test
slots, substantive unrelated solved example `testing-bodies-one-shot-v2`, strict
two-field body schema, 4,096 new-token limit, seed 42 and temperature 0. The shared
provider/runner/RAG/tokenizer/body assembler are reused, not duplicated. All inputs,
scaffolds, demo, exact prompts/schema, raw invalid outputs, identities/config,
retrieval traces, generated sources and hashes are retained.

Pure/Single/Multi use the same local Ollama Qwen2.5-Coder 7B digest and quantization.
FT uses the existing local HF base + active `b2_testing_v2` PEFT adapter, NF4 and
raw instruction envelope, not Ollama's schema-constrained Q4 generate envelope.
Its recorded training completed **300 steps / 0.6 epochs**, not two epochs.
This is a **systems comparison**, not a causal isolated adapter-effect experiment.
Known retrieval query/method identity/regex/reranking limitations remain unchanged.
Single uses mixed; Multi uses testing_db + refactoring_db, the existing shared
retrieval/fusion pipeline, same global evidence budget. No retrieval bugfixes are
bundled into this experiment. Timing/token data are descriptive: backend loading,
prompt processing, generation, retrieval and hashing are distinct where measured;
no controlled throughput ranking is justified.

## Metrics and interpretation

Primary evidence: body schema and truncation; Java syntax and compilation;
positive actually executed tests; class pass and per-test successes/failures;
**instrumented** focal invocation; two fresh repeats of the identical output;
real JaCoCo 0.8.13 focal **method and class** line/branch covered/missed/total.
Generated-test classes/dependencies and gold tests are excluded from coverage.
Class counters describe the extracted wrapper (including its compiler-generated
constructor and copied static initialization), not the original full project class;
focal-method counters avoid this wrapper/class-size confound.
Only passing classes earn primary coverage credit. Failed-class instrumentation is
retained separately as diagnostic, never silently counted as quality. Missing
measurement is null plus reason, not zero; zero-branch denominator means N/A, not
100%. Macro averages are case-level, pooled metrics use summed denominators.
Conditional passing-class coverage is separate from all-attempt success credit:
a failed/unassembled class earns zero **credit** against its known reference
production denominator, not a claim of measured zero execution coverage.

Assertion-call presence is only a lexical non-vacuity diagnostic, not semantic
correctness proof. A mechanically passing class with no actual focal invocation
cannot be called useful focal testing. No CodeBLEU/string similarity is a primary
quality metric. No real fault-detection rate is claimed without buggy revisions.
Mutation/PIT was not added to this small pilot; line/branch coverage does not prove
assertion strength or bug detection. Repeat stability concerns these same outputs,
not statistical generation reproducibility across repeated model samples.

Execution is reviewed local code with an allowlisted secret-scrubbed environment,
resource limits, timeouts and original-process-group cleanup. It is **not an OS
security sandbox** or full process-tree containment. Scope is intentionally local
and diagnostic. Source history/default profiles and all protected dirty user files
remain unchanged.

## Reproduction and operational commands

From repository root, the existing WSL `.venv_wsl` and pinned local dependencies:

~~~bash
# Model-free: verifies archive/member/wrapper hashes; compiles all five originals
# and runs their five unchanged references in a NEW ignored directory.
.venv_wsl/bin/python scripts/benchmarks/prepare_methods2test_eval.py --run-id NEW_REPACK_ID

# Existing frozen run: reference baseline, reviewed identical outputs twice, report.
.venv_wsl/bin/python -m llm_ontology.benchmarks.methods2test_metrics reference --run-id RUN_ID
.venv_wsl/bin/python -m llm_ontology.benchmarks.methods2test_metrics evaluate --run-id RUN_ID --review-manifest PATH_TO_REVIEWED_HASHES_JSON
.venv_wsl/bin/python -m llm_ontology.benchmarks.methods2test_metrics report --run-id RUN_ID
~~~

A new generation run additionally requires fresh current train/validation/RAG
snapshot absence checks and a complete exclusive freeze. Preparation alone does
not authorize new inference. The original bounded selection/audit scripts, source
snapshot, tool identities and local evidence are retained in the ignored run. The
public preparation entrypoint was independently executed model-free and reproduced
all five exact production/reference hashes and five passing reference tests.
Do not reuse or overwrite this pilot run ID; its 20-cell ledger is authoritative.

## Actual results

**Completed: 20/20 actual generation calls, 5 per arm, exactly one per cell.**
All 20 responses were nonempty strict two-field JSON; none was truncated. Six had
invalid Java statements (usually missing final semicolons) and were rejected by
the unchanged body parser/assembler, not repaired. One assembled Single-RAG class
failed compilation because 0x80 was supplied as a byte literal without a cast.
There were no transport/API, timeout, aborted-test, failed-container or other
infrastructure failures. All failures remain in the 20-attempt denominator.

| System | Schema | Syntax/assembled | Compiled | Positive classes | Passing classes | Tests passed / started (one run) |
|---|---:|---:|---:|---:|---:|---:|
| Pure Qwen | 5/5 | 3/5 | 3/5 | 3/5 | **3/5** | 6/6 |
| Testing FT | 5/5 | 5/5 | 5/5 | 5/5 | **2/5** | 7/10 |
| Single-RAG | 5/5 | 3/5 | 2/5 | 2/5 | **1/5** | 3/4 |
| MultiRAG | 5/5 | 3/5 | 3/5 | 3/5 | **2/5** | 5/6 |

Positive execution is not a correctness claim: failing assertions still start
real tests. Every positively executed class started exactly two tests; no tests
were skipped or aborted. All **13/13 positively executed classes** had identical
per-test names/statuses/types and launcher counts on the second fresh run of the
same source. The 14th assembled class repeated its compile failure, not test
execution. Test counts above intentionally do not double-count repeats.

Paired matrix (P = positive class passes twice; A = assertion failure twice;
S = body syntax rejection; C = compile failure twice):

| Official EVAL ID | Pure | FT | Single | Multi |
|---|---|---|---|---|
| 79160472_49 | P | A | S | P |
| 52804523_92 | S | A | A | A |
| 56354946_19 | S | P | S | S |
| 206427_319 | P | A | P | P |
| 206427_280 | P | P | C | S |

### Real coverage, not a proxy

All eight passing model classes have valid scoped JaCoCo measurements and actual
instrumented focal invocation; both coverage repeats agree. Coverage is **null**
for the six unassembled candidates and the compile failure. Failed executable
classes retain diagnostic instrumentation but receive no success coverage credit.

Every arm faces the same focal production totals: **23 lines / 22 branches** over
five cases. The following pooled all-attempt values award coverage only to passing
classes, with zero success credit (not a measured coverage zero) for failed cells:

| System | Credited focal lines / 23 | Credited focal branches / 22 | Case-macro line / branch success credit |
|---|---:|---:|---:|
| Pure Qwen | **19/23 (82.61%)** | **13/22 (59.09%)** | 58.00% / 56.67% |
| Testing FT | 9/23 (39.13%) | 7/22 (31.82%) | 36.00% / 30.00% |
| Single-RAG | 7/23 (30.43%) | 6/22 (27.27%) | 20.00% / 20.00% |
| MultiRAG | 10/23 (43.48%) | 8/22 (36.36%) | 40.00% / 40.00% |

Conditional on passing classes, pooled focal coverage is Pure **19/20 lines,
13/14 branches**; FT **9/11, 7/10**; Single **7/7, 6/6**; Multi **10/10, 8/8**.
Their conditional case-macro line/branch ratios are respectively 96.67%/94.44%,
90%/75%, 100%/100%, and 100%/100%. The 100% conditional RAG values must not hide
four/three failed attempts. Detailed **extracted-class** as well as focal-method
covered/missed denominators are in the compact JSON; these are different scopes.

The five unchanged reference tests pass and instrumentally invoke their focal
methods, with focal line/branch baseline counts respectively:

- 79160472_49: 2/3 lines, 1/2 branches.
- 52804523_92: 2/2 lines, 3/4 branches.
- 56354946_19: 1/1 lines, 1/4 branches.
- 206427_319: 6/7 lines, 5/6 branches.
- 206427_280: 9/10 lines, 4/6 branches.

These references cover 20/23 lines and 14/22 branches pooled, separately from model
runs. They are not coverage ceilings or the only correct tests.

### What the failures mean

- FT compiled all five, but three classes had wrong assertions. For Preconditions
  it called Jupiter's assertNotNull rather than Preconditions.assertNotNull:
  instrumentation confirms the focal method was **never invoked**, even though
  lexical assertions are present. It is not useful focal testing.
- For Utilities, FT/Multi expected an exception on null although instanceof makes
  the method return false. Single asserted true on that false result.
- FT gave contradictory expected counts for the same RegexUtils input. Its
  passing Strings class repeats identical assertions; assertion quantity is not
  distinct behavioral coverage.
- Pure, Single and Multi all produced some syntactically invalid bodies. Single's
  EndianUtils candidate additionally used an out-of-range byte-array literal;
  adding a cast/semicolon or changing an expected value would be repair and was
  deliberately not performed.

**Conclusion:** the executable evaluator and actual coverage measurement now work,
and this complete bounded pilot exposes format, API/compile, focal-invocation and
assertion-quality failures separately. Pure Qwen produced the highest passing
class count and all-attempt focal coverage here. This small convenience sample and
the declared backend/quantization/envelope differences do **not** establish a
scientific ranking, isolated FT regression, or causal retrieval effect. No real
bug detection is measured. Keep official TEST untouched for a later frozen final
evaluation after validation decisions; no additional calls are authorized here.

### Verification and artifacts

- Five original production compilations and five unchanged positive reference tests;
  five separate instrumented reference controls; Labels solved demo 2/2; fresh
  passing/failing/no-tests launcher controls.
- **40 scoped tests passed** (including real JVM/JaCoCo canaries and per-test XML
  stability regression); scoped Ruff and diff checks passed. No full suite.
- The public model-free preparation CLI reproduced all five exact wrappers and
  five passing references in a separate ignored verification directory, zero calls.
- Final report-only checks verify all 20 unique charged/completed cells, original
  frozen source/config/scaffold/production identities, no evaluator-only reference
  in actual dispatch prompts, equal production coverage denominators, and complete
  two-run evaluation for every assembled source. The separate read-only report
  helper was added after dispatch; original frozen generator/evaluator source
  files and their copied snapshot remain unchanged.
- [Compact aggregate, paired matrix, exact counters, identities and ledger](methods2test_eval_five_v1_results.json).
  Private prompts/raw outputs/source, original rich bytes, XML, JaCoCo .exec/XML,
  compiler/launcher logs and full source snapshot are in the ignored run directory.
  Gold bodies/jars/weights/archives are not committed. Protected dirty user files
  and historical baselines/runs are untouched.
- FT batch model load was measured separately (179.48 seconds, one load). Actual
  prompt processing/generation/retrieval/token metadata are retained. Identity
  hashing was not separately timed and is explicitly null, not included in model
  generation timing; no cross-backend speed ranking is made.


### Independent final QA and reuse boundaries

Independent code/artifact review found no high/medium correctness issue affecting
these recorded 20 cells. It independently confirmed case/source identities,
verbatim focal/reference wrappers, the 20-cell ledger, XML/launcher counts and
all published focal coverage counters. A further 25 non-build fixture tests
passed in that review; 11 JVM-related tests were explicitly deselected. Parent
verification additionally recalculated the complete JSON totals and ran seven
scoped pilot/report tests successfully. No extra model calls were made.

For the complete delivered report (ledger, per-test repeat proof and identity
checks), use the finalizer rather than only the basic metrics aggregate:

~~~bash
.venv_wsl/bin/python -m llm_ontology.benchmarks.methods2test_report --run-id methods2test-eval-five-v1-20261112
~~~

This is a report-only verification/write operation, not generation authorization.
It requires the recorded frozen dependencies to remain unchanged.

Reuse caution: the current five-case aggregate divides branch case-macro success
credit by five. All five selected focal methods have positive branch denominators,
so every published number is unaffected. Before reusing that macro metric with
branchless methods, exclude N/A cases from the applicable-case denominator; do
not convert undefined branch coverage to zero or 100 percent. The present pilot
results and frozen inference/evaluation source bytes were not rewritten for this
future extension.
