from __future__ import annotations

import random
from typing import TypeVar


T = TypeVar("T")


def split_records(
    records: list[T],
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    seed: int = 42,
) -> tuple[list[T], list[T], list[T]]:
    if train_ratio <= 0 or val_ratio < 0 or train_ratio + val_ratio >= 1:
        raise ValueError("Expected 0 < train_ratio and train_ratio + val_ratio < 1.")
    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)
    train_end = int(len(shuffled) * train_ratio)
    val_end = train_end + int(len(shuffled) * val_ratio)
    return shuffled[:train_end], shuffled[train_end:val_end], shuffled[val_end:]


def combine_records(*groups: list[T]) -> list[T]:
    combined: list[T] = []
    for group in groups:
        combined.extend(group)
    return combined
