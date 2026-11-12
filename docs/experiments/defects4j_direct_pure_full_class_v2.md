# Pure-model three-case control (2026-11-12)

## Frozen scope

Run: `artifacts/evaluation/runs/direct-pure-fullclass-v2-20261112/`.
Exactly **six actual local generation requests**: Lang-24, Lang-26, Lang-27 x
Qwen base / GPT-OSS-20B, one attempt each, failures retained, zero retries/repairs.
No adapter, retrieval, embeddings, index client/factory, training, provisioning,
subject rebuild, download, paid API, full benchmark, overlap investigation or push.

Installed WSL Ollama 0.15.2 identities, checked with /api/tags and /api/show:

- qwen2.5-coder:7b, 7.6B, Q4_K_M,
  dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364.
  This is the exact same Ollama base/instruct model digest as the preceding RAG pilot.
- gpt-oss:20b, 20.9B, MXFP4,
  17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7.
  This is local, NOT gpt-oss:120b-cloud or a substituted model.

The opt-in defects4j_direct_pilot module composes existing OllamaProvider,
RagExperimentRunner / no_rag, canonical TestingAnswer JSON extraction and unchanged
Defects4J Jupiter evaluate_pair. Existing VectorRetriever's no_rag branch returns
no documents; its store is a fail-closed object, never a Chroma/index client.
No evidence is supplied. Canonical Direct wording differs only as designed for
no evidence. Task, focal context, public APIs, requirements, full-class-v2 Labels
few-shot, output schema and example order are unchanged. Existing prepared.json,
nonindexable manifests, all six fixed/buggy binary trees, dependencies, Java/Javac
and pinned Jupiter hashes were verified read-only against the original freeze.
Original source/protocol/output files remain untouched. New freeze pins current
code/config bytes and stores source snapshots; it does not falsely reuse the old
source identity after the provider's optional think control was added.

All requests: /api/generate, temperature=0, top_p=.9, seed=42, num_ctx=32768,
num_predict=4096, stream=false, canonical JSON schema. GPT-OSS uses explicit
think=low, supported by installed metadata/template; Qwen leaves think unset.
4096 is the total generated-token budget, not an extra allowance for reasoning.
Ollama reports total eval_count only: final/reasoning token counts are unavailable,
not assumed zero. Each request uses keep_alive=0 for sequential GPU ownership;
no concurrent FT/RAG load was started. Actual request bodies and raw server
responses are retained privately. Server model templates/system/options were
inspected: Qwen's normal instruct template/system; GPT-OSS Harmony template with
low reasoning; explicit temperature=0 overrides its stored temperature=1.

## Six-cell outcomes

| Model | Case | JSON / complete class | Compile | Fixed / buggy (twice each) | Input / total output tokens | Finish |
|---|---|---|---|---|---:|---|
| Qwen base | Lang-24 | valid / yes | yes | assertion failure / assertion failure | 2646 / 321 | stop |
| Qwen base | Lang-26 | valid / yes | no | compile failure / compile failure | 1871 / 325 | stop |
| Qwen base | Lang-27 | invalid truncated JSON / no extracted class | not reached | not run / not run | 3139 / 4096 | length |
| GPT-OSS | Lang-24 | empty server response / no | not reached | not run / not run | 2689 / 495 | stop |
| GPT-OSS | Lang-26 | empty server response / no | not reached | not run / not run | 2028 / 427 | stop |
| GPT-OSS | Lang-27 | empty server response / no | not reached | not run / not run | 3220 / 468 | stop |

Qwen Lang-24 runs two genuine Jupiter tests per revision/repeat: started=2,
succeeded=1, failed=1, aborted=0, skipped=0, containers_failed=0, JVM exit=1.
Its invalid-number test wrongly rejects a trailing-decimal input (123.), which
fixed production accepts. It therefore fails fixed code and is **not** a genuine
bug detection, despite also failing buggy code. Four fresh XML reports agree.

Qwen Lang-26 has four annotated methods but omits java.util.TimeZone/Locale
imports; javac fails on all four revision/repeat evaluations. No test starts.
The unchanged source also makes questionable pattern/exception expectations;
these are not executed or counted as observed behavioral failures.
Qwen Lang-27 exhausts 4096 tokens inside a JSON string; invalid raw output is
retained, never manually extracted/repaired or compiled. Requested 2-4 test
methods is adherence only: annotation proxies are 2 / 4 / unavailable.

