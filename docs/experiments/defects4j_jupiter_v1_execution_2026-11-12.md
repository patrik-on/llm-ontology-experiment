# Defects4J integration: actual execution evidence, 2026-11-12

**Integration exercised; scientific evaluation NOT ready.** This report distinguishes
real model-free evaluator controls from the three real local model attempts. No
training/retraining, index rebuild, full benchmark or paid inference was performed.
See [protocol/runbook](defects4j_jupiter_v1_runbook.md) for commands and contracts.

## Authoritative run

artifacts/evaluation/runs/d4j-20261112-pilot-v3/

The run-ID suffix v3 is a preparation iteration, **not baseline_v3**. Protocol is
new defects4j_jupiter_v1; historical baseline_v1/v2 and both historical prompt
families were preserved. Earlier local v1 terminated during native parser use;
v2 validated controls before the configuration/source freeze was finalized. They
are retained, not overwritten, and are not mixed into this pilot's model results.

- Defects4J v3.0.1, commit 6d54320e0db5a357f9ab38a8e4d2e5aead7e1c09.
- Reviewed official/user-local Java11, SVN/Perl and bounded Lang-24 initialization
  under /home/patrik/benchmark-work; full provenance is PROVISIONING.md and provenance/.
- Both **fresh** fixed/buggy checkouts built successfully through the implemented
  prepare path, including upstream production/developer-test compilation. Each
  has 143 production classes; the independent provisioning canary counted 256
  developer-test classes per revision. Generated-suite evaluation excludes those
  developer-test binaries and uses exported production classpaths.
- Temurin 11.0.33+10; pinned Console 1.11.4/Jupiter 5.11.4; WSL Python 3.13.11.
  Existing Java17/default Maven were not substituted for this benchmark toolchain.
- Existing JavaParser terminated natively with installed tree-sitter 0.26.0.
  Installing only the official binary tree-sitter==0.25.2 wheel into .venv_wsl
  resolved extraction (47 NumberUtils methods, one isNumber). No parser rewrite,
  global package installation or historical dependency-range change.
- Local Ollama 0.15.2, Qwen 7.6B Q4_K_M; its full model template/details are
  predictions/rag_single/ollama_model.json and rag_multi/ollama_model.json.
  HF uses the existing local base + b2_testing_v2 adapter, NF4, raw instruction
  format. Therefore these are **not identical backend/prompt treatments**.

The case hash is a9d5b44eddb1f16e77ba1cdab5f9444567ad073145ada10557e362857b4c1411.
Shared fixed focal-context SHA-256 is
5870c5b169fa545dc7a35f6eb8b08b1d6e0e01b623a546a468d29033ba8cba61.
The complete fixed NumberUtils source SHA-256 is
a3cd8c25a53a655a644c11accf68724e583d5e1388c1f0be40e67e5e130bca6e.

Prepared revision/source/binary/dependency/toolchain identities, all recorded
integration-source hashes, unmodified generated-source hashes, exact FT prompt
rendering, shared RAG input hashes, and absent evaluator-only reference identifiers
were checked after evaluation. The actual retrieval metadata digest remained
unchanged. Machine-readable proof: analysis/provenance_check.json.

## Real model-free evaluator controls

canary/canary.json: **all seven controls passed**, with model_calls=0:

- Passing Jupiter test: passed with positive fresh selected-class execution.
- Deliberately failing assertion: assertion_failure.
- Empty class and disabled-only class: no_tests, not accepted.
- Invalid Java: compile_failure.
- Runtime exception: execution_error, not a detected bug.
- Infinite-loop test: timeout, process group terminated.

The separate evaluator-only Lang24Canary source was compiled/executed twice on
fixed and twice on buggy code: **fixed passed both; buggy failed an actual
assertion both times**. Fresh XML reports show **one executed test in every
execution**. Identical source and matched dependency hashes were used. This is
real fault-control evidence for the Jupiter adapter, **not an LLM-generated bug
finding**. The official existing JUnit4 trigger also passed fixed/failed buggy in
provisioning; it was not sent to the models or used as the generated-suite runner.

The regression suite additionally checks real process-tree timeout termination,
stale-directory rejection, selected-class/no-tests/report semantics, malformed
XML, environment secret stripping, non-indexability, dependency/stability gates,
local-only HF options and provider metadata transport. Provider/HF-loader fixtures
in those Python tests are mocks; the Java controls above are not mocks.

## Actual model attempts (one case per arm, no retries/repairs)

All three calls used local models, the identical prepared fixed focal context,
2048-new-token ceiling and the same Java evaluator. Outputs were inspected before
local execution was acknowledged. Benchmark/reference tests, patches and expected
outcomes were not inserted into the prompts. No model-generated Java was repaired.

| Arm | Actual outcome on fixed and buggy, each repeated twice | Accepted generated tests |
|---|---|---|
| ft_testing / b2_testing_v2 | invalid_source: raw @Test method fragment, no class, ends inside a string literal | 0 |
| rag_single / existing V3 mixed | compile_failure: stray g before void; javac reports identifier expected | 0 |
| rag_multi / existing V3 disjoint collections | compile_failure: unqualified NumberUtils without an import/package; javac cannot find symbol | 0 |

