"""Deterministic bounded official-EVAL preparation; never dispatches a model.

Only verbatim methods and referenced rich fields; no synthetic helpers, stubs,
annotation removal or semantic repairs. javac is the dependency arbiter.
"""

from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tarfile
from datetime import datetime, timezone

from llm_ontology.benchmarks.java_execution import (
    file_sha256,
    evaluate_revision,
    write_json,
    run_process,
    clean_env,
)
from llm_ontology.benchmarks.methods2test_harness import wrap_record
from llm_ontology.inference.experiment_runner import ExperimentCase
from llm_ontology.inference.prompting import testing_bodies_one_shot_v2 as profile
from llm_ontology.inference.prompting.testing_bodies_v1 import scaffold, sha
from llm_ontology.benchmarks.matrix_support import runtime
from llm_ontology.benchmarks.methods2test_metrics import measure
from llm_ontology.core.paths import expand_placeholders
from llm_ontology.ingestion.identity import normalize_java_for_hash, java_code_hash

CONFIG = Path("configs/benchmarks/testing_matrix_v1.json")
ARCHIVE = Path("data/raw/methods2test/dataset/eval.tar.bz2")
# Explicit JDK packages only. Imports chosen by referenced lexical simple names,
# not a wildcard dependency injection. Ambiguous collision types are rejected.
JDK = {
    "java.util": "List ArrayList LinkedList Set HashSet LinkedHashSet TreeSet SortedSet NavigableSet Map HashMap LinkedHashMap TreeMap SortedMap NavigableMap Collection Collections Arrays Objects Optional Iterator ListIterator Comparator Enumeration Locale StringTokenizer UUID Date Calendar GregorianCalendar TimeZone BitSet Random Vector Stack Queue Deque ArrayDeque Properties",
    "java.util.regex": "Pattern Matcher PatternSyntaxException",
    "java.io": "Serializable InputStream OutputStream ByteArrayInputStream ByteArrayOutputStream Reader Writer StringReader StringWriter IOException EOFException DataInputStream DataOutputStream UnsupportedEncodingException",
    "java.nio": "ByteBuffer CharBuffer ByteOrder Buffer",
    "java.nio.charset": "Charset StandardCharsets CharacterCodingException",
    "java.math": "BigInteger BigDecimal MathContext RoundingMode",
    "java.text": "ParseException DecimalFormat NumberFormat SimpleDateFormat MessageFormat",
    "java.net": "URI URISyntaxException URL MalformedURLException URLEncoder URLDecoder",
    "java.util.concurrent": "TimeUnit ConcurrentHashMap",
    "java.util.function": "Function Predicate Supplier Consumer",
    "java.util.stream": "Stream Collectors IntStream",
    "java.time": "Instant LocalDate LocalTime LocalDateTime ZoneId ZoneOffset Duration Period",
    "java.time.format": "DateTimeFormatter DateTimeParseException",
}
IMPORTS = {name: package + "." + name for package, names in JDK.items() for name in names.split()}
DANGEROUS = re.compile(
    r"\b(?:System|Runtime|ProcessBuilder|Thread|ClassLoader|File|Files|Paths|Socket|ServerSocket|URLClassLoader|URL|URLConnection|HttpURLConnection|HttpClient|PrintWriter|PrintStream|FileReader|FileWriter|FileInputStream|FileOutputStream|RandomAccessFile|Scanner|Desktop|Robot|Class|Method|Field|Constructor|AccessibleObject|MethodHandles|ObjectInputStream|ObjectOutputStream|Unsafe)\b|java\.lang\.reflect|\b(?:while\s*\(\s*true|for\s*\(\s*;)"
)


def words(text):
    # Ignore comments/literals when deciding required fields/imports/security.
    text = re.sub(
        r""""(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|/\*.*?\*/|//[^\n]*""", " ", text, flags=re.S
    )
    return set(re.findall(r"\b[A-Za-z_$][\w$]*\b", text))


