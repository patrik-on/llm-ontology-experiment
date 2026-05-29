from llm_ontology.inference.prompts import build_prompt, build_training_text
from llm_ontology.finetuning.prompt_formatter import format_inference_prompt, format_training_prompt
from llm_ontology.training.finetuning import build_tokenized_training_example
from llm_ontology.evaluation.inference_eval import is_lora_model


class FakeTokenizer:
    eos_token = "<eos>"

    def __call__(
        self,
        text: str,
        truncation: bool = False,
        max_length: int | None = None,
        padding: bool = False,
        add_special_tokens: bool = False,
    ) -> dict[str, list[int]]:
        del padding, add_special_tokens
        input_ids = list(range(1, len(text) + 1))
        if truncation and max_length is not None:
            input_ids = input_ids[:max_length]
        return {"input_ids": input_ids, "attention_mask": [1] * len(input_ids)}


def test_build_prompt_and_training_text() -> None:
    record = {"instruction": "Do it.", "input": "code", "output": "answer", "domain": "testing"}

    prompt = build_prompt(record)
    training_text = build_training_text(record)

    assert "### Instruction:" in prompt
    assert "### Response:" in prompt
    assert training_text.endswith("answer")


def test_prompt_formatter_preserves_task_instruction() -> None:
    instruction = "Vygeneruj refaktorovanú verziu podľa typu refaktoringu: Rename Method."

    prompt = format_inference_prompt(instruction, "public void oldName() {}")

    assert instruction in prompt
    assert "Rename Method" in prompt
    assert prompt.endswith("### Response:\n")


def test_training_text_can_append_eos_token() -> None:
    record = {"instruction": "Do it.", "input": "code", "output": "answer"}

    training_text = format_training_prompt(record, eos_token="<eos>")

    assert training_text.endswith("answer<eos>")


def test_tokenized_training_example_masks_prompt_labels() -> None:
    record = {"instruction": "Do it.", "input": "code", "output": "answer"}
    tokenizer = FakeTokenizer()

    feature = build_tokenized_training_example(record, tokenizer, max_seq_length=10_000)

    assert feature is not None
    labels = feature["labels"]
    first_unmasked = next(index for index, label in enumerate(labels) if label != -100)
    assert all(label == -100 for label in labels[:first_unmasked])
    assert labels[first_unmasked:] == feature["input_ids"][first_unmasked:]


def test_tokenized_training_example_preserves_answer_labels_when_prompt_is_truncated() -> None:
    record = {"instruction": "Do it.", "input": "code", "output": "answer"}
    tokenizer = FakeTokenizer()
    prompt_length = len(format_inference_prompt(record["instruction"], record["input"]))

    feature = build_tokenized_training_example(record, tokenizer, max_seq_length=prompt_length)

    assert feature is not None
    labels = feature["labels"]
    assert labels[0] == -100
    assert any(label != -100 for label in labels)


def test_is_lora_model_ignores_baseline_adapter_sentinel() -> None:
    assert not is_lora_model({"type": "baseline", "adapter_path": None})
    assert not is_lora_model({"type": "baseline", "adapter_path": "baseline"})
    assert not is_lora_model({"type": "baseline", "adapter_path": "none"})
    assert is_lora_model({"type": "lora", "adapter_path": "/tmp/adapter"})
    assert is_lora_model({"type": "baseline", "adapter_path": "/tmp/adapter"})
