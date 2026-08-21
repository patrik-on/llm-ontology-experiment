from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from llm_ontology.retrieval.models import RetrievalHit


@runtime_checkable
class TokenCounter(Protocol):
    model_identifier: str
    model_revision: str | None
    method: str

    def count(self, text: str) -> int: ...

    def truncate(self, text: str, max_tokens: int) -> str: ...


class HuggingFaceTokenCounter:
    """Exact tokenizer-based counting with a pinned Hub revision."""

    method = "huggingface_tokenizer"

    def __init__(
        self,
        *,
        model_identifier: str,
        model_revision: str,
        trust_remote_code: bool = False,
    ) -> None:
        if not model_revision.strip():
            raise ValueError("A concrete tokenizer revision is required.")
        self.model_identifier = model_identifier
        self.model_revision = model_revision
        self.trust_remote_code = trust_remote_code
        self._tokenizer: Any | None = None

    def count(self, text: str) -> int:
        return len(self._load()(text, add_special_tokens=False)["input_ids"])

    def truncate(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""
        tokenizer = self._load()
        token_ids = tokenizer(text, add_special_tokens=False)["input_ids"][:max_tokens]
        return str(tokenizer.decode(token_ids, skip_special_tokens=True))

    def _load(self) -> Any:
        if self._tokenizer is None:
            try:
                from transformers import AutoTokenizer
            except ImportError as exc:  # pragma: no cover - optional dependency.
                raise RuntimeError("Transformers is required for exact token counting.") from exc
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_identifier,
                revision=self.model_revision,
                trust_remote_code=self.trust_remote_code,
            )
        return self._tokenizer