def infer_spec(d):
    focal, gold = d["focal_method"]["body"], d["test_case"]["body"]
    if not re.search(r"\bpublic\s+static\b", focal):
        raise ValueError("not_public_static")
    if (
        d["focal_class"].get("superclass")
        or d["focal_class"].get("interfaces")
        or d["test_class"].get("superclass")
        or d["test_class"].get("interfaces")
    ):
        raise ValueError("inheritance_or_interface_context")
    annotations = re.findall(r"@([\w.]+)(\s*\()?", gold)
    if annotations != [("Test", "")]:
        raise ValueError("non_simple_test_annotation")
    if re.search(r"@(?!Override\b)\w+", focal):
        raise ValueError("focal_annotation_dependency")
    if DANGEROUS.search(" ".join(words(focal + gold))):
        raise ValueError("effects_or_unsafe_API")
    name = d["focal_method"]["identifier"]
    if name in (
        "assertThat",
        "assertTrue",
        "assertFalse",
        "assertEquals",
        "assertNull",
        "assertNotNull",
        "fail",
    ):
        raise ValueError("assertion_API_name_collision")
    if not re.search(r"\bassert[A-Z]\w*\s*\(", gold):
        raise ValueError("no_assertion")
    if not re.search(
        r"\b"
        + re.escape(d["focal_class"]["identifier"])
        + r"\s*\.\s*"
        + re.escape(name)
        + r"\s*\(",
        gold,
    ):
        raise ValueError("no_qualified_focal_call")
    fields = {f["var_name"]: f["original_string"] for f in d["focal_class"].get("fields", [])}
    chosen = []
    needed = words(focal)
    while True:
        extra = [n for n in fields if n in needed and n not in chosen]
        if not extra:
            break
        chosen.extend(extra)
        needed.update(words("\n".join(fields[n] for n in extra)))
    copied = "\n".join(fields[n] for n in chosen)
    if DANGEROUS.search(" ".join(words(copied))):
        raise ValueError("effects_in_fields")
    # Rich records contain signatures, not helper bodies. Missing helpers are
    # rejected by javac; never recreated from guessed semantics.
    allwords = words(focal + gold + copied)
    if allwords & {"Date", "Optional", "Function", "Predicate", "Supplier", "Consumer"}:
        raise ValueError("unresolved_ambiguous_JDK_binding")
    if re.search(
        r"\bnew\s+" + re.escape(d["focal_class"]["identifier"]) + r"\s*\(", focal + copied
    ):
        raise ValueError("unavailable_original_constructor_semantics")
    production_words = words(focal + copied)
    if "assertThat" in allwords:
        if re.search(r"assertThat\s*\([^;]+\)\s*\.", gold, re.S):
            assertion = "assertj"
        else:
            assertion = "hamcrest"
    else:
        assertion = "jupiter"
    return {
        "imports": sorted(IMPORTS[n] for n in production_words if n in IMPORTS),
        "reference_imports": sorted(IMPORTS[n] for n in allwords if n in IMPORTS),
        "fields": chosen,
        "assertions": assertion,
    }


def historical_selection_ids(current_root=None):
    result = set(expand_placeholders(json.loads(CONFIG.read_text())).get("prior_explored_case_ids", []))
    for p in Path("artifacts/evaluation/runs").glob("*/selection.json"):
        if current_root is not None and p.parent.resolve() == current_root.resolve():
            continue
        try:
            result.update(json.loads(p.read_text()).get("ids", []))
        except (ValueError, OSError):
            pass
    return result


