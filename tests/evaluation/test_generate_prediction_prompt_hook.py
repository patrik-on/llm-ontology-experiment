"""The prompt hook sees the exact string that was tokenized, before generation starts."""
from llm_ontology.evaluation.hf_inference import generate_prediction
from llm_ontology.inference.prompting.instruction import format_inference_prompt


class Row(list):
    @property
    def shape(self):
        return (len(self),)

    def __getitem__(self, index):
        item = list.__getitem__(self, index)
        return Row(item) if isinstance(index, slice) else item

    def new_ones(self, shape):
        return Row([1] * shape[-1])


def test_on_prompt_receives_the_tokenized_string_before_generate():
    events = []

    class Tokenizer:
        pad_token_id, eos_token_id = 0, 0

        def __call__(self, text, return_tensors=None):
            events.append(("tokenize", text))
            return {"input_ids": Row([5, 6, 7])}

        def decode(self, ids, skip_special_tokens=True):
            return "out"

    class Model:
        def generate(self, input_ids, attention_mask, **kwargs):
            events.append(("generate", None))
            return [Row([5, 6, 7, 9, 0])]

    generate_prediction(Model(), Tokenizer(), "refactoring", "Do X", "class A {}",
                        {"max_new_tokens": 8}, on_prompt=lambda p: events.append(("charge", p)))
    prompt = format_inference_prompt("Do X", "class A {}")
    assert events == [("tokenize", prompt), ("charge", prompt), ("generate", None)]
