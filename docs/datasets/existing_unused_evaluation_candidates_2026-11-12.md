# Existing unused evaluation data — 2026-11-12

## Decision

**Yes: Methods2Test is already the right existing source for further testing evaluation.**
The local official test partition contains **78,388 records**; only **500** were
materialized in our testing test JSONL. That leaves **77,888 raw test records not
selected into any current processed split**. They need screening and executable
packaging, not another dataset download or another training run.

Three concrete, short, JDK-only production-method candidates are identified below.
Their production and reference code are absent from the current materialized
training/validation assets and actual V3 retrieval contents under the checks
specified here. **They are reference-ready, not yet executable benchmark cases.**
No generation, training, installation, download, external build, index rebuild,
full test suite or new benchmark integration was performed for this audit.

Inspection base: repository HEAD `e3b99ac`, Ubuntu WSL, existing `.venv_wsl`.
Read first: `devinfo.md`, `README.md`, the user-owned untracked
`docs/datasets/data_audit_report.md`, and the prior repository audit. This is an
additive report, not a rewrite of those documents or historical experiment claims.

## 1. All local source families and their actual uses

Counts are rows unless explicitly marked as projects/containers. FT columns are
**selected train / validation / internal test**, not optimizer exposure counts.
RAG counts are actual unique documents per source, **not** collection-count sums.

| Dataset/source | Purpose; actual local raw inventory | Selected FT train / val / test | Actual V3 RAG unique docs | Unused reserve and execution context |
|---|---|---:|---:|---|
| Methods2Test | Testing; **780,944 expanded corpus JSON records**, 9,410 project directories; **4,408,368,183 B** across the three expanded splits | **4,000 / 500 / 500**; same records also occur in B1 combined | **3,978** | **77,888 unmaterialized official-test records**; rich method/test metadata exists locally in compressed dataset archives. Best testing source. Not complete executable projects. |
| ML4Refactoring | Refactoring; `data/raw/ML 4 Refactoring dataset/all.zip` **40,783,884,999 B**; **11,150 project ZIPs**, also present at `/mnt/c/datasets/ml4refactoring/all/dataset` (40,781,558,631 B) | **4,000 / 500 / 500**, from only **17 projects**; same records also in B1 and final refactoring mixture | **1,283** | **11,133 other project containers** beyond the 17 identified Apache project ZIPs; not a verified count of viable pairs. No official held-out partition established by these assets. Before/after snapshots, not a ready test-generation or behavior-evaluation harness. |
| MaRV | Refactoring only; `data/raw/marv/dataset/MaRV.json` **698 records**, **3,488,734 B**; four operation groups | **478 / 100 / 108**, included in final refactoring but **not** B1 | **478** | 108 internal-test records, 57 with two positive votes; all 108 pass the current code-hash absence check against train/val/RAG, but repository/commit independence is not established by that check. Only **12 raw records** are outside all processed splits, and their after values are deletion-only diff headers, not useful complete Java references. Not a testing dataset. |
| SWE-Refactor, pinned Zenodo 17196850 | Refactoring; **1,099 unique IDs**, **18 projects**, six operations; local pure JSON **67,505,459 B** | **0 / 0 / 0** as a selected source | **0** as a source | Existing external refactoring reserve, not a new download. 922 atomic / 177 compound cases. Per-case cross-source overlap clearance and project/application/harness work remain necessary; do not call all 1,099 unseen or executable. |
| Handcrafted smoke v1 | Testing + refactoring; **24 cases**, 12 per domain; case JSONLs **22,359 + 26,518 B** | **0 / 0 / 0** | **0** | Reserved pipeline/regression fixtures, already explored by smoke runs; not a fresh scientific test set. Existing behavior fixtures are different from a general real-project benchmark. |
| Synthetic format validation | Testing; **one BatchSizer subject** at `data/validation/testing_full_class_v2/BatchSizer.java`; 678 B; separate Labels solved demonstration | **0 / 0 / 0** | **0** | Explicit validation/demo roles. Manifest forbids indexing and labels the fixture non-scientific. Do not recycle validation/demo material as a fresh final holdout. |
| Defects4J prepared cases | Testing; **Lang-24, Lang-26, Lang-27**, each with fixed/buggy prepared metadata (**225,729 B** across three prepared JSONs) and six existing production-class directories | **0 / 0 / 0** as a selected dataset source | **0** as a source; cross-source overlap is not inferred from this | Already explored in the recorded pilots. Existing shared Jupiter path and prepared subjects can support further authorized diagnostics, but these three are not unused evaluation cases. No new subject build or execution here. |
| TestBench | Testing; configured `benchmarks/TestBench-main` **absent** | 0 | 0 | Config/adapter, not locally available evaluation data at that root. |
| MultiFileTest | Suggested external testing source; no configured/local benchmark copy found in the bounded inspected roots | 0 | 0 | Not needed for this existing-data recommendation; no download or research integration attempted. |
| Schema samples / external documents | Three small `data/samples/*_sample.json` format examples; `data/external` has only placeholder/documentation files | 0 | 0 | Documentation, not an unused benchmark. No approved literature corpus. |

