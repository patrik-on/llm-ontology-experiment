from __future__ import annotations


def build_callbacks(config: dict) -> list[object]:
    callbacks: list[object] = []
    if config.get("training", {}).get("early_stopping"):
        try:
            from transformers import EarlyStoppingCallback
        except ImportError:
            return callbacks
        callbacks.append(EarlyStoppingCallback(early_stopping_patience=2))
    return callbacks
