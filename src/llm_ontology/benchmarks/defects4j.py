"""Defects4J testing protocol. Historical smoke/TestBench contracts are untouched."""
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from llm_ontology.benchmarks.defects4j_execution import (
    D4J_COMMIT, clean_env, file_sha256, run_process, write_json,
)
from llm_ontology.core.config import read_yaml
from llm_ontology.ingestion.identity import normalize_java_for_hash
from llm_ontology.ingestion.java import JavaParser
from llm_ontology.ingestion.manifest import DatasetManifest, UsageRole

PROTOCOL = "defects4j_jupiter_v1"
INSTRUCTION = (
    "Generate a complete, executable JUnit 5 test class for the supplied Java focal method. "
    "Test the public behavior, including boundary cases. Use only JUnit Jupiter and the "
    "production API. Do not use external services, reflection, files or processes."
)


class Defects4JConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol: Literal["defects4j_jupiter_v1"] = PROTOCOL
    defects4j_commit: Literal["6d54320e0db5a357f9ab38a8e4d2e5aead7e1c09"] = D4J_COMMIT
    defects4j_home: Path
    java_home: Path
    tool_paths: list[Path] = Field(default_factory=list)
    perl5lib: list[Path] = Field(default_factory=list)
    library_paths: list[Path] = Field(default_factory=list)
    work_root: Path
    junit_jar: Path
    junit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    project: str = Field(default="Lang", pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    bug_id: int = Field(default=24, ge=1, strict=True)
    focal_class: str = Field(default="org.apache.commons.lang3.math.NumberUtils",
                             pattern=r"^[A-Za-z_$][A-Za-z0-9_$]*(\.[A-Za-z_$][A-Za-z0-9_$]*)*$")
    focal_method: str = Field(default="isNumber", pattern=r"^[A-Za-z_$][A-Za-z0-9_$]*$")
    focal_parameter_types: list[str] | None = None
    java_parser_version: Literal["0.25.2"] = "0.25.2"
    repository_markers: list[str] = ["commons-lang", "apache/commons-lang", "org.apache.commons.lang3"]
    training_sources: list[Path] = Field(default_factory=lambda: [Path("data/processed/testing/train.jsonl")], min_length=1)
    validation_sources: list[Path] = Field(default_factory=lambda: [Path("data/processed/testing/val.jsonl")], min_length=1)
    checkpoint_selection_sources: list[Path] = Field(default_factory=lambda: [Path("data/processed/testing/val.jsonl")], min_length=1)
    retrieval_config: Path = Path("configs/retrieval/ollama_bge_m3_v3.yaml")
    hf_models_config: Path = Path("configs/evaluation/eval_models_v2_only.yaml")
    hf_model_name: str = Field(default="b2_testing_v2", min_length=1, max_length=100)
    generation_model_digest: str = Field(default="dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364", pattern=r"^[0-9a-f]{64}$")
    embedding_model_digest: str = Field(default="7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab", pattern=r"^[0-9a-f]{64}$")
    max_new_tokens: int = Field(default=1024, ge=1, le=4096)
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    repeats: int = Field(default=2, ge=2, le=3)
    random_seed: Literal[42] = 42

    @model_validator(mode="after")
    def require_project_specific_context(self) -> Defects4JConfig:
        if self.project != "Lang":
            if self.focal_class == "org.apache.commons.lang3.math.NumberUtils":
                raise ValueError("Non-Lang subjects require an explicit project-specific focal_class.")
            if self.repository_markers == ["commons-lang", "apache/commons-lang", "org.apache.commons.lang3"]:
                raise ValueError("Non-Lang subjects require explicit project-specific repository_markers.")
        if not self.repository_markers or any(not marker.strip() for marker in self.repository_markers):
            raise ValueError("Nonempty repository/namespace markers are required; absence is not clean.")
        return self

    @property
    def case_id(self) -> str:
        return f"{self.project}-{self.bug_id}"


def load_config(path: Path) -> Defects4JConfig:
    raw = read_yaml(path)
    for key in ("defects4j_home", "java_home", "work_root", "junit_jar"):
        raw[key] = Path(raw[key]).expanduser().resolve()
    for key in ("tool_paths", "perl5lib", "library_paths"):
        raw[key] = [Path(p).expanduser().resolve() for p in raw.get(key, [])]
    return Defects4JConfig.model_validate(raw)


def validate_subject_selection(config: Defects4JConfig) -> dict[str, Any]:
    """Read-only validation; availability of metadata is not a successful subject build."""
    head = subprocess.check_output(["git", "-C", str(config.defects4j_home), "rev-parse", "HEAD"], text=True).strip()
    if head != D4J_COMMIT:
        raise ValueError("Subject selection requires the pinned Defects4J v3.0.1 checkout.")
    projects = (config.defects4j_home / "framework/projects").resolve()
    project = (projects / config.project).resolve()
    project.relative_to(projects)
    active = project / "active-bugs.csv"
    if not project.is_dir() or not active.is_file():
        raise ValueError(f"Project {config.project!r} is unavailable in the pinned installation.")
    active.resolve().relative_to(project)
    with active.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    matching = [row for row in rows if row and row[0].strip() == str(config.bug_id)]
    if len(matching) != 1:
        raise ValueError(f"{config.case_id} is not a unique active bug; deprecated/unknown bugs are forbidden.")
    return {"project": config.project, "bug_id": config.bug_id,
            "focal_class": config.focal_class, "focal_method": config.focal_method,
            "focal_parameter_types": config.focal_parameter_types,
            "active_metadata_path": str(active), "active_metadata_sha256": file_sha256(active),
            "active_bug_row": matching[0]}


def license_inventory(checkout: Path) -> dict[str, str]:
    paths = sorted(p for p in checkout.iterdir() if p.is_file()
                   and p.name.lower().startswith(("license", "notice", "copying", "copyright")))
    if not paths:
        raise ValueError("No root license/notice inventory found; subject review is required.")
    return {p.name: file_sha256(p) for p in paths}


def require_wsl() -> None:
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        raise RuntimeError("This protocol runs only inside WSL/Linux, using .venv_wsl.")


def d4j_command(config: Defects4JConfig, arguments: list[str], cwd: Path,
                output: Path, timeout: int = 300) -> str:
    env = clean_env(config.work_root / "tool-home", config.java_home,
                    tool_paths=tuple(config.tool_paths))
    env["PERL5LIB"] = ":".join(str(p) for p in config.perl5lib)
    env["LD_LIBRARY_PATH"] = ":".join(str(p) for p in config.library_paths)
    temp = config.work_root / "tmp"
    temp.mkdir(parents=True, exist_ok=True)
    env["D4J_TMP_DIR"] = str(temp)
    result = run_process([str(config.defects4j_home / "framework/bin/defects4j"), *arguments],
                         cwd, env, timeout, output)
    write_json(output.with_suffix(".process.json"), result)
    if result["status"] != "completed" or result["returncode"] != 0:
        raise RuntimeError(f"Defects4J command failed: {result}; see {output}")
    return output.read_text(encoding="utf-8").strip()


def prepare(config: Defects4JConfig, output: Path) -> dict[str, Any]:
    """Build a fresh bounded pair after the operator reviewed source/build scripts."""
    require_wsl()
    if importlib.metadata.version("tree-sitter") != config.java_parser_version:
        raise RuntimeError("This protocol pins tree-sitter==0.25.2; 0.26.0 crashed in this WSL runtime.")
    if config.work_root.as_posix().startswith("/mnt/"):
        raise ValueError("Use native Linux storage, not the OneDrive/Windows mount.")
    head = subprocess.check_output(["git", "-C", str(config.defects4j_home),
                                    "rev-parse", "HEAD"], text=True).strip()
    if head != D4J_COMMIT:
        raise ValueError("Defects4J checkout is not pinned v3.0.1.")
    java = subprocess.check_output([str(config.java_home / "bin/java"), "-version"],
                                   stderr=subprocess.STDOUT, text=True)
    if 'version "11.' not in java:
        raise ValueError("Defects4J v3.0.1 requires Java11.")
    if file_sha256(config.junit_jar) != config.junit_sha256:
        raise ValueError("Pinned Jupiter adapter checksum mismatch.")
    subject = validate_subject_selection(config)
    active = Path(subject["active_metadata_path"])
    # Never overwrite a subject checkout; a new preparation ID means new directories.
    subject_root = config.work_root / output.parent.name
    subject_root.mkdir(parents=True, exist_ok=False)
    revisions = {}
    for version, suffix in (("fixed", "f"), ("buggy", "b")):
        checkout = subject_root / version
        logs = output.parent / "prepare" / version
        logs.mkdir(parents=True)
        d4j_command(config, ["checkout", "-p", config.project, "-v", f"{config.bug_id}{suffix}",
                             "-w", str(checkout)], subject_root, logs / "checkout.log")
        d4j_command(config, ["compile", "-w", str(checkout)], checkout, logs / "compile.log")
        exports = {}
        for prop in ("cp.compile", "cp.test", "dir.bin.classes", "dir.bin.tests", "dir.src.classes"):
            exported = logs / f"{prop}.txt"
            d4j_command(config, ["export", "-p", prop, "-o", str(exported), "-w", str(checkout)],
                         checkout, logs / f"{prop}.log")
            exports[prop] = exported.read_text().strip()
        def absolute(value: str) -> Path:
            path = Path(value)
            return (checkout / path).resolve() if not path.is_absolute() else path.resolve()
        bins = absolute(exports["dir.bin.classes"])
        test_bins = absolute(exports["dir.bin.tests"])
        dependencies = []
        for part in exports["cp.compile"].split(":"):
            if not part:
                continue
            path = absolute(part)
            if path in (bins, test_bins):
                continue
            if not path.is_file() or path.suffix != ".jar":
                raise ValueError(f"Unreviewed classpath directory/nonjar dependency: {path}")
            if path not in dependencies:
                dependencies.append(path)
        source_root = absolute(exports["dir.src.classes"])
        source_root.relative_to(checkout.resolve())
        source = (source_root / (config.focal_class.replace(".", "/") + ".java")).resolve()
        source.relative_to(source_root)
        # Original tests/patches remain evaluator-only and are not copied to the case.
        revisions[version] = {
            "checkout": str(checkout), "version": f"{config.bug_id}{suffix}", "exports": exports,
            "bin_classes": str(bins), "dependencies": [str(p) for p in dependencies],
            "dependency_hashes": sorted(file_sha256(p) for p in dependencies),
            "source": str(source), "source_sha256": file_sha256(source),
            "checkout_config_sha256": file_sha256(checkout / ".defects4j.config"),
            "revision": subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                                                text=True).strip(),
            "licenses": license_inventory(checkout),
            "production_binary_hashes": {str(p.relative_to(bins)): file_sha256(p)
                                         for p in sorted(bins.rglob("*.class"))},
        }
    fixed_source = Path(revisions["fixed"]["source"]).read_text(encoding="utf-8")
    parsed = JavaParser().parse(fixed_source)
    candidates = [m for m in parsed.methods if m.method_name == config.focal_method
                  and m.class_name == config.focal_class.rsplit(".", 1)[-1]
                  and m.package_name == config.focal_class.rpartition(".")[0]
                  and (config.focal_parameter_types is None or m.parameter_types == config.focal_parameter_types)]
    if not parsed.parse_success or len(candidates) != 1:
        raise ValueError("Focal method must resolve uniquely with the existing JavaParser.")
    method = candidates[0]
    case = {"case_id": config.case_id, "instruction": INSTRUCTION, "input_text": method.content,
            "structured_identity": {"class_name": config.focal_class, "method_name": config.focal_method},
            "metadata": {"protocol": PROTOCOL, "source_role": "fixed-production-only"}}
    method_source = "\n".join(fixed_source.splitlines()[method.start_line-1:method.end_line])
    prepared = {"protocol": PROTOCOL, "subject": subject, "case": case, "focal_method": method_source,
                "fixed_source_normalized": normalize_java_for_hash(fixed_source),
                "case_sha256": hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest(),
                "defects4j_commit": head, "java_version": java,
                "java_sha256": file_sha256(config.java_home / "bin/java"),
                "javac_sha256": file_sha256(config.java_home / "bin/javac"),
                "junit_sha256": config.junit_sha256,
                "packages": {name: importlib.metadata.version(name) for name in
                             ("tree-sitter", "tree-sitter-java", "pydantic", "torch", "transformers", "peft", "bitsandbytes", "chromadb")},
                "active_metadata_sha256": file_sha256(active),
                "active_bug_row": subject["active_bug_row"], **revisions}
    if revisions["fixed"]["dependency_hashes"] != revisions["buggy"]["dependency_hashes"]:
        raise ValueError("Fixed/buggy production dependency identities differ.")
    write_json(output, prepared)
    manifest = DatasetManifest(dataset_name="defects4j", dataset_version="3.0.1",
        source_path=str(output), source_split="active-bug-canary", usage_role=UsageRole.BENCHMARK,
        allowed_for_indexing=False, case_count=1, content_hash=file_sha256(output),
        tasks=["testing"], metadata={"protocol": PROTOCOL, "case_id": config.case_id,
                                   "defects4j_commit": head})
    write_json(output.parent / "benchmark_manifest.json", manifest.model_dump(mode="json"))
    return prepared


