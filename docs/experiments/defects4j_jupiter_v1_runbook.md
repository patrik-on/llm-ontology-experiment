# Defects4J/Jupiter FT + RAG integration (2026-11-12)

Protocol: **defects4j_jupiter_v1**. This is a bounded, diagnostic testing integration,
not a new frozen final baseline and not a complete Defects4J installation.
Historical baseline_v1/v2, TestBench and instruction/canonical prompt templates
remain unchanged. No training, index rebuild, full benchmark, paid service or push.

## Experimental contract

One candidate: **Lang-24**, active in Defects4J **v3.0.1**, framework commit
**6d54320e0db5a357f9ab38a8e4d2e5aead7e1c09**. Fixed upstream revision
8e2f4ddb9a1ecd7a1bf7d752c2c891d630287036; buggy parent
7df70a8c6b14452767ac932a14640e32a1dc16da. Defects4J creates synthetic checkout
commits; both actual checkout commit IDs and the upstream active-bug row are recorded.

All arms receive exactly the same fixed-production focal context, extracted by the
existing JavaParser: NumberUtils.isNumber, package/imports/class declaration,
fields and method documentation. Original tests, trigger names, patches, buggy
source, reference/control tests and expected outcomes are evaluator-only. No
benchmark material is inserted into retrieval or training. Preparation writes a
DatasetManifest with usage_role=benchmark and allowed_for_indexing=false.

- **ft_testing:** existing b2_testing_v2 PEFT specialist over the local HF Qwen2.5
  Coder 7B base, existing load_eval_model/generate_prediction, instruction-v1
  envelope, raw Java output. Local-only loading, no remote custom code. The new
  benchmark instruction explicitly asks for Jupiter; this does not rewrite the
  historical training instruction or convert JUnit4 outputs to JUnit5.
- **rag_single:** existing V3 mixed collection and canonical JSON/JUnit5 prompt,
  shared RagExperimentRunner, shared provider factory/OllamaProvider,
  VectorRetriever, tokenizer/budgeting and TestingAnswer extraction.
- **rag_multi:** the same shared runner and canonical prompt, V3 testing_db +
  refactoring_db, existing RRF/candidate reranking/global budgeting. No second
  retrieval or HTTP client.

**Shared cases/evaluator do not imply identical prompts or model runtimes.** HF
uses raw instruction formatting and NF4 bitsandbytes; Ollama has its own instruct
rendering and quantization (runtime /api/show is preserved). This is a descriptive
comparison of two existing systems, not a controlled causal FT-vs-RAG ablation.
Single/MultiRAG retain the same canonical contract. Both generation paths are
single-attempt, seed 42, greedy/temperature 0, at most 2048 new tokens. FT removes
only a complete surrounding Markdown fence; no package/import/JUnit repair,
semantic repair or retries. A truncated/invalid class remains a failed attempt.

## Runtime and provenance

Final runtime is **Ubuntu WSL + .venv_wsl**, not Windows Python/Ollama. The new
repository-scoped YAML points to live-verified paths; no frozen config is redirected.
Ollama is exactly http://localhost:11434; generation and embedding digests are pinned
and checked. The existing EnvironmentStatusService supplies RAG readiness.

User-local assets are under /home/patrik/benchmark-work (not OneDrive):

- defects4j: bounded sparse official checkout, only Lang-24 subject revisions.
- deps/jdk-11.0.33+10: official Temurin Java11, archive SHA-256
  c4b8eaf56c93b95b689ffc08d155df1bcdbbffb666f8f71d21d97aedaea6f0ec.
- downloads/junit-platform-console-standalone-1.11.4.jar: official Maven Central,
  independently matched publisher SHA-256
  b016ef6b1c3454d6d7c2c88ce081dabf289699686af6622d6e4e2e1b54b4a2fc.
- deps/ubuntu: checksum-verified Ubuntu Noble SVN 1.14.3 and runtime Perl packages,
  unpacked locally, not installed globally. The YAML explicitly allowlists their
  executable/library/Perl paths; credentials and inherited shell hooks are not copied.
- PROVISIONING.md, provenance/, logs/, canary-metadata.json: reviewed commands,
  download origins/sizes/checksums, init-equivalent Major wrapper diff, exported
  classpaths, original trigger installation controls. No full init.sh/get_repos.sh.

The upstream init/build/checkout scripts, subject build chain and changed subject
source were reviewed before execution. The initial official framework-archive
attempt was capped at 60 MB; its named ABORTED partial is unused. The full
all-subject repository archive/Gradle distributions were not downloaded. Empty
Constants.pm existence-guard directories are explicitly documented placeholders:
other projects, generated-suite tools, mutation and Gradle workflows are **not ready**.
Major archive has a recorded digest, not an independent publisher checksum claim.
Framework is MIT; Commons Lang is Apache-2.0. Subject LICENSE.txt/NOTICE.txt hashes
are captured per checkout; downloaded tools retain their own notices.

An actual integration attempt exposed a **native crash in existing JavaParser
with tree-sitter 0.26.0** (even a tiny class), after both subject builds succeeded.
The official binary PyPI wheel tree-sitter==0.25.2 was installed only into .venv_wsl
(no dependency/global changes); the same parser then extracted all 47 NumberUtils
methods successfully. This protocol checks that exact parser version before build.
The project's broad allowed dependency range is deliberately not rewritten.