The documented sibling `../si-context-eval` is a separate educational fixture
experiment: its README describes 12 testing and 12 refactoring tasks, and this
repository already contains analysis of its runs. Only its README/bridge were
read for classification; no new sibling-source or run audit was performed. Do
not count those fixtures as another Methods2Test/ML4Refactoring raw reserve.

### Sampled raw schemas and identities

- Methods2Test corpus: `src_fm`, `src_fm_fc`, `src_fm_fc_co`,
  `src_fm_fc_ms`, `src_fm_fc_ms_ff`, `target`. Rich records have
  `repository`, `focal_class`, `focal_method`, `test_class`, `test_case`.
- ML4Refactoring is not a per-example JSON source: a pair is identified by
  project/commit/relative before-after paths inside a project ZIP. Directly
  checked `apache-abdera.zip`, commit
  `77e8fe85a70c803dfff55cf4a3d0b8f929646607`,
  `core/src/main/java/org/apache/abdera/util/NamedItem.java-1-Move Class-0-`: its
  before/after members are 82/87 B. Production code is present, but complete
  project/build/test context is not established by such a snapshot pair.
- MaRV groups lists by operation; each record carries `refactoring_id`,
  `commit_sha`, `commit_link`, `file_path`, `description`, `code_before`,
  `code_after`, `evaluations`. These code fields can be **unified-diff hunks**,
  not directly compilable Java. Directly checked ID `189767`, OsmAnd commit
  `8f6f447926d12a4607d38a864bf4c271e9e6ecf9`,
  `OsmAnd/src/net/osmand/plus/mapcontextmenu/MenuController.java`. Its positive
  reviewer votes do not turn a diff fragment into a complete class. The local
  698-record file also differs from the 693-case published evaluated subset.
  Its 478/100/108 split is internal, not an official upstream evaluation split.
- SWE is a benchmark list with `uniqueId`, project/commit/path fields, full and
  primary before/after code, operation, compile-command/JDK and result metadata.
  Example observed ID
  `67b98ab96e15fba231ca494c7ce3752cce0a9654_57_71__61_75_86_91` is checkstyle
  `SinglelineDetector.java`, Inline Method. Stored build/test flags are references,
  not local execution evidence; upstream evaluator bypasses and missing pinned
  subjects remain as documented in the acquisition report. It is not another
  training dataset with an official train/validation split.

### Mixtures are not new independent sources

Live multiset comparisons confirmed all three splits exactly:

- `data/processed/refactoring/*` = ML4Refactoring + MaRV:
  **4,478 / 600 / 608**, totaling **47,302,004 B** across JSONLs.
- `data/processed/combined/*` = Methods2Test + ML4Refactoring, no MaRV:
  **8,000 / 1,000 / 1,000**, totaling **50,364,682 B**.
- Source-only JSONL totals: testing **6,440,422 B**; ML4Refactoring
  **43,924,260 B**; MaRV **3,377,744 B**.

