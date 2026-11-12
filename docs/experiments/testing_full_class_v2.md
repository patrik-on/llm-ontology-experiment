# Opt-in complete-class testing prompt v2

Profile: **testing-full-class-v2**. Protocol: **testing_format_validation_v2**.
No training/retraining, index rebuild, downloads, paid calls or full benchmark.
This composes the existing local FT loader/generate_prediction, RagExperimentRunner,
canonical JSON schema/retrieval and evaluate_revision compiler/Jupiter evaluator.
No new client, retrieval engine or generic evaluation pipeline. No silent default
switch: frozen instruction-v1, canonical-se-prompt-v2 and historical runs remain intact.

## Prompt delta

The case instruction now explains that the entire generated class is compiled and
executed against existing production binaries on Java 11 + pinned Jupiter. It names
the production FQN and requires a complete public test class, correct package/imports,
2–4 meaningful tests, actual assertions, exact visible public signatures/static access,
no snippets/ellipses/placeholders, no production rewrite or unavailable APIs/dependencies.
A short compile-oriented self-check is requested, not hidden reasoning.

Both systems receive the same requirements and small synthetic **demo.labels.Labels**
production example: bracket("oak") yields "[oak]", empty text yields "[]", null throws
IllegalArgumentException. The full correct LabelsTest is in
src/llm_ontology/inference/prompting/testing_full_class_v2.py (DEMO_PRODUCTION,
DEMO_TEST). FT shows that Java class directly and asks for raw Java in instruction-v1;
RAG shows the same class inside a full canonical testing JSON example and asks for JSON,
with Java only in generated_tests. There is no Java-only-vs-JSON contradiction.
Single/MultiRAG use the identical instruction; only retrieved evidence differs.

Exact demonstration production source:

~~~java
package demo.labels;
public final class Labels {
    private Labels() {}
    public static String bracket(String text) {
        if (text == null) throw new IllegalArgumentException("text");
        return "[" + text + "]";
    }
}
~~~

Exact Java demonstration answer (the RAG JSON wraps this as generated_tests):

~~~java
package demo.labels;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

public class LabelsTest {
    @Test void bracketsTextAndEmptyText() {
        assertEquals("[oak]", Labels.bracket("oak"));
        assertEquals("[]", Labels.bracket(""));
    }
    @Test void rejectsNull() {
        assertThrows(IllegalArgumentException.class, () -> Labels.bracket(null));
    }
}
~~~

This is a **systems comparison**, not an isolated fine-tuning ablation: HF + local PEFT
adapter/NF4/instruction rendering differs from Ollama quantization/instruct rendering.
The adapter itself is unchanged. Better prompting does not require retraining.

## Independent fixture and leakage boundary

The single new validation fixture is **validation.batches.BatchSizer.groupsNeeded**
under data/validation/testing_full_class_v2/. It is independent of the demonstration,
Defects4J, smoke, training and retrieval datasets. Its DatasetManifest has role
validation, allowed_for_indexing=false. It is format/protocol validation, **not a
scientific benchmark**. Gold control assertions stay evaluator-only, outside case,
prompt and retrieval query. Only the visible production class is the actual input.
No reference tests, patches, trigger inputs or expected Defects4J values enter prompts.
Existing index lineage/contamination remains unknown and unchanged; retrieval traces,
queries, manifest snapshots and selected evidence remain available for inspection.

## Bounded execution

Only one fixture × ft_testing/rag_single/rag_multi: **at most three new local calls**,
4096 output tokens equally, seed 42, greedy/temperature 0, no retries/repair. Per-arm
attempt directories are exclusive, including failures. Invalid JSON, truncation,
compilation failures and zero effective tests remain failed attempts in the denominator.
Acceptance requires compilation, 2–4 executed passing tests, and nontruncated EOS/stop.
No bug-detection metric is invented for a fixture with no buggy revision.

Preparation compiles the tiny demo and fixture with the already pinned Java/Jupiter
assets, checks the demo and evaluator-only fixture assertions, and minimal empty/
assertion-negative controls. It does not checkout/build/reprovision Defects4J or rerun
its full reference controls. The new runner binds code/config/toolchain/fixture hashes;
resumes reject changed source or production binaries. Exact prompts, schema, raw
responses, source, compilation/execution logs/XML, token counts and finish reason,
model/adapter/index identities are retained in a fresh canonical run directory.

Generated source must be reviewed before evaluate --reviewed-local-execution. The
existing local diagnostic process/resource guards are reused. **No OS sandbox**:
filesystem/network isolation and whole-process-tree containment are not claimed.

