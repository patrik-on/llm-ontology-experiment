from __future__ import annotations

import hashlib
from typing import Any, Iterable

from llm_ontology.approaches import RetrievedContext
from llm_ontology.benchmarks.smoke import SmokeCase
from llm_ontology.inference.prompting import (
    EVIDENCE_PLACEHOLDER,
    CanonicalPromptBuilder,
    normalize_retrieved_evidence,
)


def audit_prompt_fairness(
    cases: Iterable[SmokeCase],
    *,
    builder: CanonicalPromptBuilder | None = None,
) -> dict[str, Any]:
    prompt_builder = builder or CanonicalPromptBuilder()
    comparisons: list[dict[str, Any]] = []
    for case in cases:
        project_context = _project_context(case)
        common = {
            "task": case.task,
            "instruction": "",
            "input_text": case.input.source_code,
            "requirements": case.input.requirements,
            "project_context": project_context,
        }
        prompts = {
            "no_rag": prompt_builder.build(**common, approach="direct"),
            "single_collection_rag": prompt_builder.build(
                **common,
                approach="rag",
                contexts=(
                    RetrievedContext(
                        "fairness:single",
                        "Synthetic evidence used only for prompt-structure auditing.",
                        source="mixed",
                        metadata={"collection": "mixed"},
                    ),
                ),
            ),
            "multi_collection_rag": prompt_builder.build(
                **common,
                approach="multi_rag",
                contexts=(
                    RetrievedContext(
                        "fairness:testing",
                        "Synthetic testing evidence used only for prompt-structure auditing.",
                        source="testing",
                        metadata={"collection": "testing_db"},
                    ),
                    RetrievedContext(
                        "fairness:refactoring",
                        "Synthetic refactoring evidence used only for prompt-structure auditing.",
                        source="refactoring",
                        metadata={"collection": "refactoring_db"},
                    ),
                ),
            ),
        }
        normalized_texts = {
            mode: normalize_retrieved_evidence(prompt.text)
            for mode, prompt in prompts.items()
        }
        normalized_hashes = {
            mode: _sha256(text) for mode, text in normalized_texts.items()
        }
        template_hashes = {
            mode: prompt.prompt_template_sha256 for mode, prompt in prompts.items()
        }
        stored_normalized_hashes = {
            mode: prompt.normalized_prompt_sha256 for mode, prompt in prompts.items()
        }
        passed = (
            len(set(normalized_texts.values())) == 1
            and len(set(normalized_hashes.values())) == 1
            and len(set(template_hashes.values())) == 1
            and normalized_hashes == stored_normalized_hashes
            and all(EVIDENCE_PLACEHOLDER in text for text in normalized_texts.values())
        )
        comparisons.append(
            {
                "case_id": case.id,
                "task": case.task,
                "passed": passed,
                "prompt_template_version": next(iter(prompts.values())).prompt_template_version,
                "prompt_template_sha256": template_hashes,
                "normalized_prompt_sha256": normalized_hashes,
                "full_prompt_sha256": {
                    mode: prompt.full_prompt_sha256 for mode, prompt in prompts.items()
                },
            }
        )
    return {
        "passed": bool(comparisons) and all(item["passed"] for item in comparisons),
        "cases_checked": len(comparisons),
        "modes": ["no_rag", "single_collection_rag", "multi_collection_rag"],
        "normalization_placeholder": EVIDENCE_PLACEHOLDER,
        "comparisons": comparisons,
    }


def smoke_project_context(case: SmokeCase) -> str:
    return _project_context(case)


def _project_context(case: SmokeCase) -> str:
    parts = [
        f"Java class: {case.input.class_name}",
        f"Focal method: {case.input.focal_method}",
    ]
    package_name = getattr(case.input, "package_name", "")
    if package_name:
        parts.append(f"Package: {package_name}")
    test_framework = getattr(case.input, "test_framework", "")
    if test_framework:
        parts.append(f"Test framework: {test_framework}")
    imports = getattr(case.input, "imports", [])
    if imports:
        parts.append("Declared imports: " + ", ".join(imports))
    return "\n".join(parts)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
