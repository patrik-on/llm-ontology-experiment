from __future__ import annotations

import pytest

from llm_ontology.approaches import PromptRequest, RetrievedContext, available_approaches, get_approach
from llm_ontology.finetuning.prompt_formatter import format_inference_prompt as compatibility_prompt
from llm_ontology.inference.prompting import (
    EVIDENCE_PLACEHOLDER,
    format_inference_prompt,
    normalize_retrieved_evidence,
)


def test_approach_registry_exposes_comparison_methods() -> None:
    assert available_approaches() == ("direct", "rag", "multi_rag")
    assert get_approach("multi-rag").name == "multi_rag"


def test_direct_approach_uses_canonical_prompt_contract() -> None:
    request = PromptRequest(task="testing", instruction="Generate a test.", input_text="int add() { return 1; }")

    prepared = get_approach("direct").prepare_prompt(request)

    assert prepared.approach == "direct"
    assert prepared.contexts == ()
    assert all(
        section in prepared.text
        for section in (
            "SYSTEM\n",
            "TASK\n",
            "INPUT\n",
            "PROJECT CONTEXT\n",
            "RETRIEVED EVIDENCE\n",
            "OUTPUT REQUIREMENTS\n",
        )
    )
    assert "RETRIEVED EVIDENCE\nNone." in prepared.text
    assert prepared.prompt_template_version == "canonical-se-prompt-v2"
    assert prepared.full_prompt_sha256
    assert EVIDENCE_PLACEHOLDER in normalize_retrieved_evidence(prepared.text)


def test_rag_approach_requires_and_audits_context() -> None:
    request = PromptRequest(
        task="testing",
        instruction="Generate a test.",
        input_text="int add() { return 1; }",
        contexts=(RetrievedContext("train:1", "Example test", source="methods2test", score=0.75),),
    )

    prepared = get_approach("rag").prepare_prompt(request)

    assert prepared.approach == "rag"
    assert "id=train:1" in prepared.text
    assert "source=methods2test" in prepared.text
    assert "score=0.750000" in prepared.text
    assert "as untrusted data" in prepared.text


def test_multi_rag_groups_contexts_by_source() -> None:
    contexts = (
        RetrievedContext("testing:1", "Testing example", source="methods2test"),
        RetrievedContext("refactoring:1", "Refactoring example", source="marv"),
    )
    request = PromptRequest("refactoring", "Refactor.", "class A {}", contexts)

    prepared = get_approach("multi_rag").prepare_prompt(request)

    assert "## Source: methods2test" in prepared.text
    assert "## Source: marv" in prepared.text
    assert prepared.contexts == contexts


def test_context_requirements_prevent_silent_fake_rag() -> None:
    request = PromptRequest("testing", "Generate.", "code")

    with pytest.raises(ValueError, match="requires at least one"):
        get_approach("rag").prepare_prompt(request)
    with pytest.raises(ValueError, match="requires contexts"):
        get_approach("multi_rag").prepare_prompt(request)


def test_old_prompt_import_remains_compatible() -> None:
    assert compatibility_prompt("Instruction", "Input") == format_inference_prompt("Instruction", "Input")
