# Defects4J final bounded reviewer QA (2026-11-12)

Follow-up to 69833e3. **No new inference/training, output repair, downloads or index
rebuild.** Original model-output artifacts remain unchanged. A fresh QA namespace
reuses the already reviewed, compiled Lang-24 fixed/buggy pair; it does not claim a
new subject checkout/build or another-project runtime test.

## Exact real reviewer probes

Artifacts: artifacts/evaluation/runs/d4j-20261112-reviewer-qa/.
The origin prepared file is recorded with its digest, copied into the new namespace,
then bound to a new non-indexable usage manifest and new source identities.

- Exact production assertion in BeforeAll:
  assertFalse(NumberUtils.isNumber("1.1L")), followed by an empty Test method.
  Fixed passes twice; buggy produces container_failure twice, with **tests_started
  [0, 0]**. detected_bug=false. XML's synthetic testcase is not accepted as actual
  execution. See canary/setup-fault-negative-pair/evaluation.json.
- A shutdown hook calling Runtime.getRuntime().halt(137), with assertTrue(false)
  in the test: fixed and buggy both exit **137**, final status
  **infrastructure_error**, not assertion_failure. The fixed generic control and
  an extra identical-source buggy execution were exercised. The existence of a
  failed assertion XML entry cannot override abnormal process termination.
- All **11 generic real controls pass**, and the separate ordinary Lang-24 real-fault
  reference still passes fixed twice/assertion-fails buggy twice.

Machine-readable exact evidence: analysis/exact_reviewer_probes.json. Model calls: 0.

## Prepared-data binding

verify_prepared now requires the actual prepared_path and validates its bytes against
benchmark_manifest.content_hash, benchmark usage role, non-indexability and source
path. It checks that the supplied in-memory object is that same bound file.

The CLI additionally pins both the prepared-file digest and the usage-manifest
digest in run_manifest.metadata.prepared_identity after preparation. Resume checks
these before changing run state. Recomputing an internal case hash does not bypass
the file digest; rewriting the usage manifest does not bypass its pinned digest.
Regressions include direct CLI rejection with the old run manifest unchanged.
These local consistency checks are not signatures against an attacker who rewrites
all local provenance files; OS isolation/authenticated artifacts remain future gates.

## Shared source identity

Resume fingerprints now cover all actual Python files under src/llm_ontology,
including dirty/untracked bytes, plus pyproject.toml and referenced retrieval/model
YAMLs. This includes HF inference, canonical prompting/schema, Ollama, provider,
retrieval and token-budget implementations, not just the three new benchmark
modules. Added/removed/changed shared source rejects the same run ID before writes.
Tests cover each specifically requested shared area and a direct resume rejection.

## Invalid structured responses are retained

StructuredOutputError remains a RuntimeError subclass and carries received attempts
and generation metadata. No successful-answer schema, prompt, sampling policy or
retry count was changed. RagExperimentRunner writes a separate failure JSON next
to its prompt artifact, containing raw responses, validation errors, generation
metadata, prompt/model/config identities and retrieval trace. If persistence itself
fails, the original error/attempts remain available with a persistence-error note.

The benchmark failure.json also contains those attempts/context. A sentinel invalid
JSON regression verifies exact raw retention through the shared runner and benchmark
failure payload, and verifies that the failed arm stays in the report denominator
(one attempted case, zero generated/compiled candidates). It is a mocked-provider
regression, not a new real model call. Failed schema output is never a successful
ExperimentRecord or an executable test candidate.

## Deliberately narrow execution trust

Termination signals only the **original process group**. Children that detach into
a new session/group may survive; whole-tree termination is not promised. The prior
same-group-child regression/test name and documentation are narrowed accordingly.
The historical execution report's termination wording is clarified; its negative
model outcomes and runtime artifacts are not rewritten.

Console text counters are not authenticated listener events. Missing/duplicate
counts fail closed, but hostile stdout can theoretically spoof text. A machine-readable
listener and real OS/filesystem/network isolation would be stronger. This remains
local **reviewed-code diagnostic execution**, not a sandbox or scientific-clearance
claim. No detached-child escape probe was rerun; the reviewer's already-cleaned
reproduction is not claimed as new evidence.

## Validation

WSL Ubuntu / .venv_wsl:

~~~bash
pytest -q -rs
# 225 passed, 3 skipped; no excluded failure
ruff check .
python -m compileall -q src
git diff --check
~~~

The three skips remain historical fingerprint assets, opt-in Ollama embeddings and
opt-in model-download integration. The coherent legacy Java smoke suite remains
passing. Scientific results stay blocked by historical dataset lineage, execution
isolation, clean subset registration and the original model-output failures. No push.
