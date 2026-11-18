"""Build a private reservoir and audit real reference events before releasing a cohort."""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import shutil
from urllib.request import urlopen

from llm_ontology.benchmarks import refactoring_execution as ex
from llm_ontology.benchmarks.refactoring_candidates import QUOTAS, digest, exposure
from llm_ontology.benchmarks.refactoring_prepare import tool_identity
from llm_ontology.benchmarks import refactoring_structural as structural
from llm_ontology.benchmarks.refactoring_cohort import structural_qa
from llm_ontology.benchmarks.refactoring_context import contextual_pair


def materialize(repo, directory, plan, validate=None):
    records = json.loads((directory / "candidates-private.json").read_text())
    root = directory / "materialized"
    root.mkdir(exist_ok=True)

    def fetch(record):
        out = root / record["id"]
        out.mkdir(exist_ok=True)
        rejected_path = out / "rejected.json"
        if rejected_path.exists() and validate is not None:
            reason = rejected_path.read_text()
            if "28000-character" in reason:
                rejected_path.rename(out / "initial-character-screen.json")
            elif "Transformers is required" in reason:
                rejected_path.rename(out / "initial-tokenizer-infrastructure.json")
        if (out / "record-private.json").exists() or rejected_path.exists():
            return
        try:
            before, after = record["input"], record["output"]
            file = record["file_path"].split(".java", 1)[0] + ".java"
            ex.safe_path(file)
            cached = None
            cache = repo / plan.get("source_cache", "__no_source_cache__") / "materialized" / record["id"]
            if (cache / "record-private.json").exists():
                candidate = json.loads((cache / "record-private.json").read_text())
                if candidate.get("commit_sha") == record.get("commit_sha") and candidate["file_path"] == file:
                    cached = candidate
                    before, after = cached["input"], cached["output"]
            if record["source"] == "marv" and cached is None:
                base = record["commit_link"].replace("https://github.com/", "https://raw.githubusercontent.com/").replace("/commit/", "/")
                # GitHub resolves the explicit first-parent revision; content is pinned by hash.
                sources = []
                for revision in ("^1", ""):
                    url = base + revision + "/" + file
                    sources.append(urlopen(url, timeout=35).read().decode("utf-8"))
                before, after = sources
            # Only the aligned context is token-screened. Full historical files
            # are detector/preparation inputs, never automatically model inputs.
            if not structural.valid_java(before) or not structural.valid_java(after):
                raise ValueError("Full Java file does not parse")
            (out / "before.java").write_text(before)
            (out / "after.java").write_text(after)
            ex.write(out / "record-private.json", {**record, "input": before, "output": after, "file_path": file})
            if cached is not None and (cache / "events.json").exists():
                shutil.copyfile(cache / "events.json", out / "events.json")
        except RuntimeError:
            # Missing parser/tokenizer dependencies are not unsuitable data.
            raise
        except Exception as exc:
            ex.write(out / "rejected.json", {"reason": str(exc)})

    with ThreadPoolExecutor(max_workers=6) as workers:
        list(workers.map(fetch, records))
    tool = tool_identity(plan)
    calls = []
    for out in sorted(root.iterdir()):
        if (out / "record-private.json").exists() and not (out / "events.json").exists():
            record = json.loads((out / "record-private.json").read_text())
            calls.append([record["file_path"], str(out / "before.java"), str(out / "after.java"), str(out / "events.json")])
    ex.write(directory / "detector-batch.json", calls)
    if calls:
        subprocess.run([str(Path(tool["java_home"]) / "bin/java"), "-Xmx2g", "-cp", tool["classpath"],
                        "RefactoringProbe", str(directory / "detector-batch.json")], check=True, timeout=1200,
                       stdout=(directory / "detector.log").open("w"), stderr=subprocess.STDOUT)


