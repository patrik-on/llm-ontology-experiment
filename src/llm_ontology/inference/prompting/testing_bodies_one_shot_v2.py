"""One unrelated solved BODY example; v1 contract/scaffold/assembly are unchanged."""
from __future__ import annotations

from dataclasses import replace
import json

from llm_ontology.inference.experiment_runner import ExperimentCase
from llm_ontology.inference.prompting import testing_bodies_v1 as v1
from llm_ontology.inference.prompting.testing_full_class_v2 import DEMO_PRODUCTION
from llm_ontology.inference.structured_output import parse_testing_bodies

PROFILE = "testing-bodies-one-shot-v2"
DEMO_CASE = ExperimentCase(case_id="synthetic-labels-body-demo", instruction=v1.CONTRACT,
    input_text=DEMO_PRODUCTION, structured_identity={"class_name": "demo.labels.Labels", "method_name": "bracket"})
DEMO_SCAFFOLD = v1.scaffold(DEMO_CASE)
DEMO_JSON = json.dumps({
    "testCase1": 'assertEquals("[oak]", Labels.bracket("oak"));\nassertEquals("[]", Labels.bracket(""));',
    "testCase2": 'assertThrows(IllegalArgumentException.class, () -> Labels.bracket(null));',
}, ensure_ascii=False, separators=(",", ":"))
DEMO_BLOCK = (
    "\nBEGIN UNRELATED SOLVED BODY DEMONSTRATION\n"
    "This synthetic example illustrates the same two-body JSON contract for another API, not INPUT. "
    "Do not copy its subject or answers; choose the actual target's inputs and assertions yourself.\n"
    "DEMONSTRATION PRODUCTION:\n" + DEMO_PRODUCTION
    + "DEMONSTRATION EMPTY SCAFFOLD:\n" + DEMO_SCAFFOLD
    + "DEMONSTRATION ANSWER (exact strict JSON):\n" + DEMO_JSON
    + "\nEND UNRELATED SOLVED BODY DEMONSTRATION"
)


def demo_source():
    return v1.assemble(DEMO_SCAFFOLD, parse_testing_bodies(DEMO_JSON))


def apply_profile(case):
    result = v1.apply_profile(case)
    return result.model_copy(update={"instruction": result.instruction + DEMO_BLOCK,
        "metadata": {**result.metadata, "prompt_profile": PROFILE, "demo_sha256": v1.sha(DEMO_BLOCK)}})


class BodyPromptBuilder(v1.BodyPromptBuilder):
    def build(self, **kwargs):
        return replace(super().build(**kwargs), prompt_template_version=PROFILE)