def verify_prepared_binding(prepared: dict[str, Any], prepared_path: Path,
                            *, expected_manifest_sha256: str | None = None) -> None:
    manifest_path = prepared_path.parent / "benchmark_manifest.json"
    if expected_manifest_sha256 is not None and file_sha256(manifest_path) != expected_manifest_sha256:
        raise ValueError("Benchmark usage manifest changed after preparation.")
    manifest = DatasetManifest.model_validate(json.loads(manifest_path.read_text(encoding="utf-8")))
    if (manifest.usage_role != UsageRole.BENCHMARK or manifest.allowed_for_indexing
            or manifest.source_paths or Path(manifest.source_path).resolve() != prepared_path.resolve()):
        raise ValueError("Prepared file is not bound to its non-indexable benchmark usage manifest.")
    if file_sha256(prepared_path) != manifest.content_hash:
        raise ValueError("Actual prepared.json digest does not match benchmark_manifest.content_hash.")
    if json.loads(prepared_path.read_text(encoding="utf-8")) != prepared:
        raise ValueError("Prepared object differs from the manifest-bound file.")


def verify_prepared(prepared: dict[str, Any], config: Defects4JConfig, *,
                    prepared_path: Path, expected_manifest_sha256: str | None = None) -> None:
    verify_prepared_binding(prepared, prepared_path, expected_manifest_sha256=expected_manifest_sha256)
    if prepared["defects4j_commit"] != D4J_COMMIT or prepared["protocol"] != PROTOCOL:
        raise ValueError("Prepared benchmark identity mismatch.")
    if prepared["case"]["case_id"] != config.case_id:
        raise ValueError("Prepared project/bug does not match the selected case.")
    identity = prepared["case"]["structured_identity"]
    if identity != {"class_name": config.focal_class, "method_name": config.focal_method}:
        raise ValueError("Prepared focal identity does not match configuration.")
    expected_case_hash = hashlib.sha256(json.dumps(prepared["case"], sort_keys=True).encode()).hexdigest()
    if expected_case_hash != prepared["case_sha256"]:
        raise ValueError("Prepared prompt case was modified.")
    current_subject = validate_subject_selection(config)
    if current_subject["active_metadata_sha256"] != prepared["active_metadata_sha256"]:
        raise ValueError("Pinned active-bug metadata changed after preparation.")
    for version in ("fixed", "buggy"):
        revision = prepared[version]
        checkout = Path(revision["checkout"])
        head = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
        if head != revision["revision"] or file_sha256(checkout / ".defects4j.config") != revision["checkout_config_sha256"]:
            raise ValueError("Prepared checkout revision/configuration changed.")
        if file_sha256(Path(revision["source"])) != revision["source_sha256"]:
            raise ValueError("Prepared subject source changed.")
        if sorted(file_sha256(Path(p)) for p in revision["dependencies"]) != revision["dependency_hashes"]:
            raise ValueError("Prepared dependencies changed.")
        bins = Path(revision["bin_classes"])
        actual = {str(p.relative_to(bins)): file_sha256(p) for p in sorted(bins.rglob("*.class"))}
        if not actual or actual != revision["production_binary_hashes"]:
            raise ValueError("Prepared production binaries changed.")
    for binary, expected in (("java", prepared["java_sha256"]), ("javac", prepared["javac_sha256"])):
        if file_sha256(config.java_home / f"bin/{binary}") != expected:
            raise ValueError("Prepared Java toolchain changed.")
    if file_sha256(config.junit_jar) != prepared["junit_sha256"] or prepared["junit_sha256"] != config.junit_sha256:
        raise ValueError("Prepared Jupiter adapter changed.")


