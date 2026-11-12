# Defects4J post-review hardening (2026-11-12)

This supersedes the *current implementation limitations* identified after commit
43ddc40, not its historical negative model results. **No additional model calls,
training, output repair, index rebuild or downloads occurred during this phase.**
The initial run d4j-20261112-pilot-v3 and its report remain historical evidence.

## Reusable bounded configuration, not an all-project readiness claim

- project is a validated Defects4J identifier, not Literal[Lang]. bug_id is a
  strictly positive integer, not Literal[24]. Defaults remain Lang-24.
- Selection must be a unique row in active-bugs.csv inside the selected project
  under the pinned v3.0.1 installation. Unknown/deprecated bugs, absent project
  metadata, unpinned framework HEAD and path escapes fail closed. No automatic
  clone/init/download occurs.
- focal_class/focal_method are safe Java identifiers, resolved in production
  source with matching package/class. Optional focal_parameter_types disambiguates
  overloads; otherwise the method must resolve uniquely. Other projects require
  explicit project-specific focal context and repository/namespace markers.
- hf_model_name selects a configured local adapter rather than being restricted
  to b2_testing_v2. The FT arm requires a local PEFT adapter plus saved training
  summary/config; baseline/unknown/missing adapter selections fail rather than
  silently using another model. Default remains the testing specialist.
- One configured bug per run is deliberate. A batch/full-matrix runner is future
  work. Only **Lang-24** has actual subject-build/evaluator runtime proof here.
  Other-case validation/control-flow tests use fixtures, not unexecuted claims of
  successful Math/other project compilation. The current sparse installation and
  its subject repository contain Lang-24 only; other cases need separate reviewed
  assets/build-chain preparation. Multi-output/nonjar classpaths may fail closed.

The generic evaluator controls are available for any prepared case. The known
Lang24Canary reference is gated on Lang-24 + NumberUtils.isNumber; tests assert
that another selected case never invokes that reference. Other cases explicitly
report fault_validation_status=not_validated_for_case and real_fault_detected=null.
Passing generic controls does not imply a real-fault control passed for that case.

## Source roles and provenance

The audit now hashes/inspects current **training, validation, checkpoint-selection**
files and actual retrieval documents/metadata. The selected adapter's saved summary
must identify train/val paths included in the configured roles. Empty/missing role
lists/files fail closed. A validation set reused to select checkpoints is bound
under both roles, not represented as two distinct sample sets.

Actual fresh expanded audit (audit_schema_version=2):

- training: 4000 rows;
- validation: 500 rows;
- checkpoint selection: the same 500 validation rows;
- retrieval: 11,478 collection entries (5739 unique documents represented in
  mixed and the two disjoint collections).

Validation/checkpoint source SHA-256:
8e48b96d25041811cc7fb96e1f84401b816787640501840f9d1e38a8ffff7e1f.
Training and retrieval identities remain equal to the original diagnostic audit.
All 4000 training rows and 500 validation rows still lack explicit repository
lineage; the selection role has those same 500 unknown identities. Existing
conservative namespace flags are retained as candidates, not confirmed overlap.

historical_data_identity_verified=false and scientifically_clean=false remain
unconditional gates: current-file hashes cannot prove past training or checkpoint
selection bytes. current_inputs_disjoint is a separate conservative observation,
not scientific clearance. Existing 188-pair combined/refactoring train/test leakage
and unknown base pretraining contamination remain documented limitations.

Prepared-state verification now also checks case hash/focal identity, current
active metadata, checkout HEAD/.defects4j.config, javac and Jupiter identity.
Canonical output containment and configuration/source mismatch checks reject
historical-run reuse before writing. A regression verifies the old manifest bytes
stay unchanged on such rejection. java_parser_version=0.25.2 and seed 42 are explicit
in this protocol's serialized config; no global dependency range was changed.

## Real lifecycle/discovery correctness

