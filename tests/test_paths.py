from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_ontology.core.config import read_yaml
from llm_ontology.core.paths import expand_placeholders, work_root_path

REPO = Path(__file__).resolve().parents[1]


def test_expands_only_project_placeholders(monkeypatch):
    monkeypatch.setenv("LLM_ONTOLOGY_WORK_ROOT", "/opt/work/")
    data = {"a": "${LLM_ONTOLOGY_WORK_ROOT}/deps", "b": ["$HOME", "${OTHER}", 3], "c": "x"}
    assert expand_placeholders(data) == {"a": "/opt/work/deps", "b": ["$HOME", "${OTHER}", 3], "c": "x"}
    assert work_root_path("downloads") == Path("/opt/work/downloads")


def test_unknown_project_placeholder_fails_loudly():
    with pytest.raises(KeyError):
        expand_placeholders("${LLM_ONTOLOGY_TYPO}/x")


def test_defaults_reproduce_original_wsl_paths(monkeypatch):
    for name in ("LLM_ONTOLOGY_WORK_ROOT", "LLM_ONTOLOGY_MODELS_ROOT", "LLM_ONTOLOGY_DATASETS_ROOT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", "/home/patrik")
    runtime = read_yaml(REPO / "configs/benchmarks/java_evaluation_runtime_v1.yaml")
    assert runtime["java_home"] == "/home/patrik/benchmark-work/deps/jdk-11.0.33+10"
    plan = expand_placeholders(json.loads((REPO / "configs/benchmarks/refactoring_matrix_v1.json").read_text()))
    assert plan["raw_ml4refactoring"] == "/mnt/c/datasets/ml4refactoring/all/dataset"
    assert plan["cache"] == "/home/patrik/benchmark-work/refactoring-matrix/git"
    model = read_yaml(REPO / "configs/shared/models/qwen25_coder_7b_hf.yaml")
    assert model["model"]["name"] == "/mnt/c/models/huggingface/Qwen2.5-Coder-7B-Instruct"


def test_configs_contain_no_machine_specific_absolute_paths():
    offenders = []
    for path in (REPO / "configs").rglob("*"):
        if path.suffix in {".json", ".yaml", ".yml"}:
            text = path.read_text(encoding="utf-8")
            if "/home/patrik" in text or "/mnt/c/" in text:
                offenders.append(str(path.relative_to(REPO)))
    assert not offenders, offenders
