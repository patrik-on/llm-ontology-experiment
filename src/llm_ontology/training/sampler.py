from __future__ import annotations

import random
from collections import defaultdict
from typing import Any


def balanced_domain_sample(records: list[dict[str, Any]], seed: int = 42) -> list[dict[str, Any]]:
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_domain[str(record.get("domain", "unknown"))].append(record)
    if len(by_domain) <= 1:
        return list(records)
    size = min(len(group) for group in by_domain.values())
    rng = random.Random(seed)
    sampled: list[dict[str, Any]] = []
    for group in by_domain.values():
        sampled.extend(rng.sample(group, size))
    rng.shuffle(sampled)
    return sampled
