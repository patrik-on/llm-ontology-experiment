# Qwen shared-body one-shot v2 diagnostic

Opt-in profile `testing-bodies-one-shot-v2`; config
`configs/benchmarks/defects4j_qwen_bodies_one_shot_v2.json`.
Run: `qwen-bodies-one-shot-v2-20261112`.

## Frozen change and limits

Same prepared real Lang-26 fixed production source/public API, immutable two-slot
Jupiter scaffold, strict JSON body schema, unchanged assembly/evaluator and local
backends as `qwen-shared-bodies-v1-20261112`. The ONLY substantive prompt addition
is one synthetic unrelated solved Labels.bracket example: production method,
empty two-slot scaffold, and exact JSON with testCase1/testCase2 body strings.
The first body checks ordinary/empty bracketing; the second checks null rejection.
It contains no date/Lang benchmark subject, patch, trigger, gold test or oracle.
Models still choose every actual target input and assertion. The example is never
indexed or trained. Historical v1/full-class prompts/configs/defaults are unchanged.

Exactly three authorized cells: pure Qwen, existing ft_testing adapter, and
Single-RAG; one generation each, maximum 3 including dispatch failures, no retries
or repairs. MultiRAG/GPT-OSS cannot dispatch under the new plan. Direct-first
positive compile/execution gate remains unchanged; wrong assertions are results,
not a reason to regenerate. Decoding remains 4096 output tokens, seed 42,
temperature 0/FT greedy, top_p .9, 32768 context. Ollama generate schema decoding
and HF PEFT raw instruction JSON request remain different backend contracts.
GPU cells run sequentially, with Ollama keep_alive=0; FT loads once.

Before any generation, the demo is assembled with the existing body assembler,
compiled on the pinned Java 11/Jupiter toolchain and executed by the existing
Jupiter evaluator, requiring both tests to start and pass. Two existing-style
scaffold controls check pass/assertion failure; prepared subject/launcher health
and revision/toolchain hashes are reused read-only, with no subject rebuild or
full control matrix. Exact prompts are reconstructed/frozen before outputs.
Stripping ONLY the exact demo block must reproduce the old per-arm prompt bytes.
Single-RAG query is rebuilt using unchanged source/requirements only, compared to
its old query hash, and old selected evidence IDs/content/rendering are frozen.
The actual dispatch guard rejects any rendered prompt/evidence difference before
charging/calling generation. Actual trace IDs/query are compared after generation.
Retrieval defects, index identity, filters and selection logic are not fixed.

Exclusive per-arm dispatch files persist the spent budget, including failures;
resumption never redispatches an existing cell. Exact raw/server responses,
parsed bodies, verbatim assembled source/hashes, prompt hashes/templates,
model/adapter/index identities, tokens/stop metadata and fresh evaluation reports
are retained locally under the run directory, not committed. Each candidate is
reviewed before passing its exact SHA-256 to the existing execution guard, then
compiled/run unchanged against fixed/buggy twice. No imports, assertions, test
logic or expected values are inserted or repaired after generation.

This is reviewed local diagnostic execution, not a security sandbox. Coverage is
not measured. No training, weights, index rebuild, overlap investigation, full
suite, paid API, additional model generation or push is authorized. A one-case
observation cannot establish general improvement, isolated FT causality or a
scientific benchmark score. Source identity changes from the historical run are
reported explicitly; operational input/prompt/evidence equality is distinct from
identical complete pipeline-source identity.

## Entry point

Reuse `python -m llm_ontology.benchmarks.defects4j_bodies_pilot` with
`--config configs/benchmarks/defects4j_qwen_bodies_one_shot_v2.json`,
`--run-id qwen-bodies-one-shot-v2-20261112` and the existing explicit
freeze/generate --diagnostic --arm/evaluate --reviewed-source-sha256/report actions.
A fresh namespace is not authorization for extra calls.

## Completed results (2026-11-12)

Budget exhausted: **3/3 actual generations**, one each pure Qwen / existing FT /
Single-RAG. Zero MultiRAG/GPT calls, retries, repairs, training or extra FT loads.
All three responses parsed as strict two-body JSON, assembled verbatim, compiled
and started two tests per revision in each of two independent repeats. There were
no format rejects, output truncations, prompt-budget overruns or suspected runtime
prompt truncation, infrastructure/container failures, skipped or aborted tests.

