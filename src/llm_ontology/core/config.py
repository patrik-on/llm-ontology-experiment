from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only in minimal runtimes.
    yaml = None


Config = dict[str, Any]


def deep_merge(base: Config, override: Config) -> Config:
    merged = deepcopy(base)
    for key, value in override.items():
        if key == "defaults":
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def read_yaml(path: str | Path) -> Config:
    with Path(path).open("r", encoding="utf-8") as handle:
        text = handle.read()
    if yaml is not None:
        return yaml.safe_load(text) or {}
    return _parse_simple_yaml(text)


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value.strip('"').strip("'")


def _strip_comment(line: str) -> str:
    quoted = False
    quote_char = ""
    for index, char in enumerate(line):
        if char in {"'", '"'}:
            if quoted and char == quote_char:
                quoted = False
            elif not quoted:
                quoted = True
                quote_char = char
        if char == "#" and not quoted:
            return line[:index]
    return line


def _parse_simple_yaml(text: str) -> Config:
    lines: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).rstrip()
        if not line.strip():
            continue
        lines.append((len(line) - len(line.lstrip(" ")), line.strip()))

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(lines):
            return {}, index
        is_list = lines[index][1].startswith("- ")
        if is_list:
            values = []
            while index < len(lines) and lines[index][0] == indent and lines[index][1].startswith("- "):
                values.append(_parse_scalar(lines[index][1][2:].strip()))
                index += 1
            return values, index

        values: dict[str, Any] = {}
        while index < len(lines) and lines[index][0] == indent and not lines[index][1].startswith("- "):
            key, _, raw_value = lines[index][1].partition(":")
            key = key.strip()
            raw_value = raw_value.strip()
            index += 1
            if raw_value:
                values[key] = _parse_scalar(raw_value)
            elif index < len(lines) and lines[index][0] > indent:
                values[key], index = parse_block(index, lines[index][0])
            else:
                values[key] = {}
        return values, index

    parsed, _ = parse_block(0, 0)
    return parsed if isinstance(parsed, dict) else {}


def load_config(config_path: str | Path) -> Config:
    path = Path(config_path)
    config = read_yaml(path)
    merged: Config = {}
    for default in config.get("defaults", []):
        default_path = (path.parent / default).resolve()
        merged = deep_merge(merged, read_yaml(default_path))
    return deep_merge(merged, config)


def require_keys(config: Config, keys: list[str]) -> None:
    missing = []
    for dotted_key in keys:
        current: Any = config
        for part in dotted_key.split("."):
            if not isinstance(current, dict) or part not in current:
                missing.append(dotted_key)
                break
            current = current[part]
    if missing:
        raise ValueError(f"Missing required config keys: {', '.join(missing)}")


def load_experiment_config(config_path: str | Path) -> Config:
    config = load_config(config_path)
    require_keys(
        config,
        [
            "experiment.name",
            "experiment.domain",
            "data.train_file",
            "data.val_file",
            "data.test_file",
            "output.adapter_dir",
            "output.checkpoint_dir",
            "output.result_dir",
        ],
    )
    return config