**No model-generated tests executed, no generated candidate passed fixed code,
and no model-generated real bug detection is claimed.** Shared JSON/schema success
for both RAG responses did not establish Java compilation. These ordinary negative
candidate outcomes were retained, not dropped, repaired, or counted as detected bugs.
The evaluator itself was validated separately by the real positive/negative controls.

FT used 1357 prompt tokens. Its decoded output re-tokenizes to 2048 tokens with the
local base tokenizer and ends mid-literal, consistent with the configured ceiling.
The existing HF helper does not retain raw generated token IDs: that re-tokenized
count is explicitly labeled in analysis/ft_token_audit.json, not misrepresented as
an independently retained generation-token sequence. HF seed evidence is 42 in the
frozen generation implementation. Four base shard hashes, tokenizer/config hashes,
adapter/config and saved training summary/config hashes are preserved. Actual
adapter weight SHA-256:
82259c6862f1fd3b042fd9ca9459abe03f202227317e0e075f8b860e60000c2f.

Operational wall times including identity hashing/model loading/retrieval/setup
were approximately FT 398.2 s, Single RAG 102.8 s, MultiRAG 95.1 s. They are **not
controlled latency comparisons**. RAG records preserve runtime token/duration
metadata, retrieval traces, exact prompts and structured-output attempts.

reports/summary.json includes every attempted arm in unconditional denominators;
conditional rates are null when there were no eligible executed tests. All rates
are explicitly diagnostic_only=true and scientific_scores=false. JaCoCo coverage,
mutation results, final benchmark scores and statistical comparisons are absent.

## Actual leakage audit and remaining scientific blockers

leakage_audit.json inspected the specialist's current train file (4000 rows) and
**11,478 actual collection entries**: mixed 5739 + testing_db 3978 + refactoring_db
1761, representing the same 5739-document corpus twice, not 11,478 unique samples.
It binds three collection-manifest hashes and a deterministic actual-metadata hash:
9c2d827797c96e86623719e0c8c0c308b5f100722297ff6534251c19bfc2f2f1.

Current testing/train.jsonl SHA-256:
6a2ebc5d0dbbfd2f2dbc4b653a45ec9fdc4f9ae836da3a64f1f44e8d5f09b401.
The adapter's saved summary links to that path, but has no historical dataset
checksum; current-byte auditing is not proof of training-time byte identity.

- All 4000 materialized specialist training rows lack explicit repository lineage;
  8912 collection entries also lack it. Missing identity is unknown, not clean.
- Ten conservative namespace flags correspond to five distinct MaRV documents
  repeated in mixed/refactoring_db. Inspection found no NumberUtils/isNumber/1.1L
  in those five documents. They are candidate dependency/namespace references,
  **not confirmed same-repository benchmark leakage**. No normalized-code match
  was reported by this implemented audit; this does not prove near-clone absence.
- Thus **Lang-24 is not leakage-cleared**. This bounded check does not claim that
  no clean Defects4J case exists. No corpus/index was silently rebuilt or relabeled.
- The previously verified **188 leaked train/test exact pairs** in combined/
  refactoring data remain an existing limitation, not a claim that b2_testing's
  separate train file has those same 188 pairs. No retraining was performed.
- Base-model pretraining contamination is unknown.
- Local process isolation/resource limits are not an OS sandbox. Filesystem/network
  isolation, a preregistered clean multi-project subset and approved comparable
  output/prompt contracts remain gates before scientific evaluation.

## Verification commands/results

Inside WSL, using .venv_wsl:

~~~bash
python -m llm_ontology.benchmarks.defects4j_runner dry-run --run-id <new-id>
python -m llm_ontology.benchmarks.defects4j_runner readiness --run-id <new-id>
# prepare, canary, audit, generate, review/evaluate, report commands are in the runbook.
pytest -q tests/experiments/test_defects4j.py
# 21 passed
pytest -q
# 173 passed, 3 skipped, 1 failed: unchanged legacy smoke JUnit classpath (below)
pytest -q -k "not test_all_java_inputs_and_refactoring_behavior_fixtures"
# 173 passed, 3 skipped, 1 deselected
ruff check .
python -m compileall -q src
git diff --check
# lint / compilation / diff checks passed
~~~

The full-suite failure independently reproduces when running only
 tests/datasets/test_smoke_dataset.py::test_all_java_inputs_and_refactoring_behavior_fixtures.
The unchanged smoke helper selects cached Jupiter 5.11.4 but Platform
commons/engine/launcher **1.9.3**, causing NoSuchMethodError for
ReflectionUtils.returnsPrimitiveVoid. The new Defects4J adapter does not use that
lexicographic Maven-jar discovery and passed its pinned coherent-Jupiter controls.
This unrelated historical smoke dependency-selection issue was not silently
changed as part of this benchmark protocol.

Protected existing dirty .gitignore and four dataset-document/script paths were
left untouched/uncommitted. No binary, downloaded subject/model asset or generated
runtime artifact is part of the task commit. No push was performed.
