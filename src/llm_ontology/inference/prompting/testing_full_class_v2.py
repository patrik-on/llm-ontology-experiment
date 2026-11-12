"""Opt-in instruction overlay; frozen instruction/canonical templates stay unchanged."""
from __future__ import annotations

import hashlib
import json

from llm_ontology.inference.experiment_runner import ExperimentCase

PROFILE = "testing-full-class-v2"
PROTOCOL = "testing_format_validation_v2"

DEMO_PRODUCTION = """package demo.labels;
public final class Labels {
    private Labels() {}
    public static String bracket(String text) {
        if (text == null) throw new IllegalArgumentException("text");
        return "[" + text + "]";
    }
}
"""
DEMO_TEST = """package demo.labels;
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
"""

REQUIREMENTS = """Testing task profile: testing-full-class-v2 (opt-in).
This is executable test generation, not a code-completion or prose question.
The evaluator compiles your entire test source against already compiled production
classes and JUnit Jupiter 5.11.4 / Platform 1.11.4 on Java 11, then runs that class.
Write exactly ONE complete public JUnit 5 Jupiter test class with 2-4 meaningful
@Test methods and actual assertions about the supplied public production behavior.
Cover ordinary behavior and relevant boundaries/errors supported by visible code.
Include the correct package declaration and every required import. Put the test in
the production package, or explicitly import the production class by its supplied
fully qualified name. Call its real public methods with their exact signatures;
observe static versus instance access and only use visible public constructors.
Do not return a method snippet, partial class, ellipses, TODOs or placeholders.
Do not redefine, rewrite, subclass to replace, or include the production class.
Use only Java 11 standard library, JUnit Jupiter and the visible production API.
No JUnit 4, Mockito, invented helpers, unsupported APIs/dependencies, reflection,
files, network, external services, threads or processes. Do not disable tests.
Check package, FQN, imports, signatures, assertions, balanced braces and complete
class structure before answering; do not emit hidden reasoning or a self-check essay.
The demonstration below teaches the output format only. It is unrelated to INPUT.
Do not copy its subject or tests into the answer. Solve only the actual INPUT.
"""


def demo_answer() -> dict:
    return {"task_type": "testing", "analysis_summary": "Checks bracketing and null rejection.",
            "generated_tests": DEMO_TEST, "assumptions": [], "warnings": [],
            "retrieved_evidence": []}


def profile_instruction(focal_class: str, *, envelope: str) -> str:
    if envelope not in {"ft", "rag"}:
        raise ValueError("Expected ft or rag envelope.")
    demonstration = (DEMO_TEST if envelope == "ft" else
                     json.dumps(demo_answer(), ensure_ascii=False, indent=2))
    output = ("Return only the complete Java test source, without Markdown or commentary."
              if envelope == "ft" else
              "Return only the canonical testing JSON object. generated_tests contains the "
              "complete Java class as a JSON string; other schema fields remain required. "
              "Do not return bare Java outside JSON.")
    return (REQUIREMENTS + "\nDEMONSTRATION INPUT (not the target):\n" + DEMO_PRODUCTION
            + "\nDEMONSTRATION ANSWER:\n" + demonstration
            + "\nEND DEMONSTRATION.\nACTUAL TARGET FQN: " + focal_class
            + "\nAvailable production API, package and imports are in actual INPUT; "
              "do not infer other APIs from retrieved examples.\n" + output)


def apply_profile(case: ExperimentCase, *, envelope: str) -> ExperimentCase:
    if case.metadata.get("prompt_profile") not in {None, PROFILE}:
        raise ValueError("Conflicting prompt profile.")
    focal = case.structured_identity.get("class_name")
    if not focal:
        raise ValueError("Explicit target production FQN is required.")
    # Deliberately do not forward evaluator-only metadata, gold assertions or expected outputs.
    instruction = profile_instruction(focal, envelope=envelope)
    return case.model_copy(update={"instruction": instruction, "requirements": "",
        "metadata": {**case.metadata, "prompt_profile": PROFILE,
                     "profile_instruction_sha256": hashlib.sha256(instruction.encode()).hexdigest(),
                     "output_envelope": envelope}})


def profile_identity() -> dict:
    return {"prompt_profile": PROFILE, "requirements_sha256": _sha(REQUIREMENTS),
            "demo_production_sha256": _sha(DEMO_PRODUCTION), "demo_test_sha256": _sha(DEMO_TEST)}


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