The HF base is /mnt/c/models/huggingface/Qwen2.5-Coder-7B-Instruct. The adapter is
/home/patrik/experiments/llm-ontology-v2/b2_testing/checkpoints/final_adapter.
Complete shard/adapter/tokenizer/config presence is checked; generation stores
SHA-256 identities of every used base shard and adapter weights, plus saved training
config/summary. The summary links to data/processed/testing/train.jsonl (4000 rows),
not the combined adapter. It contains no historical dataset checksum: auditing the
current file cannot prove its bytes are identical to the original training-time file.

## Commands

From the repository inside WSL, with the reviewed assets above present:

~~~bash
source .venv_wsl/bin/activate
python -m llm_ontology.benchmarks.defects4j_runner dry-run --run-id my-d4j-run
python -m llm_ontology.benchmarks.defects4j_runner readiness --run-id my-d4j-run
python -m llm_ontology.benchmarks.defects4j_runner prepare --run-id my-d4j-run --reviewed-local-execution
python -m llm_ontology.benchmarks.defects4j_runner canary --run-id my-d4j-run --reviewed-local-execution
python -m llm_ontology.benchmarks.defects4j_runner audit --run-id my-d4j-run
# Audit exit 2 means not leakage-cleared. Scientific generation is disabled.
# Only an explicitly flagged diagnostic attempt is available:
python -m llm_ontology.benchmarks.defects4j_runner generate --run-id my-d4j-run --arm ft_testing --diagnostic
# Inspect predictions/ft_testing/generated.java before executing it.
python -m llm_ontology.benchmarks.defects4j_runner evaluate --run-id my-d4j-run --arm ft_testing --reviewed-local-execution
# Repeat generation, review, evaluation for rag_single and optionally rag_multi.
python -m llm_ontology.benchmarks.defects4j_runner report --run-id my-d4j-run
~~~

The --config option selects only this new protocol's YAML. dry-run performs no
writes/model calls. prepare builds a fresh fixed/buggy pair under Linux storage,
exports cp.compile/cp.test and output/source directories, and snapshots binaries,
source, dependency identities and toolchain. The generated-test classpath uses
production binaries plus exported production dependencies + pinned Jupiter; it
excludes existing developer-test binaries and native JUnit4 test dependencies.

Artifacts are exclusively under artifacts/evaluation/runs/<run_id>/, including
run_manifest.json, prepared.json, benchmark_manifest.json, leakage_audit.json,
prepare logs, canary controls, predictions/<arm>/ and metrics/<arm>/. Config,
referenced configs and integration-source identities are checked on resume. A
changed protocol/code requires a new run ID. Existing preparation, generation and
evaluation directories are never overwritten. Successful stages are separately
recorded; a completed stage is not a claim of completed scientific evaluation.
Failed generation attempts remain in reports rather than being silently omitted.

## Executable evaluator and safety

The native Defects4J generated-suite path is JUnit4; this adapter **does not use it**
for generated tests. javac -proc:none compiles one unmodified generated class;
pinned Platform 1.11.4 selects exactly that class and only junit-jupiter. Fresh XML
must show a positive non-skipped executed count for the selected class. Empty and
all-disabled classes fail acceptance; stale workspace/report directories are rejected.
Compilation failure, no effective tests, discovery failure, assertion failure,
execution error, timeout and infrastructure failure remain distinct.

Identical generated source runs independently at least twice against each revision,
with matched production dependency checksums. Detection requires every fixed run
to pass and every buggy run to execute and fail with an actual assertion type;
compile/discovery/timeouts are not bug detections. Reports include unconditional
rates over all attempted arms and conditional rates only over eligible outputs.
JaCoCo coverage/native mutation are **not measured**; no coverage proxy is relabeled.

Execution has a scrubbed allowlist environment, separate process groups, group
termination (including descendants), CPU/file-descriptor/file-size/core limits,
bounded Java heap and fresh work/report directories. **This is not a security
sandbox**: same-user filesystem/network access is not OS-isolated. Do not run
unreviewed/generated or service-using code merely because a timeout exists. The
review acknowledgement is mandatory; local runs remain diagnostic-only. A future
scientific protocol needs OS isolation/network restrictions and a preregistered,
leakage-cleared multi-project case set. No credentials or paid APIs are required.

## Leakage and results

The audit reads the actual specialist training JSONL and actual SQLite documents
and metadata for all three V3 collections through mode=ro, binding collection
manifest hashes and a deterministic metadata digest. It checks conservative
repository/namespace markers and normalized production-method/class containment.
Missing repository lineage is **unknown**, never treated as proof of disjointness.
Namespace occurrences can be dependency imports, so candidate marker flags are
not by themselves confirmed same-repository leakage.

Lang-24 currently is **not scientifically leakage-cleared**: all 4000 materialized
training rows lack explicit repository lineage, and the actual index has unknown
lineage plus namespace candidate flags. This is evidence about this candidate,
not proof that no clean Defects4J case exists. No dataset/index was silently changed.
The prior independently verified 188 train/test exact-pair leakages remain a known
limitation of combined/refactoring fine-tuning data, not a claim that the separate
testing specialist has those same 188 leaks. Base-model pretraining contamination
is unknown. See the [dated execution report](defects4j_jupiter_v1_execution_2026-11-12.md) for exact live attempts/results.
