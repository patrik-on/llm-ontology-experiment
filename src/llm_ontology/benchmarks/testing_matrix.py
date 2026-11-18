"""Resumable current Methods2Test systems matrix.

Reuses the existing selection, providers, prompt builders, execution and statistics.
The skills arms add the unmodified external testing SKILL.md; they are not an
agent/tool loop. The ontology arms add the per-case project-ontology block frozen at
``--freeze-only`` (``ontology.with_ontology``). Each FT arm generates with its own
adapter, re-hashed before loading, and charges the exact prompt the tokenizer received.
No repair, training, download or index rebuild is performed.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
from time import perf_counter

from llm_ontology.benchmarks import matrix_support as batch
from llm_ontology.benchmarks import methods2test_execution as offline
from llm_ontology.benchmarks import methods2test_selection as selection
from llm_ontology import ontology
from llm_ontology.benchmarks.methods2test_statistics import aggregate
from llm_ontology.evaluation.run_layout import validate_evaluation_run_id
from llm_ontology.inference.experiment_runner import ExperimentCase
from llm_ontology.inference.prompting.instruction import format_inference_prompt

PROTOCOL = "methods2test_systems_ontology_v2"
ARMS = batch.ARMS
FT_ARMS = ("ft_testing", "ft_v3_onto", "ft_onto")
CONFIG = Path("configs/benchmarks/testing_matrix_v1.json")
REPO = Path(__file__).resolve().parents[3]
write = batch.durable_json
read = batch.read


def _fmt_p(value):
    return "n/a" if value is None else f"{value:.4f}"


def load_plan(cases=None):
    plan = read(CONFIG)
    if cases is not None:
        if not 1 <= cases <= 100:
            raise ValueError("--cases must be between 1 and 100")
        plan["cases"] = cases
    plan["max_actual_generation_calls"] = plan["cases"] * len(ARMS)
    if (plan["protocol"] != PROTOCOL or plan["arms"] != list(ARMS)
            or plan["official_split"] != "eval" or plan["indexing_allowed"]):
        raise ValueError("Unexpected matrix protocol")
    batch.check_arm_plan(plan, ARMS, FT_ARMS)
    for key, value in {"attempts_per_cell": 1, "retries": 0, "repairs": 0,
                       "max_new_tokens": 4096, "context_window_tokens": 32768,
                       "temperature": 0, "top_p": .9, "seed": 42, "repeats": 2,
                       "prompt_profile": "testing-bodies-one-shot-v2"}.items():
        if plan[key] != value:
            raise ValueError("Unsupported matrix generation setting: " + key)
    return plan


def resolve_skill(explicit=None):
    source = explicit or os.environ.get("SI_CONTEXT_EVAL_REPO")
    if source:
        path = Path(source).expanduser().resolve()
        if path.is_dir():
            path /= "skills/testing/SKILL.md"
    else:
        path = REPO / "configs/skills/testing/SKILL.md"
    content = path.read_bytes().decode("utf-8")
    if not content.strip() or len(content.encode()) > 128_000:
        raise ValueError("Missing/empty or unexpectedly large testing SKILL.md")
    return path, content


def direct_prompt(case):
    return batch.profile.BodyPromptBuilder().build(
        task="testing", instruction=case.instruction, input_text=case.input_text,
        requirements=case.requirements, project_context=case.project_context,
        contexts=(), approach="direct").text


class Matrix:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.plan = read(self.root / "matrix_plan.json")
        if self.plan != load_plan(self.plan["cases"]):
            raise ValueError("Matrix plan changed; use a new run-id")
        self.ids = read(self.root / "selection.json")["ids"]
        if (len(self.ids) != self.plan["cases"] or len(set(self.ids)) != len(self.ids)
                or any(not batch.re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", i)
                       or i in {".", ".."} for i in self.ids)):
            raise ValueError("Complete matching safe cohort required before generation")
        selected = read(self.root / "selection.json")
        if ([c["id"] for c in selected["cases"]] != self.ids
                or selected["indexing_allowed"] or selected["split"] != "official eval"):
            raise ValueError("Invalid selected cohort/role")
        self.maximum = len(self.ids) * len(ARMS)

    def out(self, ident, arm):
        return self.root / "cases" / ident / "predictions" / arm

    def case(self, ident, arm):
        """The arm's case. FT arms get their full FT instruction (``ft_case``) here too, so
        the frozen prompt and the generation call are built by this one function."""
        case = ExperimentCase.model_validate(read(self.root / "cases" / ident / "case.json"))
        if case.case_id != ident:
            raise ValueError("Mismatching case identity")
        if arm in batch.SKILL_ARMS:
            skill = (self.root / "context/SKILL.md").read_bytes().decode("utf-8")
            case = case.model_copy(update={"instruction": case.instruction
                + "\n\n<testing-process-skill>\n" + skill
                + "\n</testing-process-skill>\nApply relevant guidance within this single"
                " response. The fixed two-body JSON contract takes precedence; no tools,"
                " repairs or extra output are available."})
        if arm in FT_ARMS:
            case = batch.ft_case(case)
        if arm in batch.ONTOLOGY_ARMS:
            block = batch.frozen_block(self.root / "cases" / ident / "ontology")
            case = case.model_copy(update={"instruction": batch.with_ontology(case.instruction, block)})
        return case

    def prompt(self, ident, arm, c=None, out=None, audit=None):
        case = self.case(ident, arm)
        if arm in FT_ARMS:
            return format_inference_prompt(case.instruction, case.input_text)
        if arm == "rag_single":
            return batch._render_rag(c, case, out, arm, audit)
        return direct_prompt(case)

    def dispatches(self):
        paths = list(self.root.glob("cases/*/predictions/*/dispatch.json"))
        for path in paths:
            if path.parents[2].name not in self.ids or path.parent.name not in ARMS:
                raise ValueError("Unplanned dispatch")
        if len(paths) > self.maximum:
            raise ValueError("Matrix budget exceeded")
        return paths

    def progress(self):
        cells = {}
        for ident in self.ids:
            for arm in ARMS:
                out = self.out(ident, arm)
                status = (read(out / "completion.json")["status"]
                          if (out / "completion.json").exists()
                          else "interrupted_unresolved" if (out / "dispatch.json").exists()
                          else "blocked" if (self.root / (arm + "-stop.json")).exists()
                          else "pending")
                cells[ident + "/" + arm] = status
        result = {"updated_at": batch.now(), "maximum": self.maximum,
                  "charged": len(self.dispatches()), "cells": cells,
                  "completed": sum(s in {"assembled", "model_output_failure",
                      "infrastructure_failure", "pre_dispatch_failure"} for s in cells.values())}
        write(self.root / "progress.json", result)
        print("PROGRESS", result["completed"], "/", self.maximum,
              "charged", result["charged"], flush=True)
        return result

    def freeze(self):
        if (self.root / "freeze.json").exists():
            return self.verify()
        if self.dispatches():
            raise ValueError("Cannot freeze after dispatch")
        c = batch.runtime()
        control_root = self.root / "preflight" / batch.uuid4().hex
        batch._controls(control_root, c, read(self.root / "selection.json"))
        identities = batch.freeze_hf_identities(self.root, c, self.plan["adapters"])
        model_files = sorted({p for path in identities.values() for p in read(path)["files"]})
        write(self.root / "hf_file_pins.json", {
            p: {"bytes": Path(p).stat().st_size, "mtime_ns": Path(p).stat().st_mtime_ns}
            for p in model_files})
        provider = batch.OllamaProvider(model_name=batch.direct.MODELS["qwen_base"][0])
        if provider.resolve_model_digest() != c.generation_model_digest:
            raise ValueError("Generation model digest mismatch")
        write(self.root / "ollama_identity.json", provider.describe_model())
        manifests = Path(batch.load_rag_config(c.retrieval_config).vector_store.persist_path) / "manifests"
        index = {str(p.resolve()): batch.file_sha256(p) for p in sorted(manifests.glob("*.json"))}
        if not index:
            raise ValueError("Missing existing index manifests")
        write(self.root / "index_identity.json", index)
        audit = read(self.root / "leakage_audit.json")
        for p, digest in audit["snapshots"].items():
            if batch.file_sha256(Path(p)) != digest:
                raise ValueError("Leakage snapshot changed: " + p)
        gold = [read(self.root / "cases" / i / "raw-private.json")["raw"]["test_case"]["body"]
                for i in self.ids]
        files = set()
        for ident in self.ids:
            cr = self.root / "cases" / ident
            record = read(cr / "raw-private.json")
            prod, ref, _ = selection.general_wrap_record(record, selection.infer_spec(record["raw"]))
            prepared = read(cr / "prepared.json")
            reference = read(cr / "reference-coverage/coverage.json")
            classfile = Path(prepared["revision"]["bin_classes"]) / (
                prepared["focal_class"].replace(".", "/") + ".class")
            if (prod != self.case(ident, "qwen_base").input_text
                    or ref != (cr / "reference-private.java").read_text()
                    or batch.sha(prod) != prepared["production_sha256"]
                    or batch.sha(ref) != prepared["reference_sha256"]
                    or reference["status"] != "passed" or not reference["focal_invoked"]
                    or not reference["coverage"]
                    or batch.file_sha256(classfile) != reference["production_class_sha256"]):
                raise ValueError("Unsafe/changed wrapper or reference: " + ident)
            # The ontology block sees only the supplied production class; the gold test is
            # passed as forbidden text and must not appear in it.
            batch.freeze_ontology(cr / "ontology", lambda: ontology.testing_context(
                self.case(ident, "qwen_base"), forbidden=(gold[self.ids.index(ident)],)),
                self.plan["ontology_schema_version"])
            # Pin original rich/corpus agreement as well as the audited source bytes.
            candidate = next(a for a in audit["candidates"] if a["id"] == ident)
            corpus = Path(candidate["corpus_path"])
            if batch.file_sha256(corpus) != candidate["corpus_sha256"]:
                raise ValueError("Corpus changed")
            files.add(corpus.resolve())
            for arm in ARMS:
                out = cr / "frozen_prompts" / arm
                out.mkdir(parents=True, exist_ok=True)
                prompt = self.prompt(ident, arm, c, out, audit)
                if prompt.count(batch.profile.DEMO_BLOCK) != 1 or any(g and g in prompt for g in gold):
                    raise ValueError("One-shot/gold isolation failed")
                (out / "prompt.txt").write_text(prompt, encoding="utf-8")
            # Pin inputs, reference evidence and every rendered prompt, never predictions.
            files.update(p.resolve() for p in cr.rglob("*") if p.is_file()
                         and "predictions" not in p.relative_to(cr).parts)
            files.update(Path(prepared["revision"]["bin_classes"]).rglob("*.class"))
            files.update(Path(p) for p in prepared["revision"].get("dependencies", []))
        sources = batch.build_dependency_identity(c)
        sources[str(CONFIG.resolve())] = batch.file_sha256(CONFIG)
        entry = REPO / "scripts/benchmarks/run_testing_matrix.py"
        sources[str(entry)] = batch.file_sha256(entry)
        for source in sources:
            target = self.root / "source_snapshot" / Path(source).relative_to(REPO)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(Path(source).read_bytes())
            files.add(target)
        files.update(self.root / n for n in ["matrix_plan.json", "selection.json",
            "leakage_audit.json", "selection_protocol.json",
            *(Path("hf_identity") / (n + ".json") for n in sorted(set(self.plan["adapters"].values()))),
            "hf_file_pins.json", "ollama_identity.json", "index_identity.json",
            "context/SKILL.md", "context/identity.json"])
        files.update(Path(p).resolve() for p in audit["snapshots"])
        files.add(selection.ARCHIVE.resolve())
        files.update(p for p in control_root.rglob("*") if p.is_file())
        write(self.root / "freeze.json", {"protocol": PROTOCOL, "created_at": batch.now(),
            "files": {str(p.absolute()): batch.file_sha256(p) for p in sorted(files)},
            "sources": sources, "java": {str(p): batch.file_sha256(p) for p in
                [c.java_home / "bin/java", c.java_home / "bin/javac", c.junit_jar]},
            "maximum": self.maximum}, exclusive=True)
        self.progress()

    def verify(self):
        frozen = read(self.root / "freeze.json")
        if frozen["protocol"] != PROTOCOL or frozen["maximum"] != self.maximum:
            raise ValueError("Wrong freeze protocol/budget")
        for group in ["files", "sources", "java"]:
            for p, digest in frozen[group].items():
                if batch.file_sha256(Path(p)) != digest:
                    raise ValueError("Frozen dependency changed: " + p)
        for p, pin in read(self.root / "hf_file_pins.json").items():
            stat = Path(p).stat()
            if pin != {"bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}:
                raise ValueError("Model file changed: " + p)

    def generate(self, arm):
        c, loaded, identity = batch.runtime(), None, None
        pending = [i for i in self.ids if not (self.out(i, arm) / "dispatch.json").exists()
                   and not (self.out(i, arm) / "completion.json").exists()]
        stop = self.root / (arm + "-stop.json")
        # An interrupted transport's outcome is unknown: do not retry or continue that arm.
        if stop.exists() or any((self.out(i, arm) / "dispatch.json").exists()
                and not (self.out(i, arm) / "completion.json").exists() for i in self.ids):
            return
        if not pending:
            return
        try:
            if arm in FT_ARMS:
                identity = batch.arm_hf_identity(self.root, self.plan["adapters"], arm)
                write(self.root / (arm + "-loaded_identity.json"), {"adapter": self.plan["adapters"][arm],
                    "verified_at": batch.now(), "files": identity["files"]})
                loaded = batch.load_eval_model(identity["model"], {**identity["inference"],
                    "local_files_only": True, "trust_remote_code": False})
            for ident in pending:
                out = self.out(ident, arm)
                out.mkdir(parents=True, exist_ok=True)
                case, generated = self.case(ident, arm), None
                ledger, started = Ledger(self, ident, arm), perf_counter()
                try:
                    if arm in FT_ARMS:
                        generated = batch.generate_ft(c, case, out,
                            loaded_model=loaded, model_identity=identity,
                            before_generation=lambda prompt: ledger.charge({"prompt": prompt,
                                "max_new_tokens": 4096, "do_sample": False, "seed": 42}))
                    elif arm != "rag_single":
                        generated = batch._generate_direct(c, case, out, ledger, protocol_id=PROTOCOL)
                    else:
                        generated = batch.generate_rag(c, case, out, arm,
                            read(self.root / "leakage_audit.json"), body_profile=True, opener=ledger)
                    if ledger.dispatch_time is None:
                        raise RuntimeError("Generation returned without charged dispatch")
                    raw = batch._raw(out, generated)
                    if batch._infrastructure(out, raw):
                        raise RuntimeError("Empty/API response anomaly")
                    write(out / "received.json", generated)
                    answer = batch.parse_testing_bodies(raw)
                    write(out / "bodies.json", answer.model_dump())
                    source = batch.assemble((self.root / "cases" / ident / "scaffold.java").read_text(), answer)
                    (out / "generated.java").write_text(source, encoding="utf-8")
                    write(out / "generation.json", {"source_sha256": batch.sha(source), "assembled": True})
                    status = "assembled"
                except Exception as exc:
                    raw = batch._raw(out, generated, exc)
                    if raw:
                        (out / "raw.txt").write_text(raw, encoding="utf-8")
                    write(out / "failure.json", batch.generation_failure_payload(exc,
                        case_sha256=batch.file_sha256(self.root / "cases" / ident / "case.json"), arm=arm))
                    status = ("pre_dispatch_failure" if ledger.dispatch_time is None else
                              "infrastructure_failure" if batch._infrastructure(out, raw)
                              or isinstance(exc, batch.InfrastructureFailure) else "model_output_failure")
                if status in {"infrastructure_failure", "pre_dispatch_failure"}:
                    write(stop, {"id": ident, "status": status, "created_at": batch.now()}, exclusive=True)
                write(out / "completion.json", {"status": status,
                    "generation_pipeline_seconds": perf_counter() - started}, exclusive=True)
                self.progress()
                if stop.exists():
                    break
        except Exception as exc:
            if not stop.exists():
                write(stop, {"status": "pre_dispatch_failure", "error": str(exc)}, exclusive=True)
            raise
        finally:
            if loaded is not None:
                del loaded
                gc.collect()
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

    def report(self):
        # Recheck stored candidate and coverage identities, including report-only mode.
        for ident in self.ids:
            reference_path = self.root / "cases" / ident / "reference-coverage/coverage.json"
            reference = read(reference_path)["coverage"] if reference_path.exists() else None
            for arm in ARMS:
                out = self.out(ident, arm)
                source = out / "generated.java"
                if not source.exists():
                    continue
                if batch.file_sha256(source) != read(out / "generation.json")["source_sha256"]:
                    raise ValueError("Stored candidate changed")
                if not (out / "metrics.json").exists():
                    continue  # Explicitly unknown until evaluated.
                metrics = read(out / "metrics.json")
                if metrics["source_sha256"] != batch.file_sha256(source):
                    raise ValueError("Metrics refer to another source")
                if metrics["statuses"] != ["source_review_rejected"]:
                    if len(metrics["outcomes"]) != 2:
                        raise ValueError("Two fresh executions required")
                    for result in metrics["outcomes"]:
                        if result["status"] != "passed" and result["coverage"] is not None:
                            raise ValueError("Failed coverage cannot receive primary credit")
                        coverage = result["coverage"] or result.get("diagnostic_coverage")
                        if coverage and coverage["status"] == "measured":
                            if not reference or coverage["method"]["descriptor"] != reference["method"]["descriptor"]:
                                raise ValueError("Wrong focal overload")
                            for scope in ["method", "class"]:
                                for counter in ["line", "branch"]:
                                    if coverage[scope]["counters"][counter]["total"] != reference[scope]["counters"][counter]["total"]:
                                        raise ValueError("Coverage denominator changed")
        result = aggregate(self.root, arms=ARMS, pairs=self.plan["primary_pairs"])
        result.update(protocol=PROTOCOL, skill=read(self.root / "context/identity.json"),
            generation_budget_complete=all((self.out(i, a) / "completion.json").exists()
                and (self.out(i, a) / "dispatch.json").exists() for i in self.ids for a in ARMS))
        result["evaluation_complete"] = result["generation_budget_complete"] and all(
            not (self.out(i, a) / "generated.java").exists()
            or (self.out(i, a) / "metrics.json").exists() for i in self.ids for a in ARMS)
        write(self.root / "reports/aggregate.json", result)
        lines = ["# Testing matrix", "", "Protocol: " + PROTOCOL, "",
                 "| Arm | Calls | Compiled | Class pass | Focal invoked | Unknown class result |",
                 "|---|---:|---:|---:|---:|---:|"]
        for arm, stats in result["arms"].items():
            lines.append(f"| {arm} | {stats['actual_calls']}/{len(self.ids)} | "
                f"{stats['compiled']['count']} | {stats['class_pass']['count']} | "
                f"{stats['focal_invoked_accepted']['count']} | {stats['class_pass']['unknown']} |")
        lines += ["", "## Primary pairs (exact tests, Holm across the predeclared pairs)", "",
                  "A is the arm with the added context, B its control on the same cases and backend.", "",
                  "| A | B | Class pass A only / B only | Class pass Δ (pp) | p McNemar (Holm) | Method line credit Δ | p Wilcoxon (Holm) |",
                  "|---|---|---:|---:|---:|---:|---:|"]
        for pair in result["paired_comparisons"]:
            cp = pair["class_pass"]
            cov = pair["coverage_success_credit"]["method"]["line"]
            delta = "n/a" if cov["mean_difference"] is None else f"{cov['mean_difference']:+.3f}"
            pp = "n/a" if cp["mean_difference"] is None else f"{100 * cp['mean_difference']:+.1f}"
            lines.append(f"| {pair['arm_a']} | {pair['arm_b']} | {cp['a_higher']} / {cp['b_higher']} | {pp} | "
                f"{_fmt_p(cp['significance']['p_value'])} ({_fmt_p(cp['significance']['p_holm'])}) | {delta} | "
                f"{_fmt_p(cov['significance']['p_value'])} ({_fmt_p(cov['significance']['p_holm'])}) |")
        lines += ["", "## Repeat diagnostics (no scoring change)", ""]
        for row in result["paired_matrix"]:
            warnings = row["repeat_diagnostics"]["warnings"]
            if warnings:
                lines.append(f"- {row['id']}/{row['arm']}: {', '.join(warnings)}. "
                    "Both measurements are in aggregate.json: paired_matrix / repeat_diagnostics / coverage_by_repeat.")
        lines += ["", "Pending/interrupted results are unknown; completed failures keep their existing scoring policy."]
        lines += ["", "Missing/unattempted cells are not passing or measured zero coverage.",
                  "Extracted-method validation; no real-bug detection or causal FT claim.",
                  "Ontology arms measure automatically derived structured context from the supplied code;"
                  " FT and Ollama arms are compared only within their backend."]
        (self.root / "reports/summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return result


class Ledger(batch.Ledger):
    """Reuse the provider interceptor, with this matrix's frozen prompts and cap."""
    def __init__(self, matrix, ident, arm):
        self.matrix, self.root = matrix, matrix.root
        self.ident, self.arm = ident, arm
        self.out, self.dispatch_time = matrix.out(ident, arm), None

    def charge(self, payload):
        if self.ident not in self.matrix.ids or self.arm not in ARMS:
            raise ValueError("Unplanned cell")
        expected = (self.root / "cases" / self.ident / "frozen_prompts" / self.arm / "prompt.txt").read_text()
        if payload.get("prompt") != expected:
            raise ValueError("Actual prompt differs from frozen prompt")
        with batch.file_lock(self.root, ".budget.lock"):
            if ((self.out / "completion.json").exists()
                    or (self.root / (self.arm + "-stop.json")).exists()):
                raise RuntimeError("Cell completed or arm fail-stopped")
            if len(self.matrix.dispatches()) >= self.matrix.maximum:
                raise RuntimeError("Generation cap reached")
            write(self.out / "dispatch.json", {"id": self.ident, "arm": self.arm,
                "charged_to_budget": True, "request": payload, "charged_at": batch.now()}, exclusive=True)
            self.dispatch_time = perf_counter()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--cases", type=int, help="1..100 (default 100 on new runs)")
    parser.add_argument("--skill-file", type=Path, help="Override SKILL.md or si-context-eval repo (default: pinned configs/skills/testing/SKILL.md)")
    parser.add_argument("--dry-run", action="store_true", help="Offline plan; no files/API/model calls")
    parser.add_argument("--prepare-only", action="store_true", help="Selection/reference controls, no generation")
    parser.add_argument("--freeze-only", action="store_true", help="Prepare and freeze actual prompts; metadata/embeddings only, no generation")
    parser.add_argument("--report-only", action="store_true", help="Read stored evidence without generation/execution")
    args = parser.parse_args(argv)
    if sum([args.dry_run, args.prepare_only, args.freeze_only, args.report_only]) > 1:
        parser.error("Choose only one planning/preparation/report mode")
    validate_evaluation_run_id(args.run_id)
    os.chdir(REPO)
    root = REPO / "artifacts/evaluation/runs" / args.run_id
    existing = root / "matrix_plan.json"
    plan = read(existing) if existing.exists() else load_plan(args.cases)
    if args.cases is not None and args.cases != plan["cases"]:
        raise ValueError("Cannot change case count on resume; use a new run-id")
    if args.report_only:
        matrix = Matrix(root)
        if (root / "freeze.json").exists():
            matrix.verify()
        result = matrix.report()
        print("REPORT", result["actual_calls"], "/", result["max_actual_calls"])
        return 0
    skill_path, skill = resolve_skill(args.skill_file)
    if args.dry_run:
        print(json.dumps({**plan, "run_root": str(root), "skill_path": str(skill_path),
                          "skill_sha256": batch.sha(skill), "model_calls": 0}, indent=2))
        return 0
    batch.require_wsl()
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    # GPU lock shared across all NEW matrix runs, not merely within one run-id.
    with batch.file_lock(REPO / "artifacts/evaluation", ".testing-matrix-gpu.lock", blocking=False):
        if root.exists() and not existing.exists():
            raise ValueError("Run-id belongs to another/incomplete protocol; choose a new run-id")
        if not existing.exists():
            root.mkdir(parents=True, exist_ok=False)
            write(existing, plan)
            (root / "context").mkdir()
            (root / "context/SKILL.md").write_bytes(skill.encode("utf-8"))
            write(root / "context/identity.json", {"source": str(skill_path),
                "sha256": batch.sha(skill), "bytes": len(skill.encode()),
                "mode": "single-response prompt context, not agent/tool execution"})
        elif read(root / "context/identity.json")["sha256"] != batch.sha(skill):
            raise ValueError("Skill changed on resume; use the original file or a new run-id")
        if (not (root / "selection.json").exists()
                or len(read(root / "selection.json")["ids"]) != plan["cases"]):
            selection.prepare(root, config=plan)
        matrix = Matrix(root)
        if args.prepare_only:
            print("PREPARED", len(matrix.ids), "MODEL_CALLS 0", flush=True)
            return 0
        matrix.freeze()
        matrix.verify()
        if args.freeze_only:
            print("FROZEN", matrix.maximum, "PROMPTS; MODEL_CALLS 0", flush=True)
            return 0
        for arm in ARMS:
            try:
                matrix.generate(arm)
            except Exception as exc:
                print("ARM BLOCKED", arm, str(exc), flush=True)
            offline.run(root, arms=ARMS)
            matrix.report()
        matrix.verify()
        result = matrix.report()
        matrix.progress()
        print("REPORT", root / "reports/summary.md", flush=True)
        return 0 if result["evaluation_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
