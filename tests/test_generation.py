from llm_ontology.inference.prompts import build_prompt, build_training_text


def test_build_prompt_and_training_text() -> None:
    record = {"instruction": "Do it.", "input": "code", "output": "answer", "domain": "testing"}

    prompt = build_prompt(record)
    training_text = build_training_text(record)

    assert "### Instruction:" in prompt
    assert "### Response:" in prompt
    assert training_text.endswith("answer")
