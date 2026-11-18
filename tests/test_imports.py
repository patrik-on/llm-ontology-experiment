from __future__ import annotations

import importlib
import pkgutil

import llm_ontology


def test_all_llm_ontology_modules_import() -> None:
    failures = []
    for module in pkgutil.walk_packages(llm_ontology.__path__, llm_ontology.__name__ + "."):
        try:
            importlib.import_module(module.name)
        except Exception as exc:
            failures.append(f"{module.name}: {type(exc).__name__}: {exc}")

    assert not failures, "\n".join(failures)


def test_training_import_in_fresh_process():
    import subprocess
    import sys
    subprocess.run([sys.executable, "-c", "from llm_ontology.finetuning.training.finetuning import build_tokenized_training_example; from llm_ontology.approaches import ApproachPromptBuilder, get_approach; assert get_approach('direct').name == 'direct'"], check=True, timeout=30)
