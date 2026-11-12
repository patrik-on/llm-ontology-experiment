# Java testing benchmark selection (2026-11-12)

**Research status: RESEARCH_READY. Execution status: EXECUTION_NOT_READY.**

## Decision

Select **Defects4J v3.0.1** as the primary executable Java testing benchmark.
Start with a small, preregistered, leakage-audited subset rather than all bugs.
Use real-fault detection alongside compilation and executed-test/pass rates.
Real coverage can follow; the existing coverage proxy is not executed coverage.

This is a benchmark selection and preparation plan, **not evidence of a completed
benchmark run**. No upstream project was built, no model generation was run,
and no dependencies, toolchains, or benchmark archives were installed/downloaded
for execution during this audit. Small public source/metadata responses were
read over the network. This document was the only repository file added by the
subsequent documentation task. Existing dirty user files were left untouched.

Defects4J's native generated-suite runner is JUnit 4 based. The project's
canonical prompt requires JUnit 5 and structured JSON. Preserve that prompt:
use Defects4J for project checkout/build/export and a pinned JUnit 5 execution
adapter for generated tests. Do not silently change prompts to JUnit 4 or claim
that native Defects4J generated-suite commands already support Jupiter.

## Scope and evidence

Repository inspected:

- Path: C:/Users/patri/OneDrive/Dokumenty/GitHub/llm-ontology-experiment
- Base commit: e020e50a2694586041644bb3831194e32d4fa849
- Read first: devinfo.md and README.md.
- Other inspected documentation: docs/experiments/testbench_runbook.md,
  docs/experiments/environment_and_splits.md, docs/experiments/baseline_v1.md,
  and the existing untracked docs/datasets/data_audit_report.md.
- Live sources were checked on 2026-11-12 using web retrieval and small
  read-only HTTP requests. GitHub API search was sometimes rate-limited;
  repository/raw-file endpoints and primary publication pages were used instead.
- No unit tests, external builds, inference, or runtime benchmark validation were
  performed. Findings below distinguish source inspection from actual execution.

Read-only local checks included:

~~~powershell
git status --short
git rev-parse HEAD
Test-Path benchmarks/TestBench-main
wsl --list --quiet
wsl -e sh -lc 'uname -sr; java -version; javac -version; mvn -version'
wsl -e sh -lc 'command -v defects4j; command -v svn; command -v cpanm; command -v git; command -v perl; ls /usr/lib/jvm'
~~~

The bounded filesystem search inspected /home and /opt to depth four for a
TestBench directory. The artifact search inspected repository artifacts for
TestBench execution references and common Maven dependency failures. A negative
bounded search is not a claim about every location on the host.

## Current local state

| Component | Observed result |
|---|---|
| Final runtime | WSL/Linux only, as required by devinfo.md |
| WSL | Ubuntu; Linux 6.18.54.1-microsoft-standard-WSL2 |
| WSL Java and javac | OpenJDK 17.0.20.1 |
| WSL Maven | Apache Maven 3.9.16 |
| Installed JDK directories listed | Java 17 only |
| TestBench configured root | benchmarks/TestBench-main: absent |
| Other TestBench checkout | None found in the bounded /home and /opt search |
| Defects4J command | Not found on the checked WSL PATH |
| SVN / cpanm | Not found on the checked WSL PATH |
| Git / Perl | Found on the checked WSL PATH |
| Cached JUnit artifacts | Jupiter 5.11.4; Platform 1.11.4 and some 1.9.3 jars |
| Cached JaCoCo artifacts | None found in the bounded Maven-cache search |
| Real TestBench canary/build evidence | None found in searched artifact locations |

Historical Windows environment-lock documentation saying Java/Maven were absent
must not be used as the current WSL readiness assessment. Conversely, available
Java 17/Maven do not establish compatibility with TestBench's documented JDK 8
legacy projects or Defects4J v3.0.1's Java 11 requirement.

## Existing TestBench integration audit

### Adapter and configuration