The old materialized ML4Refactoring split is an internal record-level split,
not an official independent holdout: **188 unique exact pairs** occur in train
and test, and 187 in train and validation. The same pair overlaps propagate to
the two mixtures. Current group-aware preparation code does not retroactively
change these stored files or their adapters.

## 2. What is actually unused in Methods2Test?

A single streaming traversal counted file metadata under the configured
`data/raw/methods2test/corpus/json` subtree, without loading the corpus into RAM.

| Official source partition | Local records | Local bytes | Project IDs | Materialized rows | Not materialized |
|---|---:|---:|---:|---:|---:|
| train | 624,022 | 3,479,781,116 | 7,440 | 4,000 | 620,022 |
| eval (our validation) | 78,534 | 474,254,434 | 953 | 500 | 78,034 |
| test | 78,388 | 454,332,633 | 1,017 | 500 | **77,888** |
| Total | **780,944** | **4,408,368,183** | **9,410** | **5,000** | **775,944** |

All three official project-ID intersections were empty. The local README also
states repository-disjoint official splitting. The processed selection covers
only **66 train, 6 validation, 18 test project IDs**; all 5,000 materialized
source paths are distinct. Each row has five alternate focal-context views;
these views, tokenized/raw copies and the older `methods2test-v1.0` tree are
**not millions of additional independent method/test pairs**.

The **77,888** number is an inventory subtraction, not a declaration that every
remaining row is unseen code, from a previously unused repository, a correct
mapping, independently deduplicated, or directly executable. Unused raw train
records can share a repository or focal method with selected training examples.
Even the 500 materialized test rows are not uniformly code-disjoint: **494/500**
have both normalized input and output hashes absent from current train/val/RAG;
six fail that conservative check. This is separate from exact-pair overlap (zero
for testing) and explains why record-level absence alone is insufficient.

**Recommendation:** reserve official-test projects absent from materialized
train/validation/RAG, then screen source identities and both code sides. Do not
use the unused official eval partition as the final benchmark after tuning on it.
Do not regenerate/retrain the present datasets just to use a small clean reserve.

## 3. Actual adapter and retrieval boundary checked

Live training summaries and config snapshots were read at:

`/home/patrik/experiments/llm-ontology-v2/{b2_testing,b2_refactoring,b1_shared}/results/`.

| V2 adapter | Recorded selected files/counts | Recorded completed training / best checkpoint |
|---|---|---|
| b2_testing | `testing/train.jsonl` 4,000; `testing/val.jsonl` 500 | **300 steps, 0.6 epochs**, best checkpoint-100; not two completed epochs |
| b2_refactoring | `refactoring/train.jsonl` 4,478; `refactoring/val.jsonl` 600 | 1,120 steps, 2.0 epochs, best checkpoint-1120; resumed checkpoint-1000 |
| b1_shared | `combined/train.jsonl` 8,000; `combined/val.jsonl` 1,000 | 600 steps, 0.6 epochs, best checkpoint-400 |

The active testing adapter is
`/home/patrik/experiments/llm-ontology-v2/b2_testing/checkpoints/final_adapter`.
Validation influenced checkpoint selection (`eval_loss`, best-model loading),
so all selected validation records are excluded, not just gradient-training rows.
All selected train rows are conservatively considered exposed even for sub-epoch
runs; no claim is made about which examples a particular optimizer step saw.

**Evidence boundary:** hashes of today's materialized files are verified below;
training summaries name those paths/counts but do not bind them to historical
source-byte hashes. Thus source-file selection is corroborated, while exact
training-time snapshot identity is inferred, not cryptographically established.
Unknown base-model pretraining or unrecorded historical copies do not block this
bounded recommendation and are not mislabeled as known leakage.

SQLite was opened with `mode=ro` and `PRAGMA query_only=ON`; no Chroma client or
migration was invoked. The actual `data/chroma/ollama_bge_m3_v3/chroma.sqlite3`
is **305,373,184 B**, with 1,024-dimensional collections:

