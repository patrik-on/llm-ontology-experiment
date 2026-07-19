from __future__ import annotations

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


class ContextSelection(BaseModel):
    model_config = ConfigDict(frozen=True)

    documents: list[RetrievalHit] = Field(default_factory=list)
    selected_document_ids: list[str] = Field(default_factory=list)
    dropped_document_ids: list[str] = Field(default_factory=list)
    truncated_document_ids: list[str] = Field(default_factory=list)
    fixed_prompt_tokens: int
    retrieval_tokens: int
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
        allow_last_document_truncation: bool = True,
    ) -> None:
        if min(total_context_tokens, reserved_output_tokens, safety_margin_tokens) < 0:
            raise ValueError("Token budgets must not be negative.")
        if reserved_output_tokens + safety_margin_tokens >= total_context_tokens:
            raise ValueError("Output reserve and safety margin exhaust the context window.")
        self.counter = counter
        self.total_context_tokens = total_context_tokens
        self.reserved_output_tokens = reserved_output_tokens
        self.safety_margin_tokens = safety_margin_tokens
        self.allow_last_document_truncation = allow_last_document_truncation

    def select(self, fixed_prompt_text: str, documents: list[RetrievalHit]) -> ContextSelection:
        fixed_tokens = self.counter.count(fixed_prompt_text)
        available = (
            self.total_context_tokens
            - self.reserved_output_tokens
            - self.safety_margin_tokens
            - fixed_tokens
        )
        if available < 0:
            raise ValueError(
                "Fixed prompt exceeds the input budget before retrieval context is added."
            )
        selected: list[RetrievalHit] = []
        dropped: list[str] = []
        truncated: list[str] = []
        used = 0
        for document in documents:
            tokens = self.counter.count(document.content)
            remaining = available - used
            if tokens <= remaining:
                selected.append(document)
                used += tokens
                continue
            if self.allow_last_document_truncation and remaining > 0:
                content = self.counter.truncate(document.content, remaining).strip()
                if content:
                    actual = self.counter.count(content)
                    selected.append(document.model_copy(update={"content": content}))
                    truncated.append(document.document_id)
                    used += actual
                    continue
            dropped.append(document.document_id)
        return ContextSelection(
            documents=selected,
            selected_document_ids=[document.document_id for document in selected],
            dropped_document_ids=dropped,
            truncated_document_ids=truncated,
            fixed_prompt_tokens=fixed_tokens,
            retrieval_tokens=used,
            reserved_output_tokens=self.reserved_output_tokens,
            safety_margin_tokens=self.safety_margin_tokens,
            total_context_tokens=self.total_context_tokens,
            tokenizer_model=self.counter.model_identifier,
            tokenizer_revision=self.counter.model_revision,
            counting_method=self.counter.method,
        )