def snapshots(current_root=None):
    normalized = []
    projects = set()
    ids = set()
    pins = {}
    repositories = set()
    # v3 = the eval-aligned FT data of the ontology run (v3_onto holds the same records).
    for folder in ["testing", "refactoring_ml4ref", "refactoring_marv", "refactoring", "combined",
                   "v3/testing", "v3/refactoring"]:
        for split in ["train", "val"]:
            p = Path(f"data/processed/{folder}/{split}.jsonl")
            pins[str(p)] = file_sha256(p)
            with p.open() as f:
                for line in f:
                    d = json.loads(line)
                    normalized.extend(normalize_java_for_hash(d[k]) for k in ["input", "output"])
                    source = Path(d.get("source_file", ""))
                    projects.add(source.parent.name)
                    ids.add(source.stem.replace("_corpus", ""))
                    for k, v in d.items():
                        if k in (
                            "repository",
                            "repository_url",
                            "repo_url",
                            "project",
                            "project_name",
                        ):
                            repositories.add(str(v).lower().rstrip("/"))
    # Materialized testing TEST and prior explored cases are excluded too, without
    # claiming they trained the adapter.
    with Path("data/processed/testing/test.jsonl").open() as f:
        for line in f:
            ids.add(Path(json.loads(line).get("source_file", "")).stem.replace("_corpus", ""))
    ids.update(historical_selection_ids(current_root))
    db = Path("data/chroma/ollama_bge_m3_v3/chroma.sqlite3")
    con = sqlite3.connect("file:" + str(db) + "?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    docs = 0
    for (doc,) in con.execute(
        "SELECT m.string_value FROM embedding_metadata m JOIN embeddings e ON e.id=m.id JOIN segments s ON s.id=e.segment_id JOIN collections c ON c.id=s.collection WHERE c.name='mixed' AND m.key='chroma:document'"
    ):
        docs += 1
        if "Production Java code:" in doc:
            a, b = doc.split("Production Java code:", 1)[1].split("Corresponding test code:", 1)
        else:
            a, b = doc.split("Original Java code:", 1)[1].split("Refactored Java code:", 1)
            b = b.split("Change summary or diff:", 1)[0]
        normalized.extend([normalize_java_for_hash(a), normalize_java_for_hash(b)])
    for key, value in con.execute(
        "SELECT m.key, m.string_value FROM embedding_metadata m JOIN embeddings e ON e.id=m.id JOIN segments s ON s.id=e.segment_id JOIN collections c ON c.id=s.collection WHERE c.name='mixed' AND m.key IN ('project','project_name','repository','repository_url','repo_url','source_project','source_uri')"
    ):
        if value:
            repositories.add(value.lower().rstrip("/").removesuffix(".git"))
    con.close()
    manifest_dir = db.parent / "manifests"
    pins.update({str(p): file_sha256(p) for p in manifest_dir.glob("*.json")})
    return normalized, projects, ids, pins, docs, repositories


def audit_record(record, normalized, projects, repositories):
    d = record["raw"]
    pid = str(d["repository"]["repo_id"])
    repo = d["repository"]["url"].lower().rstrip("/").removesuffix(".git")
    if pid in projects or repo in repositories or repo.rsplit("/", 1)[-1] in repositories:
        raise ValueError("project_exposed_trainval")
    cp = Path(f"data/raw/methods2test/corpus/json/eval/{pid}/{record['id']}_corpus.json")
    if not cp.exists():
        raise ValueError("missing_corpus")
    co = json.loads(cp.read_text())
    for rich, key in [("focal_method", "src_fm"), ("test_case", "target")]:
        body = d[rich]["body"]
        if java_code_hash(body) != java_code_hash(co[key]):
            raise ValueError("rich_corpus_" + rich + "_mismatch")
        n = normalize_java_for_hash(body)
        if any(n in x or x in n for x in normalized if x):
            raise ValueError(rich + "_exposed_containment")
    return {
        "id": record["id"],
        "focal_hash": java_code_hash(d["focal_method"]["body"]),
        "reference_hash": java_code_hash(d["test_case"]["body"]),
        "corpus_path": str(cp),
        "corpus_sha256": file_sha256(cp),
        "checks": {
            "project_absent_trainval": True,
            "focal_absent": True,
            "reference_absent": True,
            "rich_corpus_focal_equal": True,
            "rich_corpus_reference_equal": True,
        },
    }


def descriptor(prepared, c, output):
    result = run_process(
        [
            str(c.java_home / "bin/javap"),
            "-classpath",
            prepared["revision"]["bin_classes"],
            "-p",
            "-s",
            prepared["focal_class"],
        ],
        output,
        clean_env(output / "javap-home", c.java_home),
        30,
        output / "javap.log",
    )
    if result.get("returncode") != 0:
        raise ValueError("javap_failed")
    text = (output / "javap.log").read_text()
    entries = []
    for declaration, desc in re.findall(r"([^\n]+)\n\s+descriptor:\s*(\S+)", text):
        if re.search(r"\b" + re.escape(prepared["focal_method"]) + r"\(", declaration):
            entries.append(desc)
    if len(entries) != 1:
        raise ValueError("ambiguous_method_descriptor")
    return prepared["focal_method"] + entries[0]


def general_wrap_record(record, spec):
    production, reference, policy = wrap_record(record, spec)
    missing = [i for i in spec["reference_imports"] if i not in spec["imports"]]
    package_line, rest = reference.split("\n", 1)
    reference = package_line + "\n" + "".join("import " + i + ";\n" for i in missing) + rest
    policy["reference_only_imports"] = missing
    policy["wrapper_policy_version"] = "jdk-split-imports-v2"
    return production, reference, policy


def prepare_record_general(record, spec, output, c, dependencies):
    output.mkdir(parents=True, exist_ok=False)
    production, reference, policy = general_wrap_record(record, spec)
    d = record["raw"]
    name = d["focal_class"]["identifier"]
    source = output / (name + ".java")
    write_json(
        output / "source-review-before-execution.json",
        {
            "production_sha256": sha(production),
            "reference_sha256": sha(reference),
            "policy": "conservative_JDK_local_review_v2",
            "not_os_sandbox": True,
        },
    )
    source.write_text(production)
    (output / "reference-private.java").write_text(reference)
    write_json(output / "raw-private.json", record)
    classes = output / "production-classes"
    classes.mkdir()
    compilation = run_process(
        [
            str(c.java_home / "bin/javac"),
            "-g",
            "-encoding",
            "UTF-8",
            "-proc:none",
            "-d",
            str(classes),
            str(source),
        ],
        output,
        clean_env(output / "home", c.java_home),
        c.timeout_seconds,
        output / "production-compile.log",
    )
    if compilation.get("returncode") != 0:
        write_json(
            output / "exclusion.json", {"reason": "production_compile", "result": compilation}
        )
        return None
    revision = {"bin_classes": str(classes), "dependencies": dependencies}
    oracle = evaluate_revision(
        reference,
        revision,
        output=output / "reference",
        java_home=c.java_home,
        junit_jar=c.junit_jar,
        junit_sha256=c.junit_sha256,
        timeout=c.timeout_seconds,
    )
    if (
        oracle["status"] != "passed"
        or oracle.get("console_summary", {}).get("tests_started", 0) <= 0
    ):
        write_json(
            output / "exclusion.json", {"reason": "reference_not_positive_pass", "result": oracle}
        )
        return None
    fqn = policy["package_inferred_from_path"] + "." + name
    case = ExperimentCase(
        case_id=record["id"],
        instruction="Generate Java Jupiter tests.",
        input_text=production,
        project_context="Focal public API: "
        + fqn
        + "."
        + d["focal_method"]["full_signature"]
        + ". Only supplied extracted class/JDK/Jupiter APIs are available. Original unrelated methods are not supplied.",
        structured_identity={
            "repository": d["repository"]["url"],
            "project": str(d["repository"]["repo_id"]),
            "class_name": fqn,
            "method_name": d["focal_method"]["identifier"],
        },
        metadata={
            "dataset_version": "methods2test-unused-eval-v1",
            "split": "eval",
            "usage_role": "validation",
            "indexing_allowed": False,
            "protocol": "methods2test_eval_five_v1",
        },
    )
    empty = scaffold(case)
    case = profile.apply_profile(case)
    write_json(output / "case.json", case.model_dump(mode="json"))
    (output / "scaffold.java").write_text(empty)
    prepared = {
        "id": record["id"],
        "revision": revision,
        "focal_class": fqn,
        "focal_method": d["focal_method"]["identifier"],
        "repository": d["repository"]["url"],
        "project_id": str(d["repository"]["repo_id"]),
        "archive_member": record["member"],
        "production_sha256": sha(production),
        "raw_member_reserialized_sha256": file_sha256(output / "raw-private.json"),
        "reference_sha256": sha(reference),
        "wrapping_policy": policy,
        "production_compile": compilation,
        "source_class_path": d["focal_class"]["file"],
        "source_test_path": d["test_class"]["file"],
        "reference_status": oracle["status"],
        "reference_tests": oracle["console_summary"]["tests_started"],
    }
    write_json(output / "prepared.json", prepared)
    return prepared


def prepare(root, *, config=None):
    root.mkdir(parents=True, exist_ok=True)
    if (root / "freeze.json").exists() or list(root.glob("cases/*/predictions/*/dispatch.json")):
        raise ValueError("No preparation after freeze or generation")
    config = expand_placeholders(json.loads(CONFIG.read_text())) if config is None else dict(config)
    cap = config["selection_screen"]
    c = runtime()
    write_json(root / "selection_protocol.json", config)
    normalized, projects, excluded, pins, docs, repos = snapshots(root)
    deps = expand_placeholders(json.loads(Path("configs/evaluation/methods2test_assertions_v1.json").read_text()))
    for v in deps.values():
        if file_sha256(Path(v["path"])) != v["sha256"]:
            raise ValueError("assertion_identity_changed")
    reasons = Counter()
    project_counts = Counter()
    selected = []
    audits = []
    seen = set()
    scanned = 0
    size = 0
    attempts = 0

    def progress(state):
        write_json(
            root / "preparation_progress.json",
            {
                "state": state,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "records": scanned,
                "payload_bytes": size,
                "attempted_compiles": attempts,
                "ready": len(selected),
                "projects": dict(project_counts),
                "rejections": dict(reasons),
                "model_calls": 0,
            },
        )

    progress("snapshot_checks_complete")
    with tarfile.open(ARCHIVE, "r|bz2") as tar:
        for member in tar:
            if not member.isfile() or not member.name.endswith(".json"):
                continue
            scanned += 1
            size += member.size
            if scanned > cap["maximum_records"] or size > cap["maximum_payload_bytes"]:
                reasons["scan_cap"] = 1
                break
            if scanned % 500 == 0:
                progress("streaming")
                print("SCREEN", scanned, "READY", len(selected), "COMPILES", attempts, flush=True)
            ident = Path(member.name).stem
            if ident in excluded:
                reasons["previously_materialized_or_explored"] += 1
                continue
            if member.size > cap["maximum_member_bytes"]:
                reasons["member_size"] += 1
                continue
            payload = tar.extractfile(member).read()
            d = json.loads(payload)
            pid = str(d["repository"]["repo_id"])
            if project_counts[pid] >= cap["project_cap"]:
                reasons["project_cap"] += 1
                continue
            focal = d["focal_method"]["body"]
            gold = d["test_case"]["body"]
            if (
                len(focal.encode()) > cap["focal_bytes"]
                or len(gold.encode()) > cap["reference_bytes"]
            ):
                reasons["length"] += 1
                continue
            record = {"id": ident, "member": member.name, "raw": d}
            try:
                spec = infer_spec(d)
                if "/src/main/java/" not in d["focal_class"]["file"]:
                    raise ValueError("unsupported_source_package_path")
                fingerprint = java_code_hash(focal)
                if fingerprint in seen:
                    raise ValueError("duplicate_focal")
                audit = audit_record(record, normalized, projects, repos)
            except (ValueError, KeyError) as exc:
                reasons[str(exc)] += 1
                continue
            attempts += 1
            out = root / "candidates" / ident
            try:
                if (out / "exclusion.json").exists():
                    reasons[json.loads((out / "exclusion.json").read_text())["reason"]] += 1
                    continue
                if (out / "prepared.json").exists():
                    prepared = json.loads((out / "prepared.json").read_text())
                    if prepared.get("archive_member_sha256") != hashlib.sha256(payload).hexdigest():
                        raise ValueError("incomplete_or_changed_prepared_candidate")
                elif out.exists():
                    reasons["previous_incomplete_wrapper_rejected"] += 1
                    continue
                else:
                    prepared = prepare_record_general(
                        record, spec, out, c, [v["path"] for v in deps.values()]
                    )
                if prepared is None:
                    reasons[json.loads((out / "exclusion.json").read_text())["reason"]] += 1
                    continue
                if not prepared.get("focal_method_name"):
                    prepared["focal_method_name"] = prepared["focal_method"]
                    prepared["focal_method"] = descriptor(prepared, c, out)
                write_json(out / "prepared.json", prepared)
                coverage = (
                    json.loads((out / "reference-coverage/coverage.json").read_text())
                    if (out / "reference-coverage/coverage.json").exists()
                    else measure(
                        (out / "reference-private.java").read_text(),
                        prepared,
                        out / "reference-coverage",
                    )
                )
                if (
                    coverage["status"] != "passed"
                    or not coverage["coverage"]
                    or not coverage["focal_invoked"]
                ):
                    raise ValueError("reference_focal_instrumentation")
                # Pin the actual JVM descriptor and immutable instrumented denominators.
                prepared["archive_member_sha256"] = hashlib.sha256(payload).hexdigest()
                prepared["selection_audit"] = audit
                prepared["reference_coverage"] = coverage["coverage"]
                # Metadata refers to this new cohort; input body/scaffold unchanged.
                cp = out / "case.json"
                case = json.loads(cp.read_text())
                case["metadata"].update(
                    dataset_version=config["dataset"], protocol=config["protocol"]
                )
                write_json(cp, case)
                write_json(out / "prepared.json", prepared)
                (out / "rich-original-private.json").write_bytes(payload)
                # Keep paths stable; case directories are links to prepared candidates.
                (root / "cases").mkdir(exist_ok=True)
                if not (root / "cases" / ident).exists():
                    (root / "cases" / ident).symlink_to(out, target_is_directory=True)
                selected.append(prepared)
                audits.append(audit)
                seen.add(fingerprint)
                project_counts[pid] += 1
                print(
                    "READY",
                    len(selected),
                    ident,
                    d["repository"]["url"],
                    prepared["focal_method"],
                    flush=True,
                )
                progress("preparing")
                if len(selected) == config["cases"]:
                    break
            except ValueError as exc:
                reasons[str(exc)] += 1
    selection = {
        "role": "validation",
        "split": "official eval",
        "indexing_allowed": False,
        "ids": [p["id"] for p in selected],
        "cases": selected,
        "before_model_outputs": True,
        "official_test_reserved": True,
        "selection_policy": config["selection"],
        "rejections": dict(reasons),
    }
    write_json(root / "selection.json", selection)
    write_json(
        root / "leakage_audit.json",
        {
            "candidates": audits,
            "snapshots": pins,
            "rag_documents": docs,
            "scope": "Current train/validation/checkpoint and actual both code sides of mixed union; historical training bytes/base pretraining unknown.",
            "checked_before_model_calls": True,
        },
    )
    progress("ready" if len(selected) == config["cases"] else "insufficient_eligible_cases")
    if len(selected) != config["cases"]:
        raise RuntimeError(
            f"Only {len(selected)} honestly prepared; no partial generation permitted"
        )
    print("PREPARED", len(selected), "PROJECTS", len(project_counts), "MODEL_CALLS 0", flush=True)