| Collection | Documents | Source breakdown |
|---|---:|---|
| mixed | 5,739 | Methods2Test 3,978; ML4Refactoring 1,283; MaRV 478 |
| testing_db | 3,978 | Methods2Test 3,978 |
| refactoring_db | 1,761 | ML4Refactoring 1,283; MaRV 478 |

Across all three collections there are **5,739 distinct embedding IDs and
5,739 distinct stored document texts**, not 11,478 independent examples.
All indexed Methods2Test `source_file` paths resolve back to the selected
`testing/train.jsonl` provenance set (zero unmatched paths). Missing repository
URLs in testing metadata were handled using the numeric project ID embedded in
those paths, rather than interpreting missing metadata as no overlap.

Both sides of all **5,739 actual mixed documents** were parsed from their stored
production/reference sections and normalized, including refactoring outputs.
The selected candidates were checked against that actual content as well as
stored input/focal hashes and source identities, not merely a builder report.
The production corpus artifacts additionally show 3,986 testing and 2,043
refactoring pre-deduplication rows; they are not additional independent corpora.
General older config roots remain historical: the available actual index is V3.

## 4. Three concrete existing official-test candidates

Selection was made **before any new model output**: official test; unselected
project/source; no current train/val/RAG code match; short public static utility;
actual focal invocation plus assertion in the reference; JDK-only production
logic; no date/time, network, service, mocking or framework fixture requirement.
Within the bounded archive prefix, the first distinct methods meeting the manual
JDK-only/simple-utility screen were retained in archive order. No success-based
selection occurred. This is a **one-project canary reserve**, not a representative
three-project benchmark or a generalization score.

Common repository: `https://github.com/webauthn4j/webauthn4j`,
Methods2Test project ID **134147639**. Despite the parent project's domain, these
specific production methods have no WebAuthn/security-framework dependencies.

Corpus path prefix:
`data/raw/methods2test/corpus/json/test/134147639/`.
Rich source: `data/raw/methods2test/dataset/test.tar.bz2` members
`test/134147639/<ID>.json`; corresponding corpus files are `<ID>_corpus.json`.

| ID | Focal API | Existing source context / missing executable wrapper |
|---|---|---|
| **134147639_39** | `UUIDUtil.fromString(String)` | Source `webauthn4j-util/src/main/java/com/webauthn4j/util/UUIDUtil.java`; JDK `java.util.UUID`, no state/helper dependency. Reference has one real equality assertion and one qualified focal invocation. Needs class/package/import and test-class wrapper. |
| **134147639_28** | `UnsignedNumberUtil.getUnsignedLong(ByteBuffer)` | Source `webauthn4j-util/src/main/java/com/webauthn4j/util/UnsignedNumberUtil.java`; JDK `java.nio.ByteBuffer` + `java.math.BigInteger` only. Reference exercises an unsigned boundary and uses `UNSIGNED_LONG_MAX`; its full initializer is available in rich `focal_class.fields`. Needs those imports/class wrapper and reference constant context. |
| **134147639_15** | `UnsignedNumberUtil.getUnsignedByte(byte)` | Same source class; JDK `Byte.toUnsignedInt` only, no helper/state. Reference checks the unsigned conversion with one assertion and one qualified focal call (not merely a matching test-method name). Needs class/test wrappers. |

Original reference class paths are respectively
`webauthn4j-util/src/test/java/com/webauthn4j/util/UUIDUtilTest.java` and
`webauthn4j-util/src/test/java/com/webauthn4j/util/UnsignedNumberUtilTest.java`.

For **each of these three**, verified:

- Project 134147639 is absent from **all 90 materialized Methods2Test project
  IDs**, not only train/validation; its source paths are absent from current RAG.
- Repository URL is absent from explicit MaRV train/validation repository URLs;
  it is not one of the 17 selected ML4Refactoring projects.
- Both production and reference lexical SHA-256 fingerprints are absent from
  every source/mixture **train and validation** file and both actual RAG sides.
- Neither normalized code string occurs as a contained fragment of the checked
  train/validation or stored RAG code, protecting against whole-class containment.
