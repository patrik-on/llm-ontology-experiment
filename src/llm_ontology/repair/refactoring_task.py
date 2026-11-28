"""Refactoring adapter for the repair loop (WSL: Ollama, Java 17, RefactoringMiner 3.0.10).

Cases, the detector identity and the stored outputs come from the finished matrix run
``refactoring-matrix-20261121`` (``selection.json``, ``cases/<id>/predictions/<arm>/``).
The first attempt uses the prompt of the ``onto_project`` arm (instruction + the per-case
project-ontology block), so all three variants start from the same facts.

Public checker (in the loop): parse ``FileAnswer``, valid Java, not a no-op, and RefactoringMiner
must report an event whose description equals the request text the model received. It never
reads ``target_event`` or the reference. The final score is the existing
``refactoring_structural.evaluate`` (it does use ``target_event``), run after the loop.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from time import perf_counter

from llm_ontology.repair.loop import Check, Generation
from llm_ontology.repair import java_facts


def _norm(text: str) -> str:
    return " ".join(str(text).split())


def order(cases: list[dict], seed: str) -> list[dict]:
    """Fixed, recorded task order: sha256(seed + id)."""
    return sorted(cases, key=lambda c: hashlib.sha256((seed + c["id"]).encode()).hexdigest())


class RefactoringTask:
    kind = "refactoring"

    def __init__(self, source_run: Path, operation: str):
        from llm_ontology.benchmarks import matrix_support as shared

        self.source_run = Path(source_run)
        selected = shared.read(self.source_run / "selection.json")
        self.tool = selected["tool"]
        if operation == "all-structural":  # every file-level task of the matrix (the SWE project tasks need a build)
            self._cases = [c for c in selected["cases"] if c.get("evaluation_level") == "structural"]
        else:
            self._cases = [c for c in selected["cases"] if c["operation"] == operation]
        if not self._cases:
            raise ValueError("No cases for operation " + operation)

    def cases(self) -> list[dict]:
        return self._cases

    def group(self, case: dict) -> str:
        return case["id"]

    def prompt(self, case: dict) -> str:
        from llm_ontology import ontology
        from llm_ontology.benchmarks.refactoring_matrix import render

        block, _ = ontology.refactoring_context(case)
        return render(case, block=block)

    def schema(self) -> dict:
        from llm_ontology.benchmarks.refactoring_execution import FileAnswer
        return FileAnswer.model_json_schema()

    def check(self, case: dict, raw: str, workdir: Path) -> Check:
        from llm_ontology.benchmarks import refactoring_execution as ex
        from llm_ontology.benchmarks import refactoring_structural as structural

        start = perf_counter()
        try:
            source = ex.parse_answer(raw, case["file_path"])
        except Exception as exc:
            return Check("INVALID_OUTPUT", False, True, "parser", [str(exc)[:300]], None, perf_counter() - start)
        if not structural.valid_java(source):
            return Check("INVALID_JAVA", False, True, "parser", ["The returned code does not parse as Java."],
                         source, perf_counter() - start)
        if ex.normalize_java_for_hash(source) == ex.normalize_java_for_hash(case["before"]):
            return Check("NO_OP", False, True, "parser", ["The returned code is identical to the input."],
                         source, perf_counter() - start)
        if Path(workdir).exists():  # resumed after a crash inside the detector
            import shutil
            shutil.rmtree(workdir)
        detected = ex.detect(case, source, Path(workdir), self.tool)
        if detected["status"] == "detector_error":
            return Check("DETECTOR_ERROR", False, False, "RefactoringMiner", ["detector error"], source,
                         perf_counter() - start)
        events = detected.get("events", [])
        # the RefactoringMiner description is the request's first line (Extract Variable adds a second
        # line with the expression to extract, which no detected event contains)
        wanted = _norm(case["request"].splitlines()[0])
        if any(_norm(e.get("description", "")) == wanted for e in events):
            return Check("PASSED", True, True, "RefactoringMiner", [], source, perf_counter() - start)
        others = [_norm(e.get("description", "")) for e in events][:5]
        messages = ["Requested: " + _norm(case["request"])] + ["Detected instead: " + o for o in others]
        if not others:
            messages.append("RefactoringMiner detected no refactoring in your output.")
        return Check("OPERATION_MISSING", False, True, "RefactoringMiner", messages, source, perf_counter() - start)

    def source(self, case: dict, raw: str) -> str:
        from llm_ontology.benchmarks import refactoring_execution as ex
        return ex.parse_answer(raw, case["file_path"])

    def facts(self, case: dict, source: str):
        return java_facts.refactoring_graph(case["before"], source, case["request"], int(case["target"]["start"]))

    def score(self, case: dict, raw: str, workdir: Path) -> dict:
        from llm_ontology.benchmarks import refactoring_execution as ex
        from llm_ontology.benchmarks import refactoring_structural as structural

        try:
            source = ex.parse_answer(raw, case["file_path"])
        except Exception as exc:
            return {"success": False, "status": "model_output_failure", "error": str(exc)[:300]}
        if Path(workdir).exists():
            import shutil
            shutil.rmtree(workdir)
        result = structural.evaluate(case, source, Path(workdir), self.tool)
        return {"success": bool(result["structural_success"]), "status": result["status"]}

    # ----- checks on the stored matrix outputs (no model calls) -------------------------
    def stored_outputs(self, arms: list[str]):
        for case in self._cases:
            for arm in arms:
                out = self.source_run / "cases" / case["id"] / "predictions" / arm
                generated, evaluation = out / "generated.java", out / "evaluation" / "evaluation.json"
                if generated.exists() and evaluation.exists():
                    yield case, arm, generated.read_text(encoding="utf-8"), json.loads(evaluation.read_text())

    def checker_agreement(self, arms: list[str], workdir: Path) -> dict:
        """L5: the public checker must give the same verdict as ``structural_success``."""
        rows = []
        for case, arm, source, evaluation in self.stored_outputs(arms):
            raw = json.dumps({"file_path": case["file_path"], "refactored_code": source})
            check = self.check(case, raw, Path(workdir) / case["id"] / arm)
            rows.append({"case": case["id"], "arm": arm, "public": check.success,
                         "final": bool(evaluation.get("structural_success")), "status": check.status})
        disagree = [r for r in rows if r["public"] != r["final"]]
        return {"outputs": len(rows), "disagreements": disagree, "agreement": not disagree and bool(rows)}

    def build_pool(self, arms: list[str], manual: dict[str, dict] | None = None) -> list[dict]:
        """Labelled development examples from stored outputs: label = final evaluator, unless a
        manual label (``{"<case>/<arm>": {"defective": bool, "note": str}}``) overrides it."""
        manual = manual or {}
        pool = []
        for case, arm, source, evaluation in self.stored_outputs(arms):
            key = f"{case['id']}/{arm}"
            label = manual.get(key)
            pool.append({"id": key, "group": case["id"], "task": "refactoring", "operation": case["operation"],
                         "before": case["before"], "after": source, "request": case["request"],
                         "target_start": int(case["target"]["start"]),
                         "defective": (bool(label["defective"]) if label
                                       else not bool(evaluation.get("structural_success"))),
                         "label_source": "manual" if label else "final_evaluator",
                         "note": (label or {}).get("note", "")})
        return pool


class OllamaLoopProvider:
    """Ollama with the frozen matrix settings: temperature 0, top_p 0.9, seed 42, schema JSON."""
    name = "ollama:qwen2.5-coder:7b"

    def __init__(self, *, context_window_tokens: int, seed: int):
        from llm_ontology.benchmarks import matrix_support as shared
        self.shared, self.config = shared, shared.runtime()
        self.context, self.seed = context_window_tokens, seed

    def generate(self, prompt: str, schema: dict, max_tokens: int, temperature: float = 0.0) -> Generation:
        provider = self.shared.OllamaProvider(model_name="qwen2.5-coder:7b", max_tokens=max_tokens,
                                              context_window_tokens=self.context, temperature=temperature, top_p=.9,
                                              seed=self.seed, timeout_seconds=self.config.generation_timeout_seconds)
        if provider.resolve_model_digest() != self.config.generation_model_digest:
            raise RuntimeError("Model digest changed")
        start = perf_counter()
        result = provider.generate_result(prompt, json_schema=schema)
        if result.model_digest != self.config.generation_model_digest or result.done is not True:
            raise RuntimeError("Incomplete response or model digest mismatch")
        return Generation(result.response, result.prompt_eval_count, result.eval_count, perf_counter() - start,
                          {"done_reason": result.done_reason, "model_digest": result.model_digest,
                           "temperature": temperature})