class CharacterTokenCounter:
    """Explicit deterministic fallback; never presented as exact tokenization."""

    method = "character_estimate_4_to_1"
    model_identifier = "character-estimate"
    model_revision = "1"

    def count(self, text: str) -> int:
        return max(1, (len(text) + 3) // 4) if text else 0

    def truncate(self, text: str, max_tokens: int) -> str:
        return text[: max(0, max_tokens) * 4]


@dataclass(frozen=True)
class _PairedEvidence:
    preamble: str
    input_heading: str
    input_text: str
    output_heading: str
    output_text: str

    def render(self, input_text: str, output_text: str) -> str:
        parts = [
            self.preamble.strip(),
            f"{self.input_heading}\n{input_text.strip()}".strip(),
            f"{self.output_heading}\n{output_text.strip()}".strip(),
        ]
        return "\n\n".join(part for part in parts if part)


class ContextSelection(BaseModel):
    model_config = ConfigDict(frozen=True)

    documents: list[RetrievalHit] = Field(default_factory=list)
    selected_document_ids: list[str] = Field(default_factory=list)
    dropped_document_ids: list[str] = Field(default_factory=list)
    truncated_document_ids: list[str] = Field(default_factory=list)
    pair_aware_truncated_document_ids: list[str] = Field(default_factory=list)
    fixed_prompt_tokens: int
    retrieval_tokens: int
    retrieval_token_budget: int | None = None
    max_document_tokens: int | None = None
    reserved_output_tokens: int
    safety_margin_tokens: int
    total_context_tokens: int
    tokenizer_model: str
    tokenizer_revision: str | None
    counting_method: str


class ContextBudgeter:
    def __init__(
        self,
        counter: TokenCounter,
        *,
        total_context_tokens: int,
        reserved_output_tokens: int,
        safety_margin_tokens: int = 256,
        retrieval_token_budget: int | None = None,
        max_document_tokens: int | None = None,
        allow_last_document_truncation: bool = True,
    ) -> None:
        if min(total_context_tokens, reserved_output_tokens, safety_margin_tokens) < 0:
            raise ValueError("Token budgets must not be negative.")
        if reserved_output_tokens + safety_margin_tokens >= total_context_tokens:
            raise ValueError("Output reserve and safety margin exhaust the context window.")
        if retrieval_token_budget is not None and retrieval_token_budget < 1:
            raise ValueError("Retrieval token budget must be positive.")
        if max_document_tokens is not None and max_document_tokens < 1:
            raise ValueError("Per-document token limit must be positive.")
        self.counter = counter
        self.total_context_tokens = total_context_tokens
        self.reserved_output_tokens = reserved_output_tokens
        self.safety_margin_tokens = safety_margin_tokens
        self.retrieval_token_budget = retrieval_token_budget
        self.max_document_tokens = max_document_tokens
        self.allow_last_document_truncation = allow_last_document_truncation

    def select(self, fixed_prompt_text: str, documents: list[RetrievalHit]) -> ContextSelection:
        fixed_tokens = self.counter.count(fixed_prompt_text)
        context_available = (
            self.total_context_tokens
            - self.reserved_output_tokens
            - self.safety_margin_tokens
            - fixed_tokens
        )
        if context_available < 0:
            raise ValueError(
                "Fixed prompt exceeds the input budget before retrieval context is added."
            )
        available = (
            context_available
            if self.retrieval_token_budget is None
            else min(context_available, self.retrieval_token_budget)
        )
        selected: list[RetrievalHit] = []
        dropped: list[str] = []
        truncated: list[str] = []
        pair_aware_truncated: list[str] = []
        used = 0
        for document in documents:
            candidate = document
            tokens = self.counter.count(candidate.content)
            limited_by_document_cap = False
            if self.max_document_tokens is not None and tokens > self.max_document_tokens:
                content, pair_aware = self._truncate_evidence(
                    candidate.content, self.max_document_tokens
                )
                if not content:
                    dropped.append(candidate.document_id)
                    continue
                candidate = candidate.model_copy(update={"content": content})
                tokens = self.counter.count(content)
                limited_by_document_cap = True
                if pair_aware:
                    pair_aware_truncated.append(candidate.document_id)
            remaining = available - used
            if tokens <= remaining:
                selected.append(candidate)
                if limited_by_document_cap:
                    truncated.append(candidate.document_id)
                used += tokens
                continue
            if self.allow_last_document_truncation and remaining > 0:
                content, pair_aware = self._truncate_evidence(candidate.content, remaining)
                if content:
                    actual = self.counter.count(content)
                    selected.append(candidate.model_copy(update={"content": content}))
                    truncated.append(candidate.document_id)
                    if pair_aware:
                        pair_aware_truncated.append(candidate.document_id)
                    used += actual
                    continue
            dropped.append(candidate.document_id)
        return ContextSelection(
            documents=selected,
            selected_document_ids=[document.document_id for document in selected],
            dropped_document_ids=dropped,
            truncated_document_ids=truncated,
            pair_aware_truncated_document_ids=list(dict.fromkeys(pair_aware_truncated)),
            fixed_prompt_tokens=fixed_tokens,
            retrieval_tokens=used,
            retrieval_token_budget=self.retrieval_token_budget,
            max_document_tokens=self.max_document_tokens,
            reserved_output_tokens=self.reserved_output_tokens,
            safety_margin_tokens=self.safety_margin_tokens,
            total_context_tokens=self.total_context_tokens,
            tokenizer_model=self.counter.model_identifier,
            tokenizer_revision=self.counter.model_revision,
            counting_method=self.counter.method,
        )

    def _truncate_evidence(self, content: str, max_tokens: int) -> tuple[str, bool]:
        paired = _parse_paired_evidence(content)
        if paired is None:
            return self.counter.truncate(content, max_tokens).strip(), False
        return self._truncate_pair(paired, max_tokens), True

    def _truncate_pair(self, pair: _PairedEvidence, max_tokens: int) -> str:
        skeleton = pair.render("", "")
        body_budget = max_tokens - self.counter.count(skeleton)
        if body_budget < 2:
            return ""

        input_tokens = self.counter.count(pair.input_text)
        output_tokens = self.counter.count(pair.output_text)
        input_budget = min(input_tokens, body_budget // 2)
        output_budget = min(output_tokens, body_budget - input_budget)

        remaining = body_budget - input_budget - output_budget
        input_extra = min(remaining, input_tokens - input_budget)
        input_budget += input_extra
        remaining -= input_extra
        output_budget += min(remaining, output_tokens - output_budget)

        if input_budget < 1 or output_budget < 1:
            return ""

        while True:
            input_text = self.counter.truncate(pair.input_text, input_budget).strip()
            output_text = self.counter.truncate(pair.output_text, output_budget).strip()
            if not input_text or not output_text:
                return ""
            compact = pair.render(input_text, output_text)
            if self.counter.count(compact) <= max_tokens:
                return compact
            if input_budget > 1 and (input_budget >= output_budget or output_budget == 1):
                input_budget -= 1
            elif output_budget > 1:
                output_budget -= 1
            else:
                return ""


def _parse_paired_evidence(content: str) -> _PairedEvidence | None:
    templates = (
        (
            "Original Java code:\n",
            "\n\nRefactored Java code:\n",
            "\n\nChange summary or diff:\n",
        ),
        (
            "Production Java code:\n",
            "\n\nCorresponding test code:\n",
            None,
        ),
    )
    for input_marker, output_marker, tail_marker in templates:
        preamble, marker, remainder = content.partition(input_marker)
        if not marker:
            continue
        input_text, marker, output_and_tail = remainder.partition(output_marker)
        if not marker:
            continue
        output_text = output_and_tail
        if tail_marker is not None:
            output_text = output_and_tail.partition(tail_marker)[0]
        input_text = input_text.strip()
        output_text = output_text.strip()
        if not input_text or not output_text:
            return None
        return _PairedEvidence(
            preamble=preamble,
            input_heading=input_marker.strip(),
            input_text=input_text,
            output_heading=output_marker.strip(),
            output_text=output_text,
        )
    return None