- Rich and corpus production/reference code agree after the repository's lexical
  normalization; the candidate references are also absent from materialized tests.
- Production and reference snippets parse successfully using the existing
  `JavaParser` (Tree-sitter **0.25.2**, Java grammar **0.23.5**) with method wrapping.
  Syntax parsing is **not** compilation or dependency resolution.

### Executability: what exists versus what still needs doing

The corpus has exactly `target` and five `src_fm*` views, not a `src_class` or a
full buildable Java class. The richer record gives repository URL, class/file
names, method bodies/signatures/invocations, fields and other-method signatures.
For these candidates, neither class has a superclass or test instance fixture.

It does **not** supply original imports, an authoritative package declaration,
full helper-method bodies, a source revision/commit, POM/Gradle files, dependency
versions or an explicit JUnit version. The path suggests package
`com.webauthn4j.util`; that is an inference, not an extracted package declaration.
The `src_fm_fc_ms*` context strings include signature-only placeholders and even
repeated focal signatures; they are **not Java compilation units**.

All three reference methods use package-private `@Test void` style and AssertJ
`assertThat(...).isEqualTo(...)`, consistent with Jupiter rather than ordinary
JUnit 4 test-method rules. Missing imports/build metadata prevent pinning their
original JUnit/AssertJ versions. A raw `target` therefore cannot simply be sent
to the current Jupiter-only evaluator as a complete test class.

**Nothing was compiled or executed for these candidates.** Two legitimate next
preparation options, neither performed here:

1. **Recommended small bounded evaluation:** wrap the unchanged selected
   production methods in explicit minimal classes with JDK imports, version the
   extraction/package contract, and create private reference test-class controls.
   Either pin an existing reviewed AssertJ dependency or explicitly adapt the
   evaluator-only assertion to Jupiter and label it an adapted control. Preserve
   the ByteBuffer-reading method's public constant context. Use the existing shared
   Jupiter evaluator and require positive real test execution before generation.
   This is extracted-method evaluation, not an original-project build claim.
2. **Original-project evaluation:** obtain and pin the appropriate original
   source revision and project build/test dependencies. The dataset's URL/update
   timestamp is not a revision checkout recipe. A full repository checkout/build
   is unnecessary for the pure-method microharness, but necessary for stronger
   original-project claims.

Keep `target`/reference classes and expected outcomes evaluator-only, never in
new prompts or indexes. The owned ignored inspection shortlist containing gold
is private local audit material, not a prompt/training dataset. No candidate
manifest, dataset role or index was modified by this report.

## 5. Provenance, bounds and verification

Owned ignored evidence: `artifacts/dataset_unused_audit_20261112/`:
`inspection.py`, `inventory_report.json`, `supplement.py`,
`supplement_report.json`, `index_identity_inventory.json`,
`actual_rag_code_hashes.json`, `verify_candidates.py` and
`selected_candidate_verification.json`. The larger preliminary shortlist and
screening report are also ignored; do not commit their reference content.

Executed in WSL from repository root, using existing dependencies only:

~~~bash
PYTHONDONTWRITEBYTECODE=1 .venv_wsl/bin/python -B artifacts/dataset_unused_audit_20261112/inspection.py
PYTHONDONTWRITEBYTECODE=1 .venv_wsl/bin/python -B artifacts/dataset_unused_audit_20261112/supplement.py
PYTHONDONTWRITEBYTECODE=1 .venv_wsl/bin/python -B artifacts/dataset_unused_audit_20261112/verify_candidates.py
~~~

- Expanded Methods2Test enumeration visited only the configured corpus subtree,
  once; file sizes/counts/project IDs were streamed. No complete raw content hash
  or all-record code-deduplication claim is made.
- Rich official-test archive inspection read **4,000 JSON members**,
  **47,042,269 payload bytes**, below the declared **64 MiB / 4,000-member** cap;
  it stopped early, never extracted files, never decompressed the full archive.
  344 records passed the initial syntactic/content filter; the three above also
  passed manual dependency screening and focused exclusion/parse checks.
  Sixteen rich/corpus code mismatches were rejected, not silently reconciled.
