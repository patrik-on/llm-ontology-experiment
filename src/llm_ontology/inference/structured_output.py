from __future__ import annotations

import json
import re
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, Field, ValidationError

from llm_ontology.core.task_mode import CanonicalTask
from llm_ontology.providers.contracts import LLMProvider
from llm_ontology.retrieval.models import RetrievedEvidence


class RefactoringAnswer(BaseModel):
    task_type: Literal["refactoring"] = "refactoring"
    analysis_summary: str
    detected_code_smells: list[str] = Field(default_factory=list)
    recommended_refactorings: list[str] = Field(default_factory=list)
    refactored_code: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    retrieved_evidence: list[RetrievedEvidence] = Field(default_factory=list)


class TestingAnswer(BaseModel):
    task_type: Literal["testing"] = "testing"
    analysis_summary: str
    generated_tests: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    retrieved_evidence: list[RetrievedEvidence] = Field(default_factory=list)


class StructuredGenerationAttempt(BaseModel):
    attempt: int
    raw_response: str
    validation_errors: list[str] = Field(default_factory=list)


class StructuredGenerationResult(BaseModel):
    answer: RefactoringAnswer | TestingAnswer
    attempts: list[StructuredGenerationAttempt]


AnswerModel = TypeVar("AnswerModel", RefactoringAnswer, TestingAnswer)


class StructuredOutputGenerator:
    """Validate task-specific JSON and perform bounded format-only repairs."""

    def __init__(self, provider: LLMProvider, *, max_retries: int = 2) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must not be negative.")
        self.provider = provider
        self.max_retries = max_retries

    def generate(
        self,
        prompt: str,
        task: CanonicalTask,
    ) -> StructuredGenerationResult:
        model: type[RefactoringAnswer] | type[TestingAnswer]
        model = RefactoringAnswer if task == CanonicalTask.REFACTORING else TestingAnswer
        attempts: list[StructuredGenerationAttempt] = []
        current_prompt = prompt
        for attempt_number in range(1, self.max_retries + 2):
            raw = self._generate_with_schema(current_prompt, model.model_json_schema())
            try:
                answer = model.model_validate(_parse_json_object(raw))
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                errors = _validation_messages(exc)
                attempts.append(
                    StructuredGenerationAttempt(
                        attempt=attempt_number,
                        raw_response=raw,
                        validation_errors=errors,
                    )
                )
                if attempt_number > self.max_retries:
                    raise RuntimeError(
                        f"Structured output remained invalid after {attempt_number} attempts: "
                        + "; ".join(errors)
                    ) from exc
                current_prompt = _repair_prompt(raw, errors, model.model_json_schema())
                continue
            attempts.append(
                StructuredGenerationAttempt(attempt=attempt_number, raw_response=raw)
            )
            return StructuredGenerationResult(answer=answer, attempts=attempts)
        raise AssertionError("unreachable")

    def _generate_with_schema(self, prompt: str, schema: dict[str, Any]) -> str:
        generate_result = getattr(self.provider, "generate_result", None)
        if callable(generate_result):
            return str(generate_result(prompt, json_schema=schema).response)
        return self.provider.generate(prompt)


def _parse_json_object(raw: str) -> dict[str, Any]:
    value = raw.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        value = fence.group(1)
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("Structured response must be a JSON object.")
    return parsed


def _validation_messages(exc: Exception) -> list[str]:
    if isinstance(exc, ValidationError):
        return [
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        ]
    return [str(exc)]


def _repair_prompt(raw: str, errors: list[str], schema: dict[str, Any]) -> str:
    return (
        "Repair only the JSON structure and required fields. Do not add commentary or markdown.\n"
        f"Validation errors: {json.dumps(errors, ensure_ascii=False)}\n"
        f"Required JSON Schema: {json.dumps(schema, ensure_ascii=False, sort_keys=True)}\n"
        f"Invalid response: {raw}"
    )