def contextualize(directory, plan):
    root = directory / "contexts"
    root.mkdir(exist_ok=True)
    calls = []
    for original in sorted((directory / "materialized").iterdir()):
        out = root / original.name
        out.mkdir(exist_ok=True)
        if (out / "events.json").exists() or (out / "rejected.json").exists():
            continue
        try:
            if (original / "rejected.json").exists():
                raise ValueError(json.loads((original / "rejected.json").read_text())["reason"])
            record = json.loads((original / "record-private.json").read_text())
            events = json.loads((original / "events.json").read_text()).get("events", [])
            event = structural.select_event(events, record["refactoring_type"],
                                            description=record.get("description") if record["source"] == "marv" else None)
            before, after, context = contextual_pair(record["input"], record["output"], event)
            record.update(input=before, output=after, context=context, selected_description=event["description"])
            ex.write(out / "record-private.json", record)
            (out / "before.java").write_text(before)
            (out / "after.java").write_text(after)
            calls.append([record["file_path"], str(out / "before.java"), str(out / "after.java"), str(out / "events.json")])
        except Exception as exc:
            ex.write(out / "rejected.json", {"reason": str(exc)})
    if calls:
        batch = directory / "context-batch.json"
        ex.write(batch, calls)
        tool = tool_identity(plan)
        with (directory / "context-detector.log").open("w") as log:
            subprocess.run([str(Path(tool["java_home"]) / "bin/java"), "-Xmx2g", "-cp", tool["classpath"],
                            "RefactoringProbe", str(batch)], check=True, timeout=1200, stdout=log, stderr=subprocess.STDOUT)


def audit(repo, directory):
    hashes, commits, _, inputs = exposure(repo)
    accepted, rejected, seen, counts = [], [], set(), Counter()
    source_root = directory / "contexts" if (directory / "contexts").exists() else directory / "materialized"
    for out in sorted(source_root.iterdir()):
        if (out / "rejected.json").exists():
            rejected.append({"id": out.name, **json.loads((out / "rejected.json").read_text())})
            continue
        record = json.loads((out / "record-private.json").read_text())
        try:
            before, after = record["input"], record["output"]
            pair = (digest(before), digest(after))
            if any(h in hashes or h in seen for h in pair) or record["commit_sha"] in commits:
                raise ValueError("Full-file overlap/duplicate after materialization")
            payload = json.loads((out / "events.json").read_text())
            event = structural.select_event(payload.get("events", []), record["refactoring_type"], before, after,
                description=record.get("selected_description") or (record.get("description") if record["source"] == "marv" else None))
            # Explicit names, types, old/new signatures in RM description, never a gold body.
            target = {"method": "", "start": min(r["startLine"] for r in event["left"]),
                      "end": max(r["endLine"] for r in event["left"])}
            request = event["description"]
            if event["type"] == "Extract Variable":
                initializer = structural.extracted_initializer(after, event)
                if initializer is None or ex.normalize_java_for_hash(initializer) not in ex.normalize_java_for_hash(before):
                    raise ValueError("Ambiguous/missing extraction expression")
                request += "\nExtract exactly this original expression: " + initializer
            case = {"id": record["id"], "source": record["source"], "operation": record["refactoring_type"],
                    "file_path": record["file_path"], "before": before,
                    "before_sha256": ex.hashlib.sha256(before.encode()).hexdigest(),
                    "class_name": record["file_path"].removesuffix(".java").split("/")[-1],
                    "target": target, "target_event": structural.identity(event), "request": request,
                    "evaluation_level": "structural", "provenance": record["provenance"],
                    "commit": record["commit_sha"], "expected_tests": None,
                    "context": record.get("context"),
                    "reference_path": str(out / "after.java")}
            if event["type"] == "Extract Variable":
                case["extraction_expression"] = initializer
            seen.update(pair)
            accepted.append(case)
            counts[case["source"], case["operation"]] += 1
        except Exception as exc:
            rejected.append({"id": out.name, "source": record["source"], "operation": record["refactoring_type"], "reason": str(exc)})
    report = {"model_calls": 0, "status": "reference_screen_only_not_final_QA",
              "counts": {s: {op: counts[s, op] for op in ops} for s, ops in QUOTAS.items() if s != "swe"},
              "deficits": {s: {op: max(0, n - counts[s, op]) for op, n in ops.items()}
                           for s, ops in QUOTAS.items() if s != "swe"},
              "rejected": rejected, "exposure_inputs": inputs}
    ex.write(directory / "structural-candidates.json", accepted)
    ex.write(directory / "reference-screen.json", report)
    return report


