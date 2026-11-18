"""Model-free, provenance-preserving candidate discovery. Candidates are NOT accepted tasks."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import re
import zipfile

from llm_ontology.datasets.ml4refactoring import extract_refactoring_type
from llm_ontology.ingestion.identity import normalize_java_for_hash

QUOTAS = {
    "swe": {"total": 5},
    "marv": {"Extract Method": 9, "Rename Method": 9, "Rename Variable": 9, "Remove Parameter": 8},
    "ml4refactoring": {name: 10 for name in (
        "Extract Variable", "Inline Variable", "Rename Parameter", "Rename Class",
        "Parameterize Variable", "Replace Variable With Attribute")},
}


def digest(text):
    return hashlib.sha256(normalize_java_for_hash(text).encode()).hexdigest()


def exposure(repo):
    """Screen actual train/validation/checkpoint-selection and stored retrieval pairs."""
    paths = sorted({*repo.glob("data/processed/**/train.jsonl"),
                    *repo.glob("data/processed/**/val.jsonl"),
                    *repo.glob("artifacts/**/production_corpus/*.jsonl")})
    hashes, commits, projects, inputs = set(), set(), set(), []
    for path in paths:
        inputs.append({"path": str(path.relative_to(repo)),
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            for key in ("input", "output"):
                if record.get(key):
                    hashes.add(digest(record[key]))
            if record.get("commit_sha"):
                commits.add(record["commit_sha"].lower())
            if record.get("project"):
                projects.add(record["project"].lower())
    return hashes, commits, projects, inputs


def discover(repo, raw, output, per_type=150):
    """Cap raw reservoir per type, not a claim of exhaustive clean availability."""
    output.mkdir(parents=True, exist_ok=False)
    hashes, commits, projects, inputs = exposure(repo)
    candidates, rejected, counts = [], Counter(), Counter()
    seen = set()

    def add(record, provenance):
        source, operation = record["source"], record["refactoring_type"]
        if operation not in QUOTAS.get(source, {}):
            return
        before, after = record["input"], record["output"]
        pair = (digest(before), digest(after))
        if pair[0] == pair[1]:
            rejected["no_op"] += 1
        elif record.get("commit_sha", "").lower() in commits or any(h in hashes for h in pair):
            rejected["exposure_overlap"] += 1
        elif pair in seen:
            rejected["duplicate_pair"] += 1
        elif max(len(before), len(after)) > 18000:
            rejected["large_file"] += 1
        else:
            seen.add(pair)
            ident = source + "-" + hashlib.sha256(json.dumps([provenance, pair], sort_keys=True).encode()).hexdigest()[:24]
            candidates.append({**record, "id": ident, "provenance": provenance})
            counts[source, operation] += 1

    for source, directory in (("marv", "refactoring_marv"), ("ml4refactoring", "refactoring_ml4ref")):
        path = repo / "data/processed" / directory / "test.jsonl"
        inputs.append({"path": str(path.relative_to(repo)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        for number, line in enumerate(path.read_text().splitlines(), 1):
            record = json.loads(line)
            if source == "marv" and record.get("evaluation_votes") != [1, 1]:
                continue
            if source == "ml4refactoring":
                record["refactoring_type"] = extract_refactoring_type(record["file_path"])
            add(record, {"path": str(path.relative_to(repo)), "line": number})
    archives = 0
    for path in sorted(raw.glob("*.zip")):
        if all(counts["ml4refactoring", op] >= per_type for op in QUOTAS["ml4refactoring"]):
            break
        # Cheap project exclusion before opening large archives.
        if path.stem.removeprefix("apache-").lower() in projects:
            continue
        archives += 1
        if archives % 100 == 0:
            print("DISCOVER", archives, dict((op, counts["ml4refactoring", op]) for op in QUOTAS["ml4refactoring"]), flush=True)
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                for name in sorted(names):
                    if "/before-refactoring/" not in name or "-astc" in name or ".java" not in name:
                        continue
                    operation = extract_refactoring_type(name.split("/")[-1])
                    if operation not in QUOTAS["ml4refactoring"] or counts["ml4refactoring", operation] >= per_type:
                        continue
                    after_name = name.replace("/before-refactoring/", "/after-refactoring/")
                    if after_name not in names or max(archive.getinfo(n).file_size for n in (name, after_name)) > 18000:
                        continue
                    prefix, file_path = name.split("/before-refactoring/", 1)
                    match = re.search(r"/([^/]+)/storage/([^/]+)$", prefix)
                    if not match or match[1].lower() in projects:
                        continue
                    add({"source": "ml4refactoring", "refactoring_type": operation,
                         "project": match[1], "commit_sha": match[2], "file_path": file_path,
                         "input": archive.read(name).decode("utf-8"),
                         "output": archive.read(after_name).decode("utf-8")},
                        {"archive": str(path), "before_member": name, "after_member": after_name})
        except (zipfile.BadZipFile, UnicodeDecodeError) as exc:
            rejected[type(exc).__name__] += 1
    report = {"status": "candidates_only", "model_calls": 0, "quotas": QUOTAS,
              "raw_archives_scanned": archives, "reservoir_cap_per_type": per_type,
              "counts": {s: {op: counts[s, op] for op in ops} for s, ops in QUOTAS.items() if s != "swe"},
              "excluded": dict(rejected), "exposure_inputs": inputs,
              "caveat": "Exact normalized before/after and commit screen, raw unused-project preference; not a near-clone or pretraining contamination certificate."}
    (output / "candidates-private.json").write_text(json.dumps(candidates, ensure_ascii=False, indent=2))
    (output / "discovery.json").write_text(json.dumps(report, indent=2))
    return report