def audit_leakage(config: Defects4JConfig, prepared: dict[str, Any], index_root: Path) -> dict[str, Any]:
    """Audit current train, validation/checkpoint selection and actual retrieval inputs.

    Current bytes cannot establish historical training/checkpoint-selection identity.
    The scientific gate remains closed even when conservative current checks pass.
    """
    source = prepared["fixed_source_normalized"]
    focal = normalize_java_for_hash(prepared["focal_method"])
    matches: list[dict[str, Any]] = []
    unknown = {role: 0 for role in ("training", "validation", "checkpoint_selection", "retrieval")}
    counts = {role: 0 for role in unknown}

    def inspect(record: dict[str, Any], identity: str, role: str) -> None:
        counts[role] += 1
        text = json.dumps(record, ensure_ascii=False).lower()
        matched = [marker for marker in config.repository_markers if marker.lower() in text]
        input_code = str(record.get("input", record.get("chroma:document", "")))
        normalized = normalize_java_for_hash(input_code)
        if normalized and len(normalized) >= 80 and (normalized in source or focal in normalized):
            matched.append("normalized-production-code")
        if matched:
            matches.append({"record": identity, "usage_role": role, "matched_by": matched})
        if not any(record.get(key) for key in ("repository", "repository_url", "project")):
            unknown[role] += 1

    source_sets = {"training": config.training_sources, "validation": config.validation_sources,
                   "checkpoint_selection": config.checkpoint_selection_sources}
    inputs: dict[str, dict[str, str]] = {}
    for role, paths in source_sets.items():
        inputs[role] = {}
        for path in paths:
            inputs[role][str(path)] = file_sha256(path)
            before = counts[role]
            with path.open(encoding="utf-8") as handle:
                for index, line in enumerate(handle):
                    if line.strip():
                        inspect(json.loads(line), f"{path}:{index+1}", role)
            if counts[role] == before:
                raise ValueError(f"Empty {role} source cannot establish leakage readiness: {path}")
    database = index_root / "chroma.sqlite3"
    with sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "SELECT c.name,e.embedding_id,m.key,m.string_value,m.int_value "
            "FROM collections c JOIN segments s ON s.collection=c.id "
            "JOIN embeddings e ON e.segment_id=s.id JOIN embedding_metadata m ON m.id=e.id "
            "ORDER BY c.name,e.id,m.key")
        current = None
        document: dict[str, Any] = {}
        metadata_digest = hashlib.sha256()
        for collection, identity, key, value, number in rows:
            group = f"{collection}:{identity}"
            metadata_digest.update(json.dumps([collection, identity, key, value, number]).encode())
            if current is not None and group != current:
                inspect(document, current, "retrieval")
                document = {}
            current = group
            document[key] = value if value is not None else number
        if current:
            inspect(document, current, "retrieval")
    if counts["retrieval"] <= 0:
        raise ValueError("Actual retrieval index contains no audited documents.")
    manifests = {p.name: file_sha256(p) for p in sorted((index_root / "manifests").glob("*.json"))}
    if set(manifests) != {"mixed.json", "testing_db.json", "refactoring_db.json"}:
        raise ValueError("Expected all three current index manifests.")
    return {"audit_schema_version": "2", "case_sha256": prepared["case_sha256"],
            "training_inputs": inputs["training"], "validation_inputs": inputs["validation"],
            "checkpoint_selection_inputs": inputs["checkpoint_selection"],
            "source_role_counts": counts,
            "index_metadata_sha256": metadata_digest.hexdigest(), "index_documents": counts["retrieval"],
            "collection_manifests": manifests, "scanned_records": sum(counts.values()), "overlaps": matches,
            "unknown_training_repository_rows": unknown["training"],
            "unknown_validation_repository_rows": unknown["validation"],
            "unknown_checkpoint_selection_repository_rows": unknown["checkpoint_selection"],
            "unknown_index_repository_rows": unknown["retrieval"],
            "current_inputs_disjoint": not matches and not any(unknown.values()),
            "historical_data_identity_verified": False,
            "scientifically_clean": False, "diagnostic_only": True,
            "limitations": ["No claim about base-model pretraining contamination.",
                            "Historical training/validation/checkpoint-selection byte identities are not verified; "
                            "current-file hashes do not retroactively prove adapter lineage.",
                            "Existing combined/refactoring FT splits contain 188 leaked train/test pairs; "
                            "the testing specialist uses separate data, not retrained here.",
                            "Missing repository lineage prevents proof of project disjointness.",
                            "A validation file reused for checkpoint selection is audited under both roles; "
                            "role counts are not unique-sample counts."]}