- ML4Refactoring read only the outer ZIP central directory (11,151 entries),
  one project central directory (abdera, 7,934 entries), two small Java
  members (82/87 B), and the configured extracted-project directory's metadata.
  No 40 GB hash, global pair count,
  full-archive extraction or project execution was attempted.
- SQLite count query:

~~~sql
SELECT c.name, COUNT(e.id), c.dimension
FROM collections c
JOIN segments s ON s.collection = c.id
JOIN embeddings e ON e.segment_id = s.id
GROUP BY c.name;
~~~

  Metadata/document inspection joined `embedding_metadata.id = embeddings.id`;
  keys included `source_file`, `source`, `project`, input/focal hashes and
  `chroma:document`. Actual document sections were normalized with
  `ingestion.identity.normalize_java_for_hash` / `java_code_hash`, which remove
  comments and normalize token spacing without changing string literals.
- All **15 processed JSONL hashes** were rechecked after inspection. Protected
  user-file hashes and SQLite byte size/mtime were unchanged during the audit.
  This freezes observed snapshots; it does not establish historical train hashes.
- No full test suite was warranted for a documentation/read-only inventory task.
  The meaningful gates were counts/hashes, source/mixture comparisons, actual
  index content, reference inspection, syntax parsing and documentation checks.

### Key SHA-256 identities

| File | SHA-256 |
|---|---|
| `testing/train.jsonl` | `6a2ebc5d0dbbfd2f2dbc4b653a45ec9fdc4f9ae836da3a64f1f44e8d5f09b401` |
| `testing/val.jsonl` | `8e48b96d25041811cc7fb96e1f84401b816787640501840f9d1e38a8ffff7e1f` |
| `testing/test.jsonl` | `18dd06494f8ebc6fc26b6f330930637446d4f78aac2e10b36b581ade6a91be68` |
| Rich Methods2Test `dataset/test.tar.bz2`, 55,058,727 B | `f83c1840893cd54a723d3f6aa06065f63b2d564d3474dff6023f0f1f88e43876` |
| Candidate `134147639_39_corpus.json`, 1,042 B | `36c1df6f083d3c4b179a457043ebec48b2e8e40354613d1c2ecb95948920799c` |
| Candidate `134147639_28_corpus.json`, 2,857 B | `c94a1cd61026f077072a00d1327d2320ce40057142e3e2f8681203d33494ce28` |
| Candidate `134147639_15_corpus.json`, 2,309 B | `f1624f95f5cb99fa953e95f4c93663806c16799b7507db8d5122be4248d31f70` |
| MaRV raw JSON | `d2d8171d3f3c0d19d1bbfbf7d606add9369a74b2f23fd28d7ca14bf1ec224828` |
| SWE pure JSON | `69e1846e6f1624cb693262de2648c973470ee2ce8a753e38d1666f5d620c3fdc` |

Methods2Test checkout revision is `574b84b633eaaa0efb83afd80b29878a9537ed90`;
expanded corpus files are not thereby pinned to tracked Git bytes. Full candidate
rich-member and normalized production/reference hashes are retained in the
private selected verification JSON, along with all 15 processed-file identities
in the inventory report.

### Related evidence read

- [Earlier repository audit](../architecture/openclaw_repository_audit_2026-11-12.md)
- [User-owned dataset audit, read-only](data_audit_report.md)
- [Pinned SWE acquisition and harness limitations](swe_refactor_zenodo_acquisition_2026-11-12.md)
- [V2 training runbook](../finetuning/v2_runbook.md)
- [Completed three-case Defects4J pilot](../experiments/defects4j_three_case_full_class_v2.md)
- [Smoke dataset role](handcrafted_smoke.md)

**Bottom line:** use the already-local Methods2Test official test reserve for
new testing cases; retain SWE-Refactor as the existing refactoring reserve.
Prepare and validate a few clean executable wrappers first, without turning
that preparation into another model experiment or a claim that all raw records
are unseen/buildable.