~~~bash
source .venv_wsl/bin/activate
python -m llm_ontology.benchmarks.testing_format_validation prepare --run-id format-v2-20261112 --reviewed-local-execution
python -m llm_ontology.benchmarks.testing_format_validation generate --run-id format-v2-20261112 --arm ft_testing --diagnostic
# Review predictions/ft_testing/generated.java, then:
python -m llm_ontology.benchmarks.testing_format_validation evaluate --run-id format-v2-20261112 --arm ft_testing --reviewed-local-execution
# Same generate/review/evaluate once each for rag_single and rag_multi (no retries).
python -m llm_ontology.benchmarks.testing_format_validation report --run-id format-v2-20261112
~~~

## Actual bounded sample (2026-11-12)

Artifacts: artifacts/evaluation/runs/**format-v2-20261112**/.
Exactly **1 fixture × 3 arms = 3 local generation calls**, no retries or output edits.
All three outputs were complete packaged public Jupiter classes, compiled successfully,
executed nonempty tests, and ended without output truncation. RAG JSON validated.

| Arm | Executed | Passing / failing | Outcome |
|---|---:|---:|---|
| FT b2_testing_v2 | 9 | 8 / 1 | assertion_failure: incorrectly expects zero items to throw; also exceeds requested 2–4 tests |
| Single RAG V3 | 4 | 3 / 1 | assertion_failure: expects groupsNeeded(5,2)=1, actual correct result is 3 |
| MultiRAG V3 | 5 | 5 / 0 | behavior execution passes, but exceeds requested 2–4 tests |

Thus executable-format/compilation checks pass **3/3** on this fixture; complete
semantic-class pass **1/3**. Strict acceptance including the modest 2–4-test contract
is **0/3**, not 1/3. These are descriptive sample counts, not benchmark rates or
real-bug detection. No failures were repaired, removed or relabeled.

Observed input/output tokens and finish reason:
- FT: **683 / 307**, eos.
- Single RAG: **2282 / 299**, stop.
- MultiRAG: **5163 / 252**, stop.

Both RAG arms retain the same normalized prompt SHA-256
f1bac2dad97ea4daabdf52d9fb70e2a1d96fc0a741e57e864521f8bfa5764efe.
Exact prompt hashes are in testing_full_class_v2_results.json. Their estimated final
prompt lengths were 2253/5134 versus runtime 2282/5163; no prompt budget exceeded,
no suspected prompt truncation, no retrieved-document truncation. Each used three
selected existing-index documents; the query contains only the production fixture
and public identity, not the demonstration or gold controls. Retrieved examples
were mostly only weakly related grouping/capacity code (Single) and mixed evidence
(Multi); these inputs/outcomes do not establish better retrieval quality.

FT uses unchanged local Qwen2.5-Coder-7B-Instruct + b2_testing_v2 adapter, adapter
SHA-256 82259c6862f1fd3b042fd9ca9459abe03f202227317e0e075f8b860e60000c2f.
RAG generation digest remains
dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364;
embedding digest remains
7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab.
Full model shard/config/tokenizer hashes, adapter lineage, Ollama template/quantization,
index manifest snapshots and effective seed/settings are in the run artifacts.

The compiled demonstration passes 2/2 tests; the separate evaluator-only fixture
control passes 2/2. Minimal empty-class and assertion-negative controls were rejected
as no_tests/assertion_failure respectively, using only the existing toolchain.
Artifact inspection verifies source hashes unchanged, actual prompts free of the
fixture gold control/Defects4J focal target, JSON source extraction, nonempty execution,
no truncation, and Single/Multi normalized-prompt parity.

Fresh verification only (small scope requested):
~~~bash
pytest -q tests/experiments/test_testing_full_class_v2.py tests/inference/test_ollama_client.py
# 15 passed, 1 harmless Pydantic-class collection warning
ruff check .
python -m compileall -q src
git diff --check
~~~
No full pytest suite or benchmark was rerun. The **225 passed / 3 skipped** full-suite
result in the earlier final-QA report belongs to the previous revision, not this one.

**Ready:** opt-in prompt composition, demo compilation and bounded local diagnostics.
**Not ready:** claiming improvement, reliable semantic correctness/strict instruction
compliance, or scientific benchmarking. Recommended next: keep this profile opt-in
and inspect assertion derivation plus weakly relevant retrieval evidence before any
separately authorized, same-case baseline comparison. Do not automatically retrain.

## Interpretation

Earlier Lang-24 failures are explored historical diagnostics on a **different case and
profile**, not a same-case baseline. A pass here would establish only successful
format/behavior execution on this tiny new fixture, not causal improvement or a final
benchmark score. No extra baseline call is authorized by this validation protocol.
A clean preregistered independent benchmark and stronger execution isolation remain
future readiness gates. Next steps should be based on these bounded actual outcomes;
there is no automatic retraining or full benchmark follow-up.
