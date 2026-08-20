"""Smoke-test Single RAG and MultiRAG through the shared UI service."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm_ontology.evaluation.experiment_log import JsonlExperimentWriter
from llm_ontology.ui.service import _record_to_view, create_ui_service


CASES = {
    "testing": {
        "task_label": "Testing",
        "source_code": (
            "public int divide(int left, int right) { "
            "if (right == 0) throw new IllegalArgumentException(); "
            "return left / right; }"
        ),
        "requirements": "Generate concise JUnit 5 happy-path and zero-divisor tests.",
    },
    "refactoring": {
        "task_label": "Refactoring",
        "source_code": (
            "public int sumPositive(int[] values) { int total = 0; "
            "for (int value : values) { if (value > 0) total += value; } "
            "return total; }"
        ),
        "requirements": "Improve readability without changing behavior.",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-history", action="store_true")
    args = parser.parse_args()
    service = create_ui_service()
    results = []
    if args.from_history:
        records = JsonlExperimentWriter(
            service.settings.history_path
        ).read_all()[-4:]
        if len(records) != 4:
            raise RuntimeError("Expected four recent UI smoke records.")
        results = [
            _result(
                record.canonical_task,
                "MultiRAG"
                if record.retrieval_mode == "multi_collection_rag"
                else "RAG",
                _record_to_view(record),
            )
            for record in records
        ]
        return _write_results(results)
    for task, case in CASES.items():
        for mode in ("RAG", "MultiRAG"):
            view = service.run(
                task_label=case["task_label"],
                mode_label=mode,
                source_code=case["source_code"],
                requirements=case["requirements"],
                top_k=5,
                log_level="INFO",
            )
            result = _result(task, mode, view)
            results.append(result)
            if not view.success or not view.output.code.strip():
                output = Path("artifacts/smoke/ui_rag_modes.json")
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps(results, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                raise RuntimeError(
                    f"UI smoke failed for task={task}, mode={mode}: {view.error}"
                )
    return _write_results(results)


def _result(task: str, mode: str, view):
    return {
        "task": task,
        "mode": mode,
        "success": view.success,
        "run_id": view.run_id,
        "error": view.error,
        "retrieval_message": view.retrieval_message,
        "retrieved": [
            document.model_dump(exclude={"content"}, mode="json")
            for document in view.retrieval_documents
        ],
        "fusion_trace": view.fusion_trace,
        "prompt": view.prompt.model_dump(exclude={"final_prompt"}, mode="json"),
        "metrics": view.metrics.values,
        "generated_code_present": bool(view.output.code.strip()),
    }


def _write_results(results: list[dict]) -> int:
    output = Path("artifacts/smoke/ui_rag_modes.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