Legacy XML synthesizes testcase entries when BeforeAll fails, although **zero tests
started**. XML counts alone therefore cannot prove executed test bodies. The pinned
Console summary is now required alongside selected-class XML; missing/duplicate
summary counts fail closed. Container failures and aborted tests cannot be accepted
or become detected bugs. Malformed XML stays infrastructure_error even when a
launcher summary says zero tests. Assertion outcomes also require Console exit 1.

Fresh final-source run: **artifacts/evaluation/runs/d4j-20261112-hardening-v2/**.
Both fresh Lang-24 revisions compiled, with 143 production class hashes each.
All **ten real model-free controls passed**:

- pass / ordinary assertion failure: positive test count, correct outcome;
- empty / disabled-only: no_tests, not accepted;
- compile failure / runtime exception / timeout: distinct negative outcomes;
- BeforeAll runtime exception and BeforeAll assertion: container_failure,
  zero actual started/non-aborted tests counted;
- aborted assumption: test_aborted, zero non-aborted tests counted.

The explicitly gated Lang-24 fault reference still passed twice on fixed and
assertion-failed twice on buggy code, one positive executed test per process.
No generated model candidate was created or rerun. Earlier hardening-v1 and small
lifecycle probes are retained separately, not substituted for the final-source run.

## Coherent legacy smoke Java dependencies

The pre-existing full-suite failure is fixed minimally in discover_junit_classpath:
Jupiter **5.11.4**, Platform **1.11.4**, opentest4j **1.3.0**, apiguardian **1.1.2**.
Discovery takes one complete installed coherent set rather than independently
choosing lexical latest versions (which incorrectly preferred Platform 1.9.3).
Explicit overrides preserve order but reject empty/partial/mixed/missing/duplicate/
extra entries without fallback. The existing complete Maven cache was used; no jars
were downloaded, removed or replaced. Historical prompts/baselines/launcher were
not changed.

Focused discovery regressions cover the lexical trap, incomplete caches and bad
overrides. The existing real Java smoke test now succeeds: 24 inputs compiled,
12 reference refactorings compiled, 24 before/after behavior executions passed.

## Validation and exact CLI

WSL Ubuntu / .venv_wsl:

~~~bash
pytest -q tests/experiments/test_defects4j*.py tests/datasets/test_junit_discovery.py
# 66 passed
pytest -q -rs
# 219 passed, 3 skipped; no excluded failing test
ruff check .
python -m compileall -q src
git diff --check
~~~

Skips: missing historical production fingerprint artifacts; opt-in Ollama embedding
integration; opt-in model-download integration. No model calls were enabled for them.
The first post-hardening full run had 218 passing tests, then one additional malformed
XML regression was added; the final 219-test pass is the authoritative result.

The [runbook](defects4j_jupiter_v1_runbook.md) contains preparation/audit steps and
precise FT + RAG commands. For future explicitly authorized diagnostic inference,
not executed during hardening:

~~~bash
CFG=configs/benchmarks/defects4j_jupiter_v1.yaml
RUN=my-new-reviewed-case-run
python -m llm_ontology.benchmarks.defects4j_runner generate --config "$CFG" --run-id "$RUN" --arm ft_testing --diagnostic
# Review the generated FT source before executing:
python -m llm_ontology.benchmarks.defects4j_runner evaluate --config "$CFG" --run-id "$RUN" --arm ft_testing --reviewed-local-execution
python -m llm_ontology.benchmarks.defects4j_runner generate --config "$CFG" --run-id "$RUN" --arm rag_single --diagnostic
# Review the generated RAG source before executing:
python -m llm_ontology.benchmarks.defects4j_runner evaluate --config "$CFG" --run-id "$RUN" --arm rag_single --reviewed-local-execution
# Optional existing MultiRAG arm: substitute rag_multi.
~~~

Use a new run ID after any implementation/config change. Prompt families and model
sampling/output contracts were not tuned on the benchmark. Scientific results
remain blocked by historical lineage, OS isolation, clean multi-project selection
and executable model-output readiness. Protected existing dirty files and all
historical negative model-output artifacts were left untouched. No push.
