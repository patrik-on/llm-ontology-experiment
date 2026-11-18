"""Eval-aligned (v3) fine-tuning datasets.

The v2 adapters were trained on ``short Slovak instruction -> raw Java`` while the
current matrices send a long English JSON contract and parse the answer with a
strict ``json.loads``. v3 records are rendered by the *same* functions the
matrices use for their FT arms, and their gold outputs are the exact JSON shape the
matrices parse:

* testing: ``ft_case(apply_profile(case))`` + wrapped production class ->
  ``{"testCase1": ..., "testCase2": ...}`` (Jupiter test bodies only);
* refactoring: ``refactoring_matrix.instruction(case)`` + aligned context unit ->
  ``{"file_path": ..., "refactored_code": ...}``.

Every build writes two datasets from ONE shared manifest: v3 (no ontology) and
v3_onto (the same records with the project-ontology block added to the instruction by
``ontology.with_ontology``). Records whose block cannot be built, or whose longer
variant exceeds the token limit, leave both datasets, and one project-grouped split is
made, so the two adapters see identical cases, order, splits and gold outputs.

Nothing here touches an evaluation run, its frozen inputs or its cohort. Training
sources are screened against the released refactoring cohort and the processed
held-out test splits; Methods2Test training comes from the official TRAIN archive,
which is project-disjoint from the EVAL archive used by the testing matrix.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import re
import tarfile
from typing import Any, Callable, Iterable, Iterator
import zipfile

from llm_ontology.datasets.format import write_jsonl
from llm_ontology.datasets.group_split import grouped_split_by_ratios, record_group_key
from llm_ontology.ingestion.manifest import GroupLevel
from llm_ontology.inference.prompting.instruction import format_prompt

FORMAT = "eval_aligned_v3"
SPLIT_RATIOS = {"train": 0.9, "val": 0.1}
# Every operation in the released refactoring cohort, plus the SWE operations.
REFACTORING_OPERATIONS = (
    "Extract Method", "Inline Method", "Rename Method", "Rename Variable", "Remove Parameter",
    "Extract Variable", "Inline Variable", "Rename Parameter", "Rename Class",
    "Parameterize Variable", "Replace Variable With Attribute",
)
MARV_OPERATIONS = ("Extract Method", "Rename Method", "Rename Variable", "Remove Parameter")

# Jupiter Assertions arity without the optional trailing message.
_BASE_ARITY = {
    "assertTrue": 1, "assertFalse": 1, "assertNull": 1, "assertNotNull": 1,
    "assertEquals": 2, "assertNotEquals": 2, "assertSame": 2, "assertNotSame": 2,
    "assertArrayEquals": 2,
}
_JUNIT4_QUALIFIED = re.compile(r"\b(?:org\.junit\.)?Assert\.(assert\w+|fail)\b")
_UNSUPPORTED_BODY = re.compile(r"\b(?:assertThat|assume\w*|Assume|ExpectedException|Mockito|mock\s*\()\b")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# --------------------------------------------------------------------------- testing


def test_body(method_source: str) -> str:
    """Interior of a simple ``@Test`` method, without its outer braces."""
    start, end = method_source.find("{"), method_source.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("test_method_without_body")
    lines = method_source[start + 1:end].strip("\n").splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
    cut = min(indents, default=0)
    return "\n".join(line[cut:] if line.strip() else "" for line in lines).strip("\n")


def _call_arguments(text: str, open_paren: int) -> list[str] | None:
    """Top-level arguments of the call whose ``(`` is at ``open_paren``."""
    depth, quote, escaped, start, args = 0, "", False, open_paren + 1, []
    for i in range(open_paren, len(text)):
        ch = text[i]
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                args.append(text[start:i].strip())
                return [a for a in args if a]
        elif ch == "," and depth == 1:
            args.append(text[start:i].strip())
            start = i + 1
    return None


def jupiter_compatible_body(body: str) -> str:
    """Map JUnit 4 ``Assert.*`` calls onto the scaffold's static Jupiter imports.

    Bodies whose meaning would change (JUnit 4 message-first overloads) or that need
    APIs the evaluation scaffold does not import are rejected, never rewritten.
    """
    body = _JUNIT4_QUALIFIED.sub(lambda m: m.group(1), body)
    if _UNSUPPORTED_BODY.search(body):
        raise ValueError("assertion_or_api_not_in_jupiter_scaffold")
    for match in re.finditer(r"\b(" + "|".join(_BASE_ARITY) + r")\s*\(", body):
        args = _call_arguments(body, match.end() - 1)
        if args is None:
            raise ValueError("unbalanced_assertion_call")
        if len(args) > _BASE_ARITY[match.group(1)] and args[0].startswith('"'):
            raise ValueError("junit4_message_first_assertion")
    return body


def _uses_test_class_members(body: str, d: dict[str, Any]) -> bool:
    test_class = d.get("test_class") or {}
    names = {f.get("var_name") for f in test_class.get("fields", []) if f.get("var_name")}
    names |= {m.get("identifier") for m in test_class.get("methods", []) if m.get("identifier")}
    names.discard(d.get("test_case", {}).get("identifier"))
    return any(re.search(r"\b" + re.escape(n) + r"\b", body) for n in names)


def testing_candidate(d: dict[str, Any]) -> dict[str, Any]:
    """One screened Methods2Test pair in the exact testing-matrix input shape.

    Uses the matrix's own selection screen (``infer_spec``) and production wrapper
    (``general_wrap_record``) so the input distribution matches the EVAL cohort.
    """
    from llm_ontology.benchmarks.methods2test_selection import general_wrap_record, infer_spec
    from llm_ontology.inference.prompting.testing_bodies_v1 import validate_body

    spec = infer_spec(d)
    if "/src/main/java/" not in d["focal_class"]["file"]:
        raise ValueError("unsupported_source_package_path")
    if spec["assertions"] != "jupiter":
        raise ValueError("assertion_library_not_in_jupiter_scaffold")
    if set(spec["reference_imports"]) - set(spec["imports"]):
        raise ValueError("reference_needs_types_not_in_scaffold")
    production, _, policy = general_wrap_record({"raw": d}, spec)
    body = jupiter_compatible_body(test_body(d["test_case"]["body"]))
    if _uses_test_class_members(body, d):
        raise ValueError("reference_uses_test_class_members")
    validate_body(body)
    name = d["focal_class"]["identifier"]
    candidate = {
        "fqn": policy["package_inferred_from_path"] + "." + name,
        "production": production,
        "signature": d["focal_method"]["full_signature"],
        "method_name": d["focal_method"]["identifier"],
        "repository": d["repository"]["url"],
        "project": str(d["repository"]["repo_id"]),
        "body": body,
        "focal_key": (str(d["repository"]["repo_id"]), d["focal_class"]["file"],
                      d["focal_method"]["full_signature"]),
    }
    testing_case(candidate, "screen")  # same scaffold checks (FQN, import collisions) as eval
    return candidate


def testing_case(candidate: dict[str, Any], case_id: str):
    """Mirror ``methods2test_selection.prepare_record_general`` case construction."""
    from llm_ontology.inference.experiment_runner import ExperimentCase
    from llm_ontology.inference.prompting import testing_bodies_one_shot_v2 as profile

    case = ExperimentCase(
        case_id=case_id,
        instruction="Generate Java Jupiter tests.",
        input_text=candidate["production"],
        project_context="Focal public API: " + candidate["fqn"] + "." + candidate["signature"]
        + ". Only supplied extracted class/JDK/Jupiter APIs are available. Original unrelated "
        "methods are not supplied.",
        structured_identity={"repository": candidate["repository"], "project": candidate["project"],
                             "class_name": candidate["fqn"], "method_name": candidate["method_name"]},
        metadata={"dataset_version": "methods2test-train-" + FORMAT, "split": "train"},
    )
    return profile.apply_profile(case)


def testing_record(first: dict[str, Any], second: dict[str, Any], case_id: str) -> dict[str, Any]:
    """FT training record whose prompt is byte-identical to the ``ft_testing`` prompt."""
    from llm_ontology.benchmarks.matrix_support import ft_case

    case = ft_case(testing_case(first, case_id))
    block = _ontology_block(lambda: _ontology().testing_context(testing_case(first, case_id)))
    output = json.dumps({"testCase1": first["body"], "testCase2": second["body"]},
                        ensure_ascii=False, separators=(",", ":"))
    return {"instruction": case.instruction, "input": case.input_text, "output": output,
            "domain": "testing", "source": "methods2test", "format": FORMAT,
            "prompt_profile": case.metadata.get("prompt_profile"), "case_id": case_id,
            "project": first["project"], "repository": first["repository"],
            "method_id": "|".join(first["focal_key"]), **block}


def iter_methods2test_archive(path: str | Path, max_member_bytes: int = 4_000_000
                              ) -> Iterator[tuple[str, dict[str, Any]]]:
    with tarfile.open(path, "r|bz2") as tar:
        for member in tar:
            if not member.isfile() or not member.name.endswith(".json") or member.size > max_member_bytes:
                continue
            yield Path(member.name).stem, json.loads(tar.extractfile(member).read())


def pair_testing_candidates(candidates: Iterable[dict[str, Any]], project_cap: int, seed: int
                            ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Two distinct gold tests of the SAME focal method fill the two slots; at most one
    pair per focal method and ``project_cap`` pairs per project."""
    by_focal: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        bodies = by_focal[candidate["focal_key"]]
        if all(_sha(c["body"]) != _sha(candidate["body"]) for c in bodies):
            bodies.append(candidate)
    pairs, per_project = [], Counter()
    keys = sorted(by_focal)
    random.Random(seed).shuffle(keys)
    for key in keys:
        bodies = by_focal[key]
        if len(bodies) < 2 or per_project[key[0]] >= project_cap:
            continue
        pairs.append((bodies[0], bodies[1]))
        per_project[key[0]] += 1
    return pairs


def build_testing_v3(archive: str | Path, out_dir: str | Path, *, train_size: int = 4000,
                     val_size: int = 500, project_cap: int = 20, seed: int = 42,
                     max_records: int | None = None, fits: Callable[[dict], bool] | None = None,
                     onto_out_dir: str | Path | None = None) -> dict[str, Any]:
    reasons, candidates, scanned = Counter(), [], 0
    for ident, d in iter_methods2test_archive(archive):
        scanned += 1
        if max_records is not None and scanned > max_records:
            break
        try:
            candidates.append({**testing_candidate(d), "id": ident})
        except (ValueError, KeyError) as exc:
            reasons[str(exc) or type(exc).__name__] += 1
        if scanned % 5000 == 0:
            print("SCAN", scanned, "CANDIDATES", len(candidates), flush=True)
    pairs = pair_testing_candidates(candidates, project_cap, seed)
    records = [testing_record(a, b, a["id"] + "+" + b["id"]) for a, b in pairs]
    return _finish(records, out_dir, {"train": train_size, "val": val_size}, seed, fits,
                   {"scanned": scanned, "candidates": len(candidates), "pairs": len(pairs),
                    "rejections": dict(reasons), "archive": str(archive)}, onto_out_dir)


# ----------------------------------------------------------------------- refactoring


def cohort_exclusions(repo: Path, manifest: str | Path) -> dict[str, set[str]]:
    """Commits, projects and normalized before/after hashes of released eval cases
    and of the processed held-out test splits."""
    from llm_ontology.benchmarks.refactoring_candidates import digest

    commits, projects, hashes = set(), set(), set()
    cases = json.loads((repo / manifest).read_text())["cases"] if (repo / manifest).is_file() else []
    for case in cases:
        if case.get("commit"):
            commits.add(str(case["commit"]).lower())
        if case.get("before"):
            hashes.add(digest(case["before"]))
        member = (case.get("provenance") or {}).get("before_member", "")
        if match := re.search(r"output/([^/]+)/storage/", member):
            projects.add(match[1].lower())
    for path in sorted(repo.glob("data/processed/**/test.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            for key in ("input", "output"):
                if record.get(key):
                    hashes.add(digest(record[key]))
            if record.get("commit_sha"):
                commits.add(record["commit_sha"].lower())
            if record.get("source") == "ml4refactoring" and record.get("project"):
                projects.add(record["project"].lower())
    return {"commits": commits, "projects": projects, "hashes": hashes}


def discover_refactoring_training(repo: Path, raw_ml4ref: Path, output: Path, *, manifest: str | Path,
                                  per_type: int = 400, max_archives: int | None = None) -> dict:
    """Candidates in the layout ``refactoring_mixed_prepare.materialize`` consumes.

    MaRV comes from the processed TRAIN split; ML4Ref from raw archives of projects that
    are neither in the released cohort nor in a processed held-out test split.
    """
    from llm_ontology.benchmarks.refactoring_candidates import digest
    from llm_ontology.datasets.ml4refactoring import extract_refactoring_type

    output.mkdir(parents=True, exist_ok=False)
    excluded = cohort_exclusions(repo, manifest)
    candidates, rejected, counts, seen = [], Counter(), Counter(), set()

    def add(record, provenance):
        source, operation = record["source"], record["refactoring_type"]
        allowed = MARV_OPERATIONS if source == "marv" else REFACTORING_OPERATIONS
        if operation not in allowed or (source != "marv" and counts[source, operation] >= per_type):
            return
        pair = (digest(record["input"]), digest(record["output"]))
        if pair[0] == pair[1]:
            rejected["no_op"] += 1
        elif record.get("commit_sha", "").lower() in excluded["commits"] or any(
                h in excluded["hashes"] for h in pair):
            rejected["eval_or_test_overlap"] += 1
        elif pair in seen:
            rejected["duplicate_pair"] += 1
        elif max(len(record["input"]), len(record["output"])) > 18000:
            rejected["large_file"] += 1
        else:
            seen.add(pair)
            ident = source + "-" + _sha(json.dumps([provenance, pair], sort_keys=True))[:24]
            candidates.append({**record, "id": ident, "provenance": provenance})
            counts[source, operation] += 1

    marv = repo / "data/processed/refactoring_marv/train.jsonl"
    for number, line in enumerate(marv.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            add(json.loads(line), {"path": str(marv.relative_to(repo)), "line": number})
    archives = 0
    for path in sorted(raw_ml4ref.glob("*.zip")):
        if all(counts["ml4refactoring", op] >= per_type for op in REFACTORING_OPERATIONS):
            break
        if max_archives is not None and archives >= max_archives:
            break
        if path.stem.removeprefix("apache-").lower() in excluded["projects"]:
            continue
        archives += 1
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                for name in sorted(names):
                    if "/before-refactoring/" not in name or "-astc" in name or ".java" not in name:
                        continue
                    operation = extract_refactoring_type(name.split("/")[-1])
                    if operation not in REFACTORING_OPERATIONS or counts["ml4refactoring", operation] >= per_type:
                        continue
                    after_name = name.replace("/before-refactoring/", "/after-refactoring/")
                    if after_name not in names or max(archive.getinfo(n).file_size for n in (name, after_name)) > 18000:
                        continue
                    prefix, file_path = name.split("/before-refactoring/", 1)
                    match = re.search(r"/([^/]+)/storage/([^/]+)$", prefix)
                    if not match or match[1].lower() in excluded["projects"]:
                        continue
                    add({"source": "ml4refactoring", "refactoring_type": operation,
                         "project": match[1], "commit_sha": match[2], "file_path": file_path,
                         "input": archive.read(name).decode("utf-8"),
                         "output": archive.read(after_name).decode("utf-8")},
                        {"archive": str(path), "before_member": name, "after_member": after_name})
        except (zipfile.BadZipFile, UnicodeDecodeError) as exc:
            rejected[type(exc).__name__] += 1
    report = {"format": FORMAT, "raw_archives_scanned": archives, "per_type_cap": per_type,
              "counts": {f"{s}/{op}": n for (s, op), n in sorted(counts.items())},
              "rejected": dict(rejected), "model_calls": 0}
    (output / "candidates-private.json").write_text(json.dumps(candidates, ensure_ascii=False, indent=2))
    (output / "discovery.json").write_text(json.dumps(report, indent=2))
    return report


def structural_case(record: dict[str, Any], events: dict[str, Any], before: str, after: str) -> dict:
    """Mirror ``refactoring_mixed_prepare.audit`` case construction (minus its exposure
    screen, which rejects training data by design)."""
    from llm_ontology.benchmarks import refactoring_execution as ex
    from llm_ontology.benchmarks import refactoring_structural as structural

    event = structural.select_event(events.get("events", []), record["refactoring_type"], before, after,
        description=record.get("selected_description") or (
            record.get("description") if record["source"] == "marv" else None))
    target = {"method": "", "start": min(r["startLine"] for r in event["left"]),
              "end": max(r["endLine"] for r in event["left"])}
    request = event["description"]
    if event["type"] == "Extract Variable":
        initializer = structural.extracted_initializer(after, event)
        if initializer is None or ex.normalize_java_for_hash(initializer) not in ex.normalize_java_for_hash(before):
            raise ValueError("Ambiguous/missing extraction expression")
        request += "\nExtract exactly this original expression: " + initializer
    return {"id": record["id"], "source": record["source"], "operation": record["refactoring_type"],
            "file_path": record["file_path"], "before": before,
            "class_name": record["file_path"].removesuffix(".java").split("/")[-1],
            "target": target, "request": request, "evaluation_level": "structural",
            "commit": record.get("commit_sha"), "project": record.get("project")}


def refactoring_record(case: dict[str, Any], after: str) -> dict[str, Any]:
    """FT training record whose prompt is byte-identical to the ``ft_refactoring`` prompt."""
    from llm_ontology.benchmarks.refactoring_matrix import instruction

    output = json.dumps({"file_path": case["file_path"], "refactored_code": after}, ensure_ascii=False)
    block = _ontology_block(lambda: _ontology().refactoring_context(case))
    return {"instruction": instruction(case), "input": case["before"], "output": output,
            "domain": "refactoring", "source": case["source"], "format": FORMAT,
            "refactoring_type": case["operation"], "case_id": case["id"],
            "project": case.get("project") or case["source"] + ":" + str(case.get("commit")),
            "commit_sha": case.get("commit") or "", **block}


def refactoring_records_from_contexts(directory: Path) -> tuple[list[dict[str, Any]], Counter]:
    records, reasons = [], Counter()
    for out in sorted((directory / "contexts").iterdir()):
        if (out / "rejected.json").exists() or not (out / "events.json").exists():
            reasons["rejected_or_undetected"] += 1
            continue
        try:
            record = json.loads((out / "record-private.json").read_text())
            if record["source"] == "marv":
                record.setdefault("project", record.get("repository") or record.get("commit_link", ""))
            case = structural_case(record, json.loads((out / "events.json").read_text()),
                                   record["input"], record["output"])
            records.append(refactoring_record(case, record["output"]))
        except Exception as exc:  # one bad candidate never stops the build
            reasons[str(exc)[:80]] += 1
    return records, reasons


def build_refactoring_v3(repo: Path, raw_ml4ref: Path, work_dir: Path, out_dir: Path, *,
                         plan: dict[str, Any], train_size: int, val_size: int, per_type: int = 400,
                         max_archives: int | None = None, seed: int = 42,
                         fits: Callable[[dict], bool] | None = None,
                         onto_out_dir: Path | None = None) -> dict[str, Any]:
    """discover -> RefactoringMiner materialize -> aligned context -> eval-format records."""
    from llm_ontology.benchmarks.refactoring_mixed_prepare import contextualize, materialize

    if not (work_dir / "discovery.json").exists():
        discover_refactoring_training(repo, raw_ml4ref, work_dir, manifest=plan["cohort_manifest"],
                                      per_type=per_type, max_archives=max_archives)
    materialize(repo, work_dir, {k: v for k, v in plan.items() if k != "source_cache"})
    contextualize(work_dir, plan)
    records, reasons = refactoring_records_from_contexts(work_dir)
    return _finish(records, out_dir, {"train": train_size, "val": val_size}, seed, fits,
                   {"work_dir": str(work_dir), "rejections": dict(reasons),
                    "by_type": dict(Counter(r["refactoring_type"] for r in records))}, onto_out_dir)


# -------------------------------------------------------------------------- combined


def build_combined_v3(testing_dir: Path, refactoring_dir: Path, out_dir: Path, seed: int = 42) -> dict:
    """Row-balanced B1 mix of the two v3 datasets (token volume is reported, not balanced)."""
    stats = {}
    out_dir.mkdir(parents=True, exist_ok=True)
    for split in ("train", "val"):
        testing = _read(testing_dir / f"{split}.jsonl")
        refactoring = _read(refactoring_dir / f"{split}.jsonl")
        n = min(len(testing), len(refactoring))
        rng = random.Random(seed)
        records = rng.sample(testing, n) + rng.sample(refactoring, n)
        rng.shuffle(records)
        write_jsonl(records, out_dir / f"{split}.jsonl")
        stats[split] = _stats(records)
    (out_dir / "build_report.json").write_text(json.dumps(stats, indent=2))
    return stats


# --------------------------------------------------------------------------- shared


def token_fit(tokenizer: Any, max_seq_length: int) -> Callable[[dict], bool]:
    """Same tokenization as ``build_tokenized_training_example``; over-length records are
    DROPPED here so training never truncates a prompt or a gold answer."""
    eos = getattr(tokenizer, "eos_token", None) or ""

    def fits(record: dict) -> bool:
        prompt = tokenizer(format_prompt(record), add_special_tokens=False)["input_ids"]
        output = tokenizer(record["output"] + eos, add_special_tokens=False)["input_ids"]
        return len(prompt) + len(output) <= max_seq_length
    return fits


def _read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {"count": len(records),
            "domains": dict(Counter(r.get("domain") for r in records)),
            "sources": dict(Counter(r.get("source") for r in records)),
            "types": dict(Counter(r.get("refactoring_type") for r in records if r.get("refactoring_type"))),
            "projects": len({r.get("project") for r in records})}


def _ontology():
    from llm_ontology import ontology
    return ontology


def _ontology_block(build: Callable[[], tuple[str, dict[str, str]]]) -> dict[str, Any]:
    """Block for the v3_onto twin of a record; a failure is recorded, never raised, and
    removes the record from BOTH datasets in ``_finish``."""
    try:
        block, identity = build()
    except ImportError:  # a missing dependency (rdflib, tree-sitter) must stop the build
        raise
    except Exception as exc:  # parser/guard failures are counted in the build report
        return {"ontology_block": None, "ontology_error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    return {"ontology_block": block, "ontology_block_sha256": identity["block_sha256"],
            "ontology_schema_sha256": identity["schema_sha256"]}


ONTOLOGY_FIELDS = ("ontology_block", "ontology_error", "ontology_block_sha256", "ontology_schema_sha256")


def split_twins(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """(v3 record, v3_onto record) from one built record with an ontology block."""
    base = {k: v for k, v in record.items() if k not in ONTOLOGY_FIELDS}
    onto = {**base, "instruction": _ontology().with_ontology(base["instruction"], record["ontology_block"]),
            "format": FORMAT + "_onto", "ontology_block_sha256": record["ontology_block_sha256"],
            "ontology_schema_sha256": record["ontology_schema_sha256"]}
    return base, onto


def _finish(records: list[dict[str, Any]], out_dir: str | Path, sizes: dict[str, int], seed: int,
            fits: Callable[[dict], bool] | None, report: dict[str, Any],
            onto_out_dir: str | Path | None = None) -> dict[str, Any]:
    """Shared manifest: drop ontology failures and over-length twins, split once, write both."""
    failures = Counter(r.get("ontology_error", "missing ontology block")
                       for r in records if r.get("ontology_block") is None)
    twins = [split_twins(r) for r in records if r.get("ontology_block") is not None]
    dropped = 0
    if fits is not None:
        kept = [t for t in twins if fits(t[0]) and fits(t[1])]
        dropped, twins = len(twins) - len(kept), kept
    if not twins:
        raise ValueError("No eval-aligned records were produced; see rejections: " + json.dumps(report)[:2000])
    onto_of = {id(base): onto for base, onto in twins}
    splits = grouped_split_by_ratios([base for base, _ in twins], ratios=SPLIT_RATIOS,
                                     group_key=lambda r: record_group_key(r, GroupLevel.PROJECT), seed=seed)
    out = Path(out_dir)
    onto_out = Path(onto_out_dir) if onto_out_dir is not None else None
    for directory in (out, onto_out):
        if directory is not None:
            directory.mkdir(parents=True, exist_ok=True)
    result = {**report, "format": FORMAT, "dropped_over_token_limit": dropped,
              "dropped_ontology_failure": sum(failures.values()),
              "ontology_failures": dict(failures.most_common(20)), "splits": {}}
    manifest = []
    for split, size in sizes.items():
        chosen = splits.get(split, [])[:size]
        write_jsonl(chosen, out / f"{split}.jsonl")
        if onto_out is not None:
            write_jsonl([onto_of[id(r)] for r in chosen], onto_out / f"{split}.jsonl")
        result["splits"][split] = {**_stats(chosen), "requested": size}
        manifest += [{"case_id": r.get("case_id"), "split": split, "output_sha256": _sha(r["output"]),
                      "prompt_sha256": _sha(format_prompt(r)),
                      "onto_prompt_sha256": _sha(format_prompt(onto_of[id(r)])),
                      "ontology_block_sha256": onto_of[id(r)]["ontology_block_sha256"]} for r in chosen]
    result["manifest_sha256"] = _sha(json.dumps(manifest, sort_keys=True))
    for directory in (out, onto_out):
        if directory is not None:
            (directory / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
            (directory / "build_report.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return result
