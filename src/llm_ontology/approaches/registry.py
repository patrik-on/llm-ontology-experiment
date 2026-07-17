from __future__ import annotations

from llm_ontology.approaches.contracts import GenerationApproach
from llm_ontology.approaches.direct import DirectApproach
from llm_ontology.approaches.multi_rag import MultiRagApproach
from llm_ontology.approaches.rag import RagApproach


_APPROACHES: dict[str, type[GenerationApproach]] = {
    "direct": DirectApproach,
    "rag": RagApproach,
    "multi_rag": MultiRagApproach,
}


def normalize_approach_name(name: str) -> str:
    return name.strip().lower().replace("-", "_")


def available_approaches() -> tuple[str, ...]:
    return tuple(_APPROACHES)


def get_approach(name: str) -> GenerationApproach:
    normalized = normalize_approach_name(name)
    try:
        approach_type = _APPROACHES[normalized]
    except KeyError as exc:
        available = ", ".join(available_approaches())
        raise ValueError(f"Unknown generation approach {name!r}. Available: {available}.") from exc
    return approach_type()
