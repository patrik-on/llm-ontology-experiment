from __future__ import annotations

from llm_ontology.approaches import ApproachPromptBuilder, RetrievedContext
from llm_ontology.benchmarks.smoke import load_smoke_cases
from llm_ontology.experiments.fairness import audit_prompt_fairness
from llm_ontology.inference.prompting import normalize_retrieved_evidence


def test_canonical_prompt_differs_only_in_retrieved_evidence() -> None:
    builder = ApproachPromptBuilder()
    common = {
        "task": "testing",
        "instruction": "Cover the focal method.",
        "input_text": "class A { int add(int a, int b) { return a + b; } }",
        "requirements": "Use JUnit 5.",
        "project_context": "No build metadata is available.",
    }
    direct = builder.build(**common, approach="direct")
    rag = builder.build(
        **common,
        approach="rag",
        contexts=(RetrievedContext("one", "Example", source="mixed"),),
    )
    multi = builder.build(
        **common,
        approach="multi_rag",
        contexts=(
            RetrievedContext("one", "Testing example", source="testing"),
            RetrievedContext("two", "Refactoring example", source="refactoring"),
        ),
    )

    assert normalize_retrieved_evidence(direct.text) == normalize_retrieved_evidence(rag.text)
    assert normalize_retrieved_evidence(rag.text) == normalize_retrieved_evidence(multi.text)
    assert len({item.prompt_template_sha256 for item in (direct, rag, multi)}) == 1
    assert len({item.normalized_prompt_sha256 for item in (direct, rag, multi)}) == 1
    assert len({item.full_prompt_sha256 for item in (direct, rag, multi)}) == 3


def test_all_smoke_cases_pass_prompt_fairness_audit() -> None:
    audit = audit_prompt_fairness(load_smoke_cases())

    assert audit["passed"] is True
    assert audit["cases_checked"] == 24
    assert all(item["passed"] for item in audit["comparisons"])
