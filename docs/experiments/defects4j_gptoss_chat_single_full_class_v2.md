# GPT-OSS chat compatibility: one real case (2026-11-12)

## Scope and implementation

Run: `artifacts/evaluation/runs/gptoss-chat-single-lang24-20261112/`.
Exactly **one actual generation HTTP request**, Lang-24 / local GPT-OSS-20B,
with zero retries, alternate endpoints, candidate repairs or extra probes.
The previous six-call run and its results/configs remain unchanged.
This separately authorized one-call budget is now exhausted.

`OllamaProvider(transport="chat")` is an opt-in on the existing provider,
not a second client. Its default remains `generate`; Qwen defaults and all
existing global configs are unchanged. Chat sends the canonical prompt as one
user message and exposes only `message.content` as the answer, never thinking.
Raw response/metadata remain available privately. The small opt-in
`defects4j_chat_pilot` module composes the existing Direct/no_rag
`RagExperimentRunner`, `TestingAnswer` extraction and unchanged
`evaluate_pair`. No adapter, retrieval, scaffold, repair, subject build,
training, index work, audit, model download, spend, full suite or push occurred.

Before generation, official API docs and pinned Ollama v0.15.2 source were
inspected. Chat supports messages, non-streaming responses, JSON schema format
and separate content/thinking; v0.15.2 ThinkValue accepts low/medium/high and
ChatHandler permits these string levels for Harmony. Installed metadata confirms
thinking capability and a Harmony template using ThinkLevel. No raw/template
request override or client-side chat templating was used.

## Frozen comparison contract

- WSL-only `http://localhost:11434/api/chat`, Ollama **0.15.2**.
- `gpt-oss:20b`, 20.9B MXFP4, digest
  `17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7`.
- Exact same Lang-24 prepared fixed/buggy binaries, dependencies, Java 11,
  Jupiter 1.11.4, fixed-code context, full-class-v2 Labels demonstration,
  visible instructions, canonical TestingAnswer schema and example order.
  Original prepared/manifests/toolchain/production-tree hashes verified read-only.
- temperature=0, top_p=.9, seed=42, num_ctx=32768, num_predict=4096,
  think=low, stream=false, keep_alive=0, unchanged from the prior GPT-OSS cell.
- An independent exact payload comparison permits only replacing the prior
  prompt field with messages=[{role:user, content:the identical prompt}].
  Full prompt SHA-256:
  `af58436856658cbb32afef6c320fc2458f176f247240aeae470fbb31b263e0d8`.
- No explicit system messages or system override. The unchanged server model
  template/system/options are stored in model.json; request messages are stored
  exactly in dispatch.json. The template supplies its own built-in system and
  date. The final server-rendered prompt bytes are not returned by this API;
  template identity is not falsely labelled a captured rendered prompt.

Only the client transport was intentionally changed. Server framing, parser and
structured-decoding behavior are necessarily endpoint-dependent.

## Actual result

**Nonempty content (2,158 characters), valid canonical JSON, complete Java class,
compilation success, three actually executed Jupiter tests, fixed pass and genuine
bug detection.** The unchanged generated class was reviewed before local execution.

| Revision | Repeats | Compile | Started / successful / failed per run | Outcome |
|---|---:|---|---|---|
| Fixed | 2 | pass | 3 / 3 / 0 | passed twice, JVM exit 0 |
| Buggy | 2 | pass | 3 / 2 / 1 | assertion failure twice, JVM exit 1 |

All four fresh XML reports agree with launcher counts: zero aborted/skipped
tests, zero failed containers and zero XML errors. The same source hash is used
in every compile. The buggy failure is a real
`org.opentest4j.AssertionFailedError` at generated line 43:
`assertFalse(NumberUtils.isNumber("123.4L"));`.
Fixed code rejects this invalid long-qualified decimal; buggy code accepts it.
Because the entire class passes fixed code twice, this is not merely a wrong
oracle that also fails fixed code, unlike the prior Direct Qwen Lang-24 output.
The requested 2–4 methods is satisfied (three), but remains adherence only.
Coverage was not measured. Execution was reviewed local execution, not a sandbox.

Server response: done=true, done_reason=stop, reported prompt_eval_count=2722,
eval_count=568. These are recorded literally, **not asserted to be the complete
reasoning-plus-answer token total**. v0.15.2 ChatHandler can internally cancel
and restart decoding to apply schema after thinking, and non-streaming metrics
come from its final response. The same num_predict=4096 is requested; an HTTP
request cap is not a claim of one internal backend completion or an independently
verified cross-stage token cap. No client retry or second HTTP generation occurred.

## Interpretation and root-cause evidence

The previous same-model/same-case generate endpoint returned response="" with
normal stop and nonzero tokens. Chat now returns a usable test class under the
same visible contract. This establishes that the opt-in chat path works for this
one real case and resolves its previously observed empty-answer pipeline blocker.
It does **not** prove general model capability, a benchmark success rate, or
causality inside the installed binary.

Pinned upstream source provides a specific plausible explanation: GenerateHandler
passes req.Format directly to completion; ChatHandler temporarily defers schema
constraints until a parsed thinking/content transition, then appends a Harmony
final header before constrained decoding. The parser requires completed headers.
The observed endpoint difference is consistent with that mechanism, not an
instrumented proof of it. Server-side framing/staged decoding and unavailable
total-token accounting limit a stricter causal inference. Lang-24 was previously
explored; overlap/provenance audit remains deferred, not declared clean.

## Evidence and verification

[Compact results](defects4j_gptoss_chat_single_full_class_v2_results.json) retain
request/schema/prompt/template/model/source/raw-response hashes, exact requested
options, reported tokens/finish, and all four independent execution counts.
Private ignored artifacts include the exact request, complete raw server response,
separate content.txt and thinking.private.txt, model metadata, code/config freeze,
unchanged generated.java, review hash, compiler/launcher logs, four XML reports,
upstream source snapshots and analysis_finalize.py. Private thinking is not quoted
or committed. One exclusive root dispatch ledger and an exclusive generation
reservation block resume/duplicate dispatch, including failed HTTP calls.

**35 affected tests passed**; scoped Ruff and py_compile passed. Independent
artifact checks verified the one-call ledger, exact prior-payload equivalence,
source immutability, positive tests, XML/launcher/JVM agreement, genuine assertion
failure, original prepared/toolchain/binaries and protected-file hashes.
No full regression suite or all-control rerun was performed. Existing user
.gitignore and four untracked docs/script remain untouched and unstaged.

Read-only official references:
- https://docs.ollama.com/api/chat
- https://docs.ollama.com/capabilities/thinking
- https://github.com/ollama/ollama/blob/v0.15.2/api/types.go
- https://github.com/ollama/ollama/blob/v0.15.2/server/routes.go
- https://github.com/ollama/ollama/blob/v0.15.2/harmony/harmonyparser.go