| Arm | Fixed pass/fail per repeat | Buggy pass/fail per repeat | Input/output tokens; finish | Fixed pass | Genuine detection |
|---|---|---|---|---|---|
| Pure Qwen | 1/1, twice | 1/1, twice | 2193/70; stop | No | No |
| Existing FT adapter | 0/2, twice | 0/2, twice | 1910/93; eos | No | No |
| Single-RAG | 0/2, twice | 0/2, twice | 4442/105; stop | No | No |

Counts are per repeat, not distinct additional tests. Ollama counts are
server-reported; HF counts are observed input/continuation lengths. Greedy FT
retains the existing top_p setting even though sampling flags do not affect
unsampled decoding. The direct execution gate passed despite its wrong assertion.
No failures were repaired or excluded from the three-call denominator.

**The solved example did not yield a fixed-passing test class on this case.** Genuine detection
is **0/3**, and all three candidates fail fixed code. Compared with the same
three historical v1 arms: compilation/positive execution remain 3/3; fixed-pass
candidates change from 2/3 to 0/3; genuine detection remains 0/3. The old FT green
result was assertion-free/nonfocal and must not be described as semantic success.

Separate manual source observations, not a semantic gate or full semantic proof:

- Pure Qwen has assertions in both bodies, but only directly calls two-argument
  getDateTimeInstance overloads, not the four-argument focal signature. Its
  hard-coded date-pattern equality fails on fixed code; invalid-style exception
  test passes. Historical pure Qwen had non-null/invalid-style checks and passed
  both revisions without detecting the bug.
- FT now has assertEquals/assertThrows, instead of the historical two bare
  getInstance calls. It **still never calls focal getDateTimeInstance**. Its
  expected output includes literal square brackets mirroring the unrelated demo,
  assumes a different timezone, and expects a null-timezone/locale exception that
  is not thrown. Both assertions fail on fixed code: assertion presence increased,
  but this is not a semantic improvement.
- Single-RAG has assertions in both bodies and directly invokes the four-argument
  focal method in its second body. Its hard-coded formatted output and invalid
  locale exception expectation are both wrong on fixed code. Historical Single
  also had assertions/a four-argument focal invocation and failed both revisions.

### Preflight and comparability evidence

The assembled synthetic Labels demo compiled and passed **2/2** started tests with
Java **11.0.33+10**, Jupiter **5.11.4** / Platform **1.11.4**, via the existing
body assembler and evaluator. Demo source SHA-256:
`3fbb81d74e3ef40ce5ea2483ca577bf897e4edbce7ca0e1edeeec169c13f57f7`.
The pass/assertion scaffold controls both started two tests with expected outcomes.
No prepared subject was rebuilt and no full launcher-control matrix was rerun.

All actual prompts match their pre-output frozen prompts, and removing ONLY the
exact demo block reproduces each historical per-arm prompt byte-for-byte. The
model/adapter identities, target production/context, scaffold, body contract,
schema, toolchain, index identities and generation requests excluding prompt are
equal. Actual Single-RAG query and selected evidence IDs equal the historical
trace; its query SHA-256 is
`f83d706201472f16db36f559ef0d2e8f92ba9b8cabb204f11aa1de181ad0e3ab`.
The demonstration never enters the retrieval query. No retrieval re-tuning/fix.

Complete Python source identity is necessarily not byte-identical: only the four
owned support/profile files differ (shared body pilot, runner's optional body
profile selection, new preflight helper and new one-shot profile). Exact hashes
and changed-file list are retained. No legacy code was reset. This is an
operational prompt-only comparison, not a strict whole-pipeline byte-identical
ablation; backend/quantization/envelope differences still preclude isolated FT
causal claims. One previously explored case establishes no general improvement.

Validation: **74 affected tests passed**, scoped Ruff and git diff checks passed;
no full suite. The pre-existing TestingAnswer collection warning in the historical
full-class test remains non-failing. Historical defaults/configs/results and five
pre-existing user-dirty files are preserved. Only owned code/config/tests/docs and
this [compact comparison JSON](defects4j_qwen_bodies_one_shot_v2_results.json) are
committed; exact prompts/raw runtime artifacts remain local under the run ID.
No additional generation is authorized by this completed run.
