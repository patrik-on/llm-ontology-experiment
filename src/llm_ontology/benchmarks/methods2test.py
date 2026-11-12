"""Extracted-method validation cases; raw EVAL is not a final test holdout.

Original focal/reference method text is never rewritten. Missing packages/imports
are explicit harness inferences. Reference content must remain evaluator-private.
"""
from __future__ import annotations

import re
from pathlib import Path

from llm_ontology.benchmarks.defects4j_execution import (
    clean_env, evaluate_revision, file_sha256, run_process, write_json,
)
from llm_ontology.inference.experiment_runner import ExperimentCase
from llm_ontology.inference.prompting import testing_bodies_one_shot_v2 as profile
from llm_ontology.inference.prompting.testing_bodies_v1 import scaffold, sha

# Bounded archive-order manual dependency shortlist, before ANY model outputs.
SPECS = {
    "79160472_49": {"imports": [], "fields": [], "assertions": "assertj"},
    "12650679_72": {"imports": ["java.util.regex.Pattern"],
                    "fields": ["NUMBER", "SEPARATOR", "NUMERIC_REGEX", "numericRegex"], "assertions": "jupiter"},
    "52804523_92": {"imports": ["java.io.Serializable"], "fields": [], "assertions": "hamcrest"},
    "56354946_19": {"imports": [], "fields": [], "assertions": "hamcrest"},
    "206427_319": {"imports": ["java.util.List", "java.util.ArrayList", "java.util.Collections",
                                  "java.util.regex.Pattern", "java.util.regex.Matcher"],
                   "fields": ["LINKS_REGEX", "LINKS_PATTERN"], "assertions": "jupiter"},
    "206427_280": {"imports": ["java.io.InputStream", "java.io.IOException", "java.io.ByteArrayInputStream"],
                   "fields": [], "assertions": "jupiter"},
}


def package_from_path(path: str) -> str:
    tail = path.split("/src/main/java/", 1)[1]
    package = str(Path(tail).parent).replace("/", ".")
    if not re.fullmatch(r"[\w$]+(?:\.[\w$]+)+", package):
        raise ValueError("Cannot infer package from source path")
    return package


def wrap_record(record: dict, spec: dict) -> tuple[str, str, dict]:
    d = record["raw"]
    package = package_from_path(d["focal_class"]["file"])
    name = d["focal_class"]["identifier"]
    fields = {f["var_name"]: f["original_string"] for f in d["focal_class"].get("fields", [])}
    imports = "".join(f"import {i};\n" for i in spec["imports"])
    copied = [fields[n] for n in spec["fields"]]
    body = d["focal_method"]["body"]
    production = f"package {package};\n{imports}public class {name} {{\n" + "\n".join(copied) + "\n" + body + "\n}\n"
    assertion_import = {
        "assertj": "import static org.assertj.core.api.Assertions.assertThat;\n",
        "hamcrest": "import static org.hamcrest.MatcherAssert.assertThat;\nimport static org.hamcrest.Matchers.*;\n",
        "jupiter": "import static org.junit.jupiter.api.Assertions.*;\n",
    }[spec["assertions"]]
    reference = f"package {package};\n{imports}import org.junit.jupiter.api.Test;\n" + assertion_import + (
        "public class ReferenceTests {\n" + d["test_case"]["body"] + "\n}\n")
    policy = {"method_logic": "verbatim", "reference_assertions": "verbatim",
              "package_inferred_from_path": package, "imports_added": spec["imports"],
              "fields_copied_verbatim": spec["fields"], "omitted_unrelated_class_members": True,
              "test_annotation_binding": "org.junit.jupiter.api.Test; simple @Test only, no expected/lifecycle conversion",
              "assertion_binding": spec["assertions"], "original_revision": None,
              "claim": "extracted-method harness, NOT original-project build"}
    return production, reference, policy


def prepare_record(record, spec, output, c, dependencies):
    output.mkdir(parents=True, exist_ok=False)
    production, reference, policy = wrap_record(record, spec)
    d = record["raw"]
    name = d["focal_class"]["identifier"]
    source = output / (name + ".java")
    source.write_text(production)
    (output / "reference-private.java").write_text(reference)
    write_json(output / "raw-private.json", record)
    classes = output / "production-classes"
    classes.mkdir()
    compilation = run_process([str(c.java_home / "bin/javac"), "-g", "-encoding", "UTF-8", "-proc:none",
                               "-d", str(classes), str(source)], output,
                              clean_env(output / "home", c.java_home), c.timeout_seconds,
                              output / "production-compile.log")
    if compilation.get("returncode") != 0:
        write_json(output / "exclusion.json", {"reason": "production_compile", "result": compilation})
        return None
    revision = {"bin_classes": str(classes), "dependencies": dependencies}
    oracle = evaluate_revision(reference, revision, output=output / "reference", java_home=c.java_home,
                               junit_jar=c.junit_jar, junit_sha256=c.junit_sha256, timeout=c.timeout_seconds)
    if oracle["status"] != "passed" or oracle.get("console_summary", {}).get("tests_started", 0) <= 0:
        write_json(output / "exclusion.json", {"reason": "reference_not_positive_pass", "result": oracle})
        return None
    fqn = policy["package_inferred_from_path"] + "." + name
    case = ExperimentCase(case_id=record["id"], instruction="Generate Java Jupiter tests.", input_text=production,
                          project_context="Focal public API: " + fqn + "." + d["focal_method"]["full_signature"]
                          + ". Only supplied extracted class/JDK/Jupiter APIs are available. Original unrelated methods are not supplied.",
                          structured_identity={"repository": d["repository"]["url"], "project": str(d["repository"]["repo_id"]),
                                               "class_name": fqn, "method_name": d["focal_method"]["identifier"]},
                          metadata={"dataset_version": "methods2test-unused-eval-v1", "split": "eval",
                                    "usage_role": "validation", "indexing_allowed": False,
                                    "protocol": "methods2test_eval_five_v1"})
    empty = scaffold(case)
    case = profile.apply_profile(case)
    write_json(output / "case.json", case.model_dump(mode="json"))
    (output / "scaffold.java").write_text(empty)
    prepared = {"id": record["id"], "revision": revision, "focal_class": fqn,
                "focal_method": d["focal_method"]["identifier"], "repository": d["repository"]["url"],
                "project_id": str(d["repository"]["repo_id"]), "archive_member": record["member"],
                "production_sha256": sha(production), "raw_member_reserialized_sha256": file_sha256(output / "raw-private.json"),
                "reference_sha256": sha(reference), "wrapping_policy": policy, "production_compile": compilation,
                "source_class_path": d["focal_class"]["file"], "source_test_path": d["test_class"]["file"],
                "reference_status": oracle["status"], "reference_tests": oracle["console_summary"]["tests_started"]}
    write_json(output / "prepared.json", prepared)
    return prepared
