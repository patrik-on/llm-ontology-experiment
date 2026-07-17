from __future__ import annotations

import pytest

from llm_ontology.approaches import PromptRequest, RetrievedContext, available_approaches, get_approach
from llm_ontology.finetuning.prompt_formatter import format_inference_prompt as compatibility_prompt
from llm_ontology.inference.prompting import format_inference_prompt


def test_approach_registry_exposes_comparison_methods() -> None:
    assert available_approaches() == ("direct", "rag", "multi_rag")
    assert get_approach("multi-rag").name == "multi_rag"


def test_direct_approach_preserves_existing_prompt_format() -> None:
    request = PromptRequest(task="testing", instruction="Generate a test.", input_text="int add() { return 1; }")

    prepared = get_approach("direct").prepare_prompt(request)

    assert prepared.approach == "direct"
    assert prepared.contexts == ()
    assert prepared.text == format_inference_prompt(request.instruction, request.input_text)


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
    assert "untrusted reference examples" in prepared.text


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