Qwen: schema-valid complete classes 2/3, compiled 1/3, fixed class passes 0/3,
genuine bug detections 0/3, truncations 1/3, schema failures 1/3.
GPT-OSS: usable outputs 0/3, fixed passes/detections 0/3 in the all-attempt
pipeline denominator, **capability unresolved due to API/parser confound**.
No HTTP/transport errors or evaluator infrastructure failures occurred. GPT-OSS's
three response-contract/API-pipeline anomalies are reported separately, not
mislabelled Java failures. Overall: four schema failures, one truncation,
eight evaluator attempts (two candidates x two revisions x two repeats), four
generated Jupiter launches, zero fixed class passes and zero genuine detections.
No execution counts are invented for candidates that never reached evaluation.
Coverage was not measured. Local source was reviewed before execution; no OS
sandbox or whole-tree containment claim is made.

## Critical GPT-OSS pipeline limitation

All three HTTP responses already contain response="" and omit thinking, despite
nonzero eval_count and normal stop, well below 4096. Thus this is **not output
budget exhaustion**, and the client/extractor did not discard a returned Java
class. Metadata alone did not establish end-to-end schema/parser compatibility;
these three cells do not establish that GPT-OSS cannot generate tests.

Read-only post-run inspection of upstream Ollama v0.15.2 source identified a
plausible specific incompatibility: GenerateHandler passes req.Format directly
into completion, while ChatHandler explicitly defers schema constraints until
a thinking/content transition for built-in parsers, then forces a final header.
The Harmony parser waits for a completed message header before emitting content.
A schema-constrained completion before a Harmony header can therefore yield no
parsed response. This is consistent with the artifacts, not a proven diagnosis
of the installed binary's internals. No seventh request, alternate-endpoint
retry, parser fix, template override or extra generation was made. A clean
GPT-OSS capability comparison remains blocked on separately authorized
model-free compatibility work plus a new explicitly budgeted pilot.

Source references (public, read-only inspection):
- https://github.com/ollama/ollama/blob/v0.15.2/server/routes.go
  GenerateHandler vs ChatHandler structuredOutputsState / currentFormat handling.
- https://github.com/ollama/ollama/blob/v0.15.2/harmony/harmonyparser.go
  ParsingHeader / HeaderEndTag handling.

## What this does and does not show

Pure Qwen can produce a complete compiling executable class for this real task:
blanket "the model cannot output a full class" is false for this sample. The
remaining wrong oracle, missing imports and truncation show concrete failures
under this unchanged contract. Compared per case with the earlier same-digest
RAG arms (all three classes failed javac per arm), Direct reaches compilation on
Lang-24 but still yields no fixed pass. That is a bounded observation, not a
causal estimate that RAG harms performance. Exact normalized prompt hashes match
the earlier RAG task per case; full prompts differ by evidence/Direct wording.

The HF FT arm previously used NF4/raw instruction rendering and a local adapter;
Ollama base uses Q4/instruct rendering and JSON. This is not an isolated adapter
ablation. Six small same-project cells cannot absolutely separate inherent
capability from prompting/runtime effects; GPT-OSS in particular remains
API-confounded. Overlap/provenance audit remains deferred, not declared clean.

## Artifacts and reproduction

[Small aggregate](defects4j_direct_pure_full_class_v2_results.json) contains all six
cells, exact model digests, prompt/request/raw/source hashes, token/finish fields,
separate failure categories and per-repeat execution counts. Private ignored run
artifacts retain freeze.json, job_plan.json, source_snapshot/, models/,
cases/*/case.json, predictions/*/{attempt,dispatch,server_response,schema}.json,
all invalid raw/structured attempts, unchanged generated.java, review hashes,
metrics/*/evaluation.json, launcher/compiler logs and XML, artifact_inventory.json
and analysis/finalize.py. No runtime archives or model weights are committed.
Exclusive cell directories and exclusive dispatch files prevent same-run retries;
failed dispatches consume budget. Verification checks exactly six dispatches,
actual options/schema/prompt hashes, source immutability and zero retrieved docs.

WSL .venv_wsl entrypoint:

~~~bash
python -m llm_ontology.benchmarks.defects4j_direct_pilot freeze --run-id NEW_ID
python -m llm_ontology.benchmarks.defects4j_direct_pilot generate --run-id NEW_ID --arm qwen_base --diagnostic
# Review generated sources, then evaluate with --reviewed-local-execution.
# Repeat generation/review/evaluation for gptoss20b only with explicit new budget.
~~~

These are documentation, not authorization to repeat this exhausted six-call run.

Verification: **40 affected tests passed** (one existing harmless Pydantic
collection warning); scoped Ruff clean; changed modules py_compile clean;
git diff --check clean. No full regression suite was run. Actual six-call ledger,
all-case normalized-prompt equality, original prepared/toolchain/binary hashes,
all request options/schema/prompt hashes and generated-source immutability passed
the independent artifact cross-check. Protected pre-existing user changes were
left unstaged and untouched.
