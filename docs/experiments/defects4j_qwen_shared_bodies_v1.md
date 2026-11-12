# Qwen shared Jupiter test-body pilot v1

Opt-in profile: testing-bodies-v1. Protocol/config:
configs/benchmarks/defects4j_qwen_shared_bodies_v1.json.
This does not change historical full-class-v2 prompts, results or FT defaults.

## Frozen design

One real prepared case, chosen before generation: Lang-26,
org.apache.commons.lang3.time.FastDateFormat.getDateTimeInstance(int, int, TimeZone, Locale).
Original fixed production context, public API signatures and fixed/buggy production
binaries are reused from real-d4j-fullclass-v2-20261112, verified read-only with
verify_prepared and original prepared SHA-256. No subject rebuild is needed.
No gold tests, patches, control assertions, expected bug outcomes or preselected
production test values enter the model case. The earlier explored case is not
an independent holdout or a same-condition performance baseline.

The program supplies package, deterministic explicit imports and this class:

~~~java
public class GeneratedBodyTests {
    @Test void testCase1() throws Exception {

    }
    @Test void testCase2() throws Exception {

    }
}
~~~

The package is the focal production package. Explicit JDK imports are sorted
from fixed-production metadata; the focal FQN and Jupiter Test are explicit.
A fixed list of explicit static Jupiter assertion imports is added. No wildcard
imports or gold-derived imports; conflicting simple names are rejected. The
complete actual scaffold, including imports, is stored in the run artifacts.
All arms receive the same scaffold, focal context, available API and substantive
body contract. No slot name hints at a normal/edge case or an expected value.
Models choose every input, setup, API invocation, assertion and expected exception.

ONE request returns exactly this JSON shape (placeholder strings describe syntax,
not a semantic example):

~~~json
{"testCase1":"<Java statements, without outer braces>","testCase2":"<Java statements, without outer braces>"}
~~~

Both keys are required nonempty strings; extra/duplicate keys, markdown, prose,
whole classes and wrong envelopes are rejected. The existing structured generation
boundary is extended opt-in; historical task models remain the default. The
existing JavaParser validates balanced method interiors and exact enclosing AST
boundaries. Type/field/method/constructor/package/import/annotation declarations,
anonymous/local classes and Unicode escapes are rejected. Statement blocks,
local variables, lambdas and try/catch are allowed. Each interior is inserted
verbatim between fixed delimiters at the generation boundary, before evaluation.
No semantic rewriting, new imports, inferred values, missing logic or regeneration.

Direct/Single/Multi use the existing OllamaProvider generate transport, canonical
prompt-rendering machinery with the opt-in body template and schema constraint.
FT uses the existing local HF PEFT generator and historical raw instruction
wrapper, with the same body task/scaffold/API and JSON contract requested as text;
it does not acquire server-side constrained decoding. No training/template migration.
This is an exploratory systems comparison, NOT an isolated causal FT ablation:
HF local base + b2_testing_v2 adapter/NF4 differs from Ollama Qwen Q4 backend.

4096 generated tokens, seed 42, temperature 0 (FT greedy), top_p .9,
32768 context, no input truncation, retries 0, repairs 0. Exactly one generation
per arm, both bodies in that request, at most four actual calls total. Exclusive
per-arm dispatch files charge HTTP/HF dispatch failures as spent calls. Arm
reservation and evaluation directories reject overwrite/stale results.

Direct Qwen runs first. If its unchanged assembled source cannot compile and
start tests, STOP without the other three calls. Wrong assertions are informative
and do not prevent continuation when actual test execution is positive. Only if
usable, run one FT, one Single-RAG and one MultiRAG request on the identical case.
The existing retrieval/index pipeline is reused without modification: diagnosed
lost-method/query/regex/newLong/lowercase/reranking defects remain UNFIXED, and
retrieval evidence may therefore be poor. Overlap investigation remains deferred.

## Model-free and execution safeguards

Existing prepared revision/launcher health evidence is reused. Two small fresh
scaffold controls compile and execute two nonvacuous tests: passing arithmetic
plus expected exception, then an intentional assertion failure. These controls
are evaluator-only and never supplied to generation. No full controls/suite or
subject rebuild is repeated.