- src/llm_ontology/benchmarks/testbench.py reads
  source_file_parser/*_out.json and supports source/simple/full context.
- It preserves target metadata and avoids importing upstream model scripts.
- The loader does not itself enforce case count, pinned project revisions,
  checksums, complete provenance, or leakage clearance.
- src/llm_ontology/benchmarks/readiness.py checks 108 unique IDs and POM presence,
  but does not establish a successful clean build or generated-test discovery.
- configs/benchmarks/testbench.yaml expects 108 cases, direct Ollama generation,
  JDK 8 by default, and JDK 17 for project Java.
- scripts/experiments/benchmarks/run_benchmark.py and evaluate_testbench.py do not
  load that YAML. Its settings are not an enforced executable experiment lock.

### Prompt/output mismatch and orchestration gap

- testbench.py:15-17 requests a complete Jupiter class and says to return only
  Java source.
- src/llm_ontology/inference/prompting/canonical.py:23,34 requires JUnit 5 and
  structured JSON including generated_tests.
- src/llm_ontology/benchmarks/runner.py:29-31 stores the generator's raw output
  as prediction.
- testbench_execution.py treats prediction as Java; it does not validate and
  extract canonical generated_tests JSON.

These contracts conflict. A correct structured response is not correctly routed
into execution. Resolve this at the adapter/output boundary through the shared
structured-output path, not by modifying shared prompts.

The benchmark runner prepares direct prompts and calls a generation helper. It
does not implement the controlled three-mode experiment through the shared
RagExperimentRunner or capture the complete frozen provenance. Do not expand it
into a second retrieval/provider/orchestration implementation.

### Maven evaluator: positive controls and correctness gaps

Inspected src/llm_ontology/benchmarks/testbench_execution.py.

Existing useful controls:

- Root-bounded path resolution and path traversal rejection.
- Generated-class selection and project-specific JAVA_HOME.
- Restoration of a colliding source file in finally.
- A planning-only dry-run path.

**Critical false acceptance:** Maven arguments at lines 132-133 disable failure
for no specified tests/no tests. _status_for_process at lines 170-172 returns
accepted for every zero exit code. No Surefire XML check confirms that the
newly generated class ran at least one non-skipped test. Thus accepted means
Maven exited successfully, not proven generated-test success.

Other limitations:

- PIT is explicitly skipped and neither PIT nor JaCoCo results are collected.
- Package repair only supplies a missing declaration; an existing mismatched
  declaration is not actually validated against target metadata.
- Existing test sources can still be compiled.
- Per-case clean working trees/build outputs are not guaranteed.
- Timeout handling does not establish termination of the whole process tree.
- Restoring one source file is not an execution sandbox.
- The evaluation CLI's exit status flags invalid records, not every ordinary
  compile/test/Maven failure; consumers must inspect the recorded outcomes.

No real upstream dependency/build failure was reproduced in this audit. The
missing checkout, output-contract mismatch, and zero-test success logic are
confirmed readiness/correctness problems; specific legacy dependency failures
remain risks, not observed runtime results here.

### Framework unit tests are not real benchmark validation

Inspected tests/experiments/test_benchmarks.py,
test_testbench_execution.py, and test_testbench_prompt.py. They use synthetic
JSON, temporary minimal POMs, and a mocked subprocess returning BUILD SUCCESS.
They test adapter/control-flow behavior, not real upstream compilation,
JUnit discovery, dependency resolution, coverage, or fault detection.

src/llm_ontology/evaluation/coverage_runner.py explicitly raises
NotImplementedError for real JaCoCo coverage. Existing reports identify their
structural coverage score as a proxy. Smoke-fixture validation and Python unit
tests must remain separate from proof of real benchmark evaluation.

## Upstream TestBench assessment

Primary sources:

- Repository: https://github.com/iSEngLab/TestBench
- Observed commit: 6d018f543932c381312d168c7c3ba50abc83f748
- Paper: https://arxiv.org/abs/2409.17561
- Paper HTML: https://arxiv.org/html/2409.17561v1
- Execution source: https://raw.githubusercontent.com/iSEngLab/TestBench/main/execute_test.py
- Coverage source: https://raw.githubusercontent.com/iSEngLab/TestBench/main/parse_jacoco.py

The paper describes 108 focal functions/programs from nine projects:
JFreeChart (6), Commons-lang (3), Commons-math (8), JCTools (7), JavaCV (13),
Java algorithms (35), Jeecg Boot (15), ZXing (13), and Apollo (8).
Its metrics include syntax, compilation, test correctness, line coverage, and
mutation-based defect detection. These are relevant executable testing goals.

Executable Java projects are a separate archive linked by the README:
https://drive.google.com/file/d/1syRdGJfvM7ZWlvEwuEBFrYDNrtw-NGzh/view
The landing page returned HTTP 200 and title java_project.zip. The archive was
not downloaded; its contents, revisions, checksums, licenses, and current
buildability were not established.

Confirmed source-level pitfalls:

- Hardcoded /home/joseph paths and shell-based Maven invocation.
- execute_test.py imports generate_content_repair, whereas the checked root
  listing contains content_repair.py and not the imported module.
- Upstream writes delete colliding tests and later remove generated files.
- Mutation extraction relies on log regexes.
- Coverage code derives the target class from the generated test's name by
  removing Test/Tests suffixes, risking attribution errors for arbitrary names.

The local JDK 8/17 project matrix cannot be independently validated against the
missing executable archive. No exact upstream Maven, JDK-patch, JaCoCo, and PIT
lock was established from the inspected materials. The checked repository root
had no license file and /LICENSE returned 404. This is a licensing uncertainty,
not permission to redistribute; individual Java project licenses also apply.

**Verdict:** relevant, but not the preferred first benchmark while executable
inputs, licensing, environment pinning, and evaluator correctness are unresolved.

## Recommended source: Defects4J v3.0.1

| Identity | Exact selection |
|---|---|
| Repository | https://github.com/rjust/defects4j |
| Release | v3.0.1 |
| Commit | 6d54320e0db5a357f9ab38a8e4d2e5aead7e1c09 |
| Pinned README | https://raw.githubusercontent.com/rjust/defects4j/v3.0.1/README.md |
| Framework license | MIT; https://raw.githubusercontent.com/rjust/defects4j/v3.0.1/license.txt |
| Dataset identity | Project ID, active bug ID, fixed/buggy revision IDs, exported metadata and content hashes |

Primary publication: Just, Jalali, and Ernst, Defects4J: A Database of Existing
Faults to Enable Controlled Testing Studies for Java Programs, ISSTA 2014.
DOI: https://doi.org/10.1145/2610384.2628055

The README's old UMass paper URL returned 404. The replacement author-hosted PDF
returned HTTP 200: https://homes.cs.washington.edu/~rjust/publ/defects4j_issta_2014.pdf
Publication identity was also checked against Crossref. The PDF URL was checked
for availability, not parsed as experimental evidence; release behavior below
is grounded in the pinned README and source files.

### Why this benchmark

- 854 active real bugs across 17 Java projects, plus ten deprecated bugs.
- Explicit fixed and buggy program versions.
- Reproducible triggering-test principle: fail before the fix, pass after it.
- Existing compile/test/export interfaces and native coverage, mutation, and
  generated-suite fault-detection infrastructure.
- No paid model service is required; local-model outputs can be evaluated.
- The framework's MIT license is explicit. Subject projects and bundled
  dependencies retain their own licenses; preserve their notices and inventory.

Defects4J is a real-fault benchmark and infrastructure, not a ready-made
canonical-prompt LLM harness. The proposed JUnit 5 adapter is still required.

### Toolchain and environment

The pinned release requires Java 11, Git >=1.9, SVN >=1.8, Perl >=5.0.12,
cpanm, and the Perl modules listed in cpanfile. Set TZ=America/Los_Angeles.
Upstream warns that different Java versions/timezones can yield unexpected
failures and non-reproducible bugs. Deprecated bugs must not enter the pilot.

The live upstream CI inspected during research specifies JDK 11.0.17. Use a
reviewed distribution/checksum and record the exact patch level; do not treat
this observation as a locally installed or locally validated toolchain.
Defects4J 2.x instead required Java 8, so version-specific instructions must not
be mixed.

Defects4J's standardized build/export interface is central, not a single
external Maven version. Record any build tools/dependencies actually used;
Maven 3.9.16 on this host does not by itself make the benchmark ready.
Initialization downloads subject repositories and external libraries: a clone
alone is incomplete and a full init is outside this bounded research task.

### JUnit 5 interoperability plan

Pinned source checked:
https://raw.githubusercontent.com/rjust/defects4j/v3.0.1/framework/projects/defects4j.build.xml

It declares junit-4.12-hamcrest-1.3.jar and uses Ant junit tasks. The native
external-suite path in framework/bin/d4j/d4j-test compiles and runs tests through
that infrastructure. Therefore native defects4j test -s is not established as
a Jupiter-compatible path.

Plan:

1. Build each revision and export source/binary directories and classpaths via
   Defects4J, without exposing original tests or triggering metadata to prompts.
2. Validate shared structured output and extract generated_tests unchanged.
3. Compile the generated JUnit 5 class against the revision's production
   binaries/dependencies plus one coherent, pinned Jupiter dependency set.
4. Execute exactly that class using a real JUnit Platform launcher; parse
   discovery/execution results rather than trusting process success alone.
5. Run the same generated source against fixed and buggy revisions in separate
   clean workspaces, with the same limits and dependency policy.
6. Initially report compile/pass/real-bug metrics. Add JaCoCo instrumentation
   separately; native Defects4J mutation/coverage results cannot be claimed to
   cover Jupiter outputs until that interoperability is actually validated.

The local cache offers Jupiter 5.11.4 and matching Platform 1.11.4 as a candidate
set, not a proven adapter. Pin complete transitive dependencies and hashes.
Do not mix older cached Platform 1.9.3 jars or use lexicographic latest-jar
selection as a lock. The existing smoke Java/JUnit validation helpers are
implementation evidence to reuse where appropriate, not proof that the proposed
Defects4J adapter already exists.

## Alternative comparison

### ProjectTest / MultiFileTest

- Repository: https://github.com/YiboWANG214/ProjectTest
- Observed commit: a893144b017c44e9a042d605a04baa447f525433
- Paper: https://arxiv.org/abs/2502.06556
- Dataset: https://huggingface.co/datasets/yibowang214/MultiFileTest
- MIT repository license and MIT dataset-card metadata were live-checked;
  subject-source provenance/licenses must still be retained.

This is a relevant multi-file test-generation benchmark with executability,
correctness, line coverage, and branch coverage. Current arXiv v5 calls it
MultiFileTest (ACL 2026 Findings); the repository README still calls it
ProjectTest. The README specifies Java 17.0.13 and Maven 3.6.3.

Checked Java POMs use source/target 11, JaCoCo 0.8.8, Surefire 3.0.0, and compiler
plugin 3.11.0. They are closer to the project's JUnit 5 contract, but mix Jupiter
5.8.1 with plugin engine 5.9.1; a checked passwordGenerator POM duplicates
Mockito 5.5.0/5.7.0 dependencies.

Material artifact issues:

- Paper says 20 Java projects; checked GitHub dataset/JAVA lists 19.
- The public 178,379-byte HF Java.jsonl was read in memory and has 19 records.
- Checked GitHub combined source uses package projecttest; HF data uses
  projecteval. Do not mix releases/normalizations.
- ProjectTest/JAVA/main/passwordGenerator.java includes GeneratorTest with
  actual Jupiter tests/assertions. Passing combined source wholesale to the
  model would expose existing tests.
- heap.java includes a HeapPerformanceTest boundary, requiring explicit
  classification rather than treating every file as production source.
- The README's generation/others/run_all.sh invokes JavaScript evaluation;
  it is not a verified complete Java execution entry point.
- Spring/Redis/MongoDB/AWS/network/UI examples need explicit dependency and
  service isolation policy, not live service credentials or unrestricted I/O.

**Verdict:** credible secondary candidate, but reconcile version/count mismatch,
separate tests from production inputs, and validate the Java harness first.
Do not claim complete 20-project reproduction from the checked 19-record data.

### SF110

Primary source: https://www.evosuite.org/experimental-data/sf110/

SF110 extends 100 randomly sampled SourceForge Java projects with ten popular
projects. The official page offers dependency-inclusive binaries (943 MB) and
sources/tests (1,014 MB); neither archive was downloaded. It explicitly directs
users to individual project licenses. Source distribution includes original
and EvoSuite tests, which must remain outside prompts/training/retrieval.

This is an established test-generation/coverage corpus, but its older projects,
large artifact size, and unestablished single exact modern JDK/build environment
make it a less practical first WSL pilot. EvoSuite-generated suites may require
its runtime. It is not a ready-made controlled LLM experiment harness.

## Required positive discovery and evaluator controls

Before any model-generated benchmark run, validate the real adapter with
handwritten canaries and assert report contents:

| Control | Required outcome |
|---|---|
| Passing Jupiter test | Selected class discovered; at least one non-skipped test executed and passed |
| Deliberately failing assertion | Executed failure, not accepted |
| Java compilation error | Compile failure; never a detected bug |
| Empty test class | No-tests/discovery failure, not accepted |
| Disabled-only test class | No effective tests, not accepted |
| Timeout | Explicit timeout; whole process tree terminated |
| Stale report from prior run | Not consumed as current evidence |
| Known evaluator-only fault-revealing test | Repeated fixed passes and genuine buggy failure |

Require fresh report paths and workspaces, selected class identity, nonzero
executed count, skipped counts, failures/errors, and verified process completion.
Use a sandbox/unprivileged account with resource limits; generated tests and
build plugins can execute arbitrary code. Populate dependencies in a separately
controlled preparation phase, then restrict network access during evaluation.

## Preparation commands: proposed, NOT EXECUTED

These commands describe a subsequent reviewed preparation task. They include
writes, dependency installation and upstream initialization and were **not run**
by this audit. Review toolchain provenance, download volume, external build code,
and required permissions first. Use Linux storage rather than a OneDrive mount.

After provisioning a reviewed JDK 11 distribution and required system tools:

~~~bash
set -eu
# Replace this placeholder with the reviewed, checksummed JDK 11 location.
export JAVA_HOME=/path/to/reviewed/jdk-11.0.17
export PATH="$JAVA_HOME/bin:$PATH"
export TZ=America/Los_Angeles
java -version
javac -version
git --version
svn --version --quiet
perl -v
command -v cpanm

mkdir -p "$HOME/benchmark-work"
cd "$HOME/benchmark-work"
git clone --branch v3.0.1 https://github.com/rjust/defects4j.git defects4j-v3.0.1
cd defects4j-v3.0.1
test "$(git rev-parse HEAD)" = 6d54320e0db5a357f9ab38a8e4d2e5aead7e1c09

# Official setup steps; review first. init.sh downloads external data/libraries.
cpanm --installdeps .
./init.sh
export PATH="$PWD/framework/bin:$PATH"
defects4j info -p Lang -b 24
~~~

Lang-24 is an active candidate canary also exercised in upstream CI. It has
**not** been cleared for overlap with this project's actual training/retrieval
data. Its inclusion in final evaluation is conditional on the audit below.

After installation and candidate approval:

~~~bash
set -eu
export TZ=America/Los_Angeles
WORK="$HOME/benchmark-work/defects4j-pilot"
mkdir -p "$WORK"
# Use fresh directories; stop rather than overwrite an existing checkout.
test ! -e "$WORK/lang24f"
test ! -e "$WORK/lang24b"
defects4j checkout -p Lang -v 24f -w "$WORK/lang24f"
defects4j checkout -p Lang -v 24b -w "$WORK/lang24b"

cd "$WORK/lang24f"
defects4j compile
defects4j test
defects4j export -p cp.compile
defects4j export -p cp.test
defects4j export -p dir.bin.classes
defects4j export -p dir.src.classes

cd "$WORK/lang24b"
defects4j compile
defects4j test
~~~

Capture logs, versions, exported metadata, source hashes and expected original
triggering behavior from both revisions. The buggy original suite is expected
to expose the known fault; do not treat that as an infrastructure failure.
These commands validate upstream projects only. They do not yet validate the
proposed JUnit 5 generated-test adapter. No unimplemented project-specific CLI
is presented here as if it already exists.

## Leakage-safe pilot and controlled experiment protocol

1. Create benchmark-only manifests with indexing_allowed=false. Never send
   benchmark cases, original tests, generated reference tests, patches, expected
   failures, or fault labels into retrieval or fine-tuning.
2. Audit actual fine-tuning training material and actual retrieval source/index
   contents against candidate project/repository identities and exact/normalized
   class/method fingerprints. An external name is not proof of independence
   from Methods2Test or other project-derived corpora.
3. If overlaps exist, select a preregistered clean benchmark subset or create a
   separately versioned training/retrieval baseline. Never silently mutate
   existing indexes or relabel their manifests.
4. Freeze approximately five active bugs across at least three eligible projects
   before seeing model outcomes. Record exclusions and baseline-build failures.
   Candidate IDs are not automatically leakage-cleared pilot membership.
5. For fault-detection evaluation, use the fixed production source as the declared
   test-generation input and evaluate the same test on fixed/buggy revisions.
   This is an explicit test-generation protocol, not an issue-repair task.
   Keep patches, original tests and triggering metadata evaluator-only.
6. Use the shared canonical prompt/schema, provider and RagExperimentRunner.
   Source, project context, output contract and evaluator are identical across
   Direct/RAG/MultiRAG. Only the retrieved-evidence block varies.
7. Decode generated_tests through the shared structured-output path; freeze any
   package repair, retries, timeout, output/context limits, sampling and seed.
   Do not copy upstream generation prompts or heuristic repairs into one mode.
8. Pin generation/embedding digests, adapter identity for fine-tuned variants,
   dataset/collection manifests, prompt artifacts/hashes, full config, retrieval
   traces and per-stage evaluation outcomes.
9. Do not amend baseline_v1, whose frozen dataset is handcrafted smoke. Give the
   new benchmark protocol its own version/config identity while retaining shared
   prompt semantics and evaluation across compared modes.

Report compilation rate, nonempty executed-test rate, pass rate on fixed code,
and real-bug detection rate. A detected bug requires the same generated test to
compile against both revisions, repeatedly pass on fixed, and fail during real
test execution on buggy code. Compilation/dependency/discovery failures are not
bug detections. Separate flaky tests, timeouts and infrastructure failures.
Report unconditional rates over all attempts as well as conditional rates over
executable outputs; do not hide failed generations by dropping them.

Add actual line/branch coverage only after validating instrumentation and clean
report attribution. Do not label the coverage proxy as JaCoCo coverage or claim
native Defects4J mutation reproduction without a verified Jupiter path.

## Completion gates and honest status

**RESEARCH_READY** means sources, selection rationale, local gaps, limitations,
and a bounded preparation protocol are documented. It does not mean the selected
benchmark has passed a local build or that an adapter is implemented.

**EXECUTION_NOT_READY** remains until all of the following are evidenced:

- Reviewed Java 11/SVN/Perl toolchain and pinned initialized benchmark assets.
- Subject-code license/provenance inventory and source/checksum records.
- Leakage-cleared, preregistered case manifest tied to actual training/index IDs.
- Successful expected upstream fixed/buggy baseline behavior.
- Real JUnit 5 adapter with positive/negative discovery controls and isolation.
- Shared structured-output and three-mode runner integration/provenance.
- Separate verified metric implementations and failure classification.

The existing Python framework tests, deterministic smoke checks, and source-level
audit are valuable, but none satisfies these real benchmark execution gates.
