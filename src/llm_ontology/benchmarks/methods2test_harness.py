"Verbatim extracted-method wrapping for the current Methods2Test matrix."

from __future__ import annotations

import re

from pathlib import Path


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
    production = (
        f"package {package};\n{imports}public class {name} {{\n"
        + "\n".join(copied)
        + "\n"
        + body
        + "\n}\n"
    )
    assertion_import = {
        "assertj": "import static org.assertj.core.api.Assertions.assertThat;\n",
        "hamcrest": "import static org.hamcrest.MatcherAssert.assertThat;\nimport static org.hamcrest.Matchers.*;\n",
        "jupiter": "import static org.junit.jupiter.api.Assertions.*;\n",
    }[spec["assertions"]]
    reference = (
        f"package {package};\n{imports}import org.junit.jupiter.api.Test;\n"
        + assertion_import
        + ("public class ReferenceTests {\n" + d["test_case"]["body"] + "\n}\n")
    )
    policy = {
        "method_logic": "verbatim",
        "reference_assertions": "verbatim",
        "package_inferred_from_path": package,
        "imports_added": spec["imports"],
        "fields_copied_verbatim": spec["fields"],
        "omitted_unrelated_class_members": True,
        "test_annotation_binding": "org.junit.jupiter.api.Test; simple @Test only, no expected/lifecycle conversion",
        "assertion_binding": spec["assertions"],
        "original_revision": None,
        "claim": "extracted-method harness, NOT original-project build",
    }
    return production, reference, policy