For every successfully assembled candidate, read the exact source locally before
passing its matching SHA-256 to the review guard. The unchanged shared Jupiter
evaluator uses fresh compilation/report directories, -proc:none, production-only
classpath, scrubbed environment and two fixed plus two buggy executions. Positive
started tests, assertion failures, runtime/infrastructure failures and compilation
failures are reported separately. Detection requires fixed passes and genuine
buggy assertion failures in both repeats. This is reviewed local execution,
NOT a security sandbox. Coverage is not measured.

Raw response/server payload, parsed bodies, assembled source, exact prompt,
scaffold/policy/schema/source hashes, frozen source snapshot, prepared identities,
model/adapter/index metadata, reported tokens/finish reasons and failures are
retained under artifacts/evaluation/runs/qwen-shared-bodies-v1-20261112.
Heavy runtime assets are not committed.

## Results

Completed in WSL/Ubuntu on 2026-11-12. Budget **4/4 actual generation calls**:
one per arm, no retries, repairs or extra calls. The direct gate passed before
FT/Single/Multi were dispatched. All four strict body responses parsed, assembled,
compiled and started both tests on both revisions, twice, unchanged.

| Arm | Fixed per repeat (pass/fail) | Buggy per repeat (pass/fail) | Output tokens / finish | Genuine detection |
|---|---|---|---|---|
| Pure Qwen | 2/0 | 2/0 | 62 / stop | No |
| Existing FT adapter | 2/0 | 2/0 | 33 / eos | No |
| Single-RAG | 0/2 | 0/2 | 151 / stop | No |
| MultiRAG | 0/2 | 0/2 | 156 / stop | No |

Counts are per independent repeat, not added as distinct tests. Zero format
rejects, truncations, infrastructure/container failures, skipped or aborted tests.
Ollama tokens are server-reported; HF tokens are observed continuation lengths.
Both model-free scaffold controls behaved as expected, with two started tests.

**Syntax/compilation success is not semantic success.** Pure Qwen only checked
nonnull construction and an invalid-style exception via two-argument overloads;
it missed the locale/cache regression. FT returned the same getInstance() call
in both slots, with **no assertion and no focal getDateTimeInstance invocation**.
Its green execution is vacuous for this testing task, not a capability win.
Single/Multi authored incorrect hard-coded date/time expectations; both assertions
failed on fixed code too, so buggy assertion failures are NOT bug detections.
The scaffold boundary worked on this one case, but **genuine detection is 0/4**.
No claim of improvement over the old full-class runs or isolated FT superiority.

Roles: pure/Single/Multi use the same unadapted instruction-tuned Qwen2.5-Coder
7B Ollama Q4_K_M (digest dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364).
The FT role uses the existing local HF base plus b2_testing_v2 PEFT adapter,
NF4; adapter SHA-256 is 82259c6862f1fd3b042fd9ca9459abe03f202227317e0e075f8b860e60000c2f.
Exact envelopes, reported tokens, chosen bodies, prompt/source hashes, model/index
identities and per-repeat outcomes are in
[compact results](defects4j_qwen_shared_bodies_v1_results.json).
The [exact empty scaffold](defects4j_qwen_shared_bodies_v1_scaffold.java) is included.
Its SHA-256 is 7620b00da89833e2299cd5167849f2c181903e554a48aa265970eca9919d931b;
the original prepared SHA-256 is acd7adde46224befc5612218362631c917ba97b2ed528926d45d75d1f510030a.

Validation: **92 affected tests passed**, including 26 body-specific cases;
scoped Ruff and git diff --check passed. Tests cover declaration/brace escapes,
strict schema and duplicate keys, failed raw retention, atomic one-call-per-arm
budget, direct gate behavior even with wrong assertions, deterministic assembly,
stale assembly rejection, identical evidence-normalized prompts/scaffolds and
no gold-derived scaffold logic. No full suite, new weights/training, pulls,
index rebuild, retrieval fixes, overlap investigation, push or paid service.

### Entry point

Use python -m llm_ontology.benchmarks.defects4j_bodies_pilot with explicit actions
freeze, generate --diagnostic --arm ..., evaluate --arm ...
--reviewed-source-sha256 ..., and report, always with --run-id. The completed
run's exclusive reservations reject redispatch. A new namespace is not permission
for more generation: the approved four-call budget is exhausted.