def build_pool(repo, root, plan, validate):
    """Fail closed on any source/type shortfall. Never replace a missing quota."""
    from llm_ontology.benchmarks.refactoring_candidates import discover
    from llm_ontology.benchmarks.refactoring_prepare import prepare
    from llm_ontology.benchmarks.refactoring_pool import pool
    directory = repo / plan["discovery_directory"]
    if not (directory / "discovery.json").exists():
        cache = repo / plan.get("source_cache", "__no_source_cache__")
        if (cache / "candidates-private.json").exists():
            directory.mkdir(parents=True, exist_ok=False)
            for name in ("discovery.json", "candidates-private.json"):
                shutil.copyfile(cache / name, directory / name)
        else:
            discover(repo, Path(plan["raw_ml4refactoring"]), directory)
    materialize(repo, directory, plan, validate)
    contextualize(directory, plan)
    report = audit(repo, directory)
    candidates = json.loads((directory / "structural-candidates.json").read_text())
    tool = tool_identity(plan)
    accepted, counts, failures = [], Counter(), []
    qa_source = {str(p.relative_to(repo)): ex.file_sha256(p) for p in
                 [Path(__file__), Path(structural.__file__), Path(ex.__file__),
                  repo / "src/llm_ontology/benchmarks/refactoring_matrix.py",
                  repo / "src/llm_ontology/benchmarks/refactoring_context.py",
                  repo / "src/llm_ontology/benchmarks/refactoring_cohort.py"]}
    for case in candidates:
        key = case["source"], case["operation"]
        if counts[key] >= QUOTAS[key[0]][key[1]]:
            continue
        out = root / "preparation" / case["id"]
        try:
            if (out / "qa/qa.json").exists():
                control = json.loads((out / "qa/qa.json").read_text())
                if json.loads((out / "qa-identity.json").read_text()) != {"tool": tool, "case": case, "sources": qa_source}:
                    raise ValueError("QA inputs changed; use a new preparation directory")
            else:
                if out.exists():
                    raise ValueError("Interrupted QA; preserve evidence and use a new preparation directory")
                gold = ex.read_utf8(Path(case["reference_path"]))
                control = structural_qa(case, gold, out / "qa", tool, validate)
                ex.write(out / "reference-private.json", {"source": gold})
                ex.write(out / "qa-identity.json", {"tool": tool, "case": case, "sources": qa_source})
            if not control["passed"]:
                raise ValueError("Reference or negative controls failed")
            public = {k: v for k, v in case.items() if k != "reference_path"}
            public.update(reference_private=str((out / "reference-private.json").relative_to(repo)),
                          qa_path=str((out / "qa/qa.json").relative_to(repo)))
            ex.write(out / "accepted.json", public)
            accepted.append(public)
            counts[key] += 1
            print("ACCEPT", key, counts[key], flush=True)
        except Exception as exc:
            failures.append({"id": case["id"], "reason": str(exc)})
    deficits = {s: {op: max(0, n - counts[s, op]) for op, n in ops.items()}
                for s, ops in QUOTAS.items() if s != "swe"}
    ready_structural = not any(n for ops in deficits.values() for n in ops.values())
    swe_result = {"ready": False, "accepted": 0, "status": "deferred_until_structural_quotas_available"}
    if ready_structural:
        swe_plan = {**plan, "cases": 5}
        _, _, swe_plan["pool_identity"] = pool(repo, swe_plan)
        swe_result = prepare(root / "swe", swe_plan, validate)
        if swe_result["ready"]:
            selected = json.loads((root / "swe/selection.json").read_text())
            for case in selected["cases"]:
                out = root / "swe/preparation" / case["id"]
                accepted.append({**case, "source": "swe", "evaluation_level": "project",
                                 "reference_private": str((out / "reference-private.json").relative_to(repo)),
                                 "qa_path": str((out / "qa/qa.json").relative_to(repo))})
    result = {"ready": ready_structural and swe_result["ready"], "accepted": len(accepted),
              "counts": {s: {op: counts[s, op] for op in ops} for s, ops in QUOTAS.items() if s != "swe"},
              "deficits": deficits, "swe": swe_result, "failures": failures,
              "model_calls": 0, "required": 100, "reference_screen": str(directory / "reference-screen.json")}
    ex.write(root / "pool-preparation.json", result)
    if result["ready"]:
        if any(ex.file_sha256(repo / path) != digest for path, digest in qa_source.items()):
            raise ValueError("QA implementation changed during preparation; use a new run-id")
        files = {**qa_source, **{row["path"]: row["sha256"] for row in report["exposure_inputs"]}}
        for case in accepted:
            for name in ("reference_private", "qa_path"):
                files[case[name]] = ex.file_sha256(repo / case[name])
        # Freeze candidate provenance and actual materialized files, not merely counts.
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in {"java", "json"}:
                files[str(path.relative_to(repo))] = ex.file_sha256(path)
        ex.write(repo / plan["cohort_manifest"], {"cases": accepted, "files": files,
                 "tool": tool, "quotas": QUOTAS, "model_calls": 0}, exclusive=True)
    return result
