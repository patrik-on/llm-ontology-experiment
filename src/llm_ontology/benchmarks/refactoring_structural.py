"""Target-bound structural checks; deliberately not a behavioral equivalence claim."""
from __future__ import annotations

from difflib import SequenceMatcher
import re
import threading

from llm_ontology.benchmarks import refactoring_execution as ex

_local = threading.local()


def parser():
    if not hasattr(_local, "parser"):
        _local.parser = ex.JavaParser().parser
    return _local.parser


def valid_java(source):
    root = parser().parse(source.encode()).root_node
    return not root.has_error and any(n.type in {"class_declaration", "interface_declaration", "enum_declaration",
                                               "record_declaration", "annotation_type_declaration"}
                                     for n in root.named_children)


def identity(event):
    """Pin the requested declaration, not every incidental usage/change in a commit."""
    keys = ("filePath", "startLine", "endLine", "startColumn", "endColumn", "codeElementType", "codeElement")
    right = [{k: r.get(k) for k in ("codeElementType", "codeElement")} for r in event.get("right", [])[:1]]
    if event["type"] in {"Remove Parameter", "Inline Variable"}:
        right = []  # No requested new declaration; the original entity pins the target.
    elif right and event["type"] in {"Rename Method", "Rename Variable", "Rename Parameter"}:
        value = right[0].get("codeElement") or ""
        right[0]["codeElement"] = (value.split("(", 1)[0].split()[-1] if event["type"] == "Rename Method"
                                   else value.split(":", 1)[0].strip())
    return {"type": event["type"],
            "left": [{k: r.get(k) for k in keys} for r in event.get("left", [])[:1]],
            "right": right}


def within_scope(before, after, event):
    """Unchanged tokens outside the detected operation's declared code ranges.

    Line masks alone allow unrelated edits on the same line. Compare token streams
    outside exact CodeRange column spans instead. Newline/formatting/comments ignored.
    """
    if event["type"].startswith("Rename "):
        old = event["left"][0].get("codeElement", "")
        new = event["right"][0].get("codeElement", "")
        if event["type"] == "Rename Method":
            old, new = (s.split("(", 1)[0].split()[-1] for s in (old, new))
        else:
            old, new = (s.split(":", 1)[0].strip().split(".")[-1] for s in (old, new))
        if not all(re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", s) for s in (old, new)) or old == new:
            return False
        left = ex.normalize_java_for_hash(before).split()
        right = ex.normalize_java_for_hash(after).split()
        pure = all(tag == "equal" or (tag == "replace" and left[a:b] == [old] * (b-a)
                                    and right[c:d] == [new] * (d-c) and b-a == d-c)
                   for tag, a, b, c, d in SequenceMatcher(None, left, right, autojunk=False).get_opcodes())
        if not pure:
            return False
        # Bind edits to this event, not another same-named entity in the file.
        def masked(source, ranges):
            lines = source.splitlines(keepends=True)
            offsets, total = [], 0
            for line in lines:
                offsets.append(total)
                total += len(line)
            spans = []
            for loc in ranges:
                def pos(line, col):
                    return offsets[line-1] + len(lines[line-1].encode("utf-16-le")[:(col-1)*2].decode("utf-16-le"))
                spans.append((pos(loc["startLine"], loc["startColumn"]), pos(loc["endLine"], loc["endColumn"])))
            # Keep actual outside tokens, rather than text-replacing names globally.
            chunks = []
            begin = 0
            for start, end in sorted(spans):
                if end <= begin:
                    continue
                if start > begin:
                    chunks.append(source[begin:start])
                begin = max(begin, end)
            chunks.append(source[begin:])
            return ex.normalize_java_for_hash(" ".join(chunks))
        # Some unit-level callers only supply entity identities, not locations.
        if not all("startLine" in r for side in ("left", "right") for r in event[side]):
            return False
        return masked(before, event["left"]) == masked(after, event["right"])
    def outside(source, locations):
        raw = source.encode()
        tree = parser().parse(raw).root_node
        lines = source.splitlines(keepends=True)
        starts, total = [], 0
        for line in lines:
            starts.append(total)
            total += len(line)
        spans = []
        for loc in locations:
            try:
                def column(line, col):
                    # JDT columns count UTF-16 code units; Python counts code points.
                    prefix = lines[line-1].encode("utf-16-le")[:(col-1)*2].decode("utf-16-le")
                    return starts[line-1] + len(prefix)
                begin = column(loc["startLine"], loc["startColumn"])
                # RM uses 1-based columns with an exclusive end (not inclusive).
                end = column(loc["endLine"], loc["endColumn"])
            except (KeyError, IndexError, TypeError, UnicodeDecodeError):
                return None
            # RM's extracted/inlined variable range starts at the declarator,
            # not its type/modifiers. Include that declaration's AST statement.
            if "declaration" in loc.get("description", "") and "variable" in loc.get("description", ""):
                byte_start = len(source[:begin].encode())
                node = tree.descendant_for_byte_range(byte_start, byte_start)
                while node is not None and node.type not in {"local_variable_declaration", "field_declaration", "formal_parameter"}:
                    node = node.parent
                if node is not None:
                    begin = len(raw[:node.start_byte].decode())
                    end = len(raw[:node.end_byte].decode())
                    if node.type == "formal_parameter":
                        # Parameter insertion/removal necessarily inserts/removes
                        # one list delimiter too. RM reports the parameter only.
                        previous, following = node.prev_sibling, node.next_sibling
                        if previous is not None and previous.type == ",":
                            begin = len(raw[:previous.start_byte].decode())
                        elif following is not None and following.type == ",":
                            end = len(raw[:following.end_byte].decode())
            spans.append((begin, end))
        # Merge spans before replacing, since method/statement ranges overlap.
        merged = []
        for start, end in sorted(spans):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        for start, end in reversed(merged):
            source = source[:start] + " " + source[end:]
        return ex.normalize_java_for_hash(source)
    left, right = outside(before, event.get("left", [])), outside(after, event.get("right", []))
    return left is not None and right is not None and left == right


def select_event(events, operation, before=None, after=None, description=None):
    matches = [e for e in events if e["type"] == operation and e.get("left") and e.get("right")]
    if not matches:
        raise ValueError("Requested operation missing: " + operation)
    if description:
        def canonical(s):
            return re.sub(r"\s+", "", s)
        exact = [e for e in matches if canonical(e["description"]) == canonical(description)]
        if len(exact) == 1:
            return exact[0]
        ranked = sorted(((SequenceMatcher(None, canonical(description), canonical(e["description"])).ratio(), i, e)
                         for i, e in enumerate(matches)), key=lambda row: (-row[0], row[1]))
        if ranked[0][0] < .75 or (len(ranked) > 1 and ranked[0][0] - ranked[1][0] < .03):
            raise ValueError("Dataset target description is ambiguous/mismatching")
        return ranked[0][2]
    # ML4Ref supplies a type, not a unique target description. Declare one
    # deterministic concrete target from that type, independently of model output.
    return sorted(matches, key=lambda e: (e["left"][0]["startLine"], e["left"][0]["startColumn"], e["description"]))[0]


def evaluate(case, source, output, tool):
    output.mkdir(parents=True, exist_ok=False)
    result = {"source_sha256": ex.hashlib.sha256(source.encode()).hexdigest(),
              "verified_success": False, "structural_success": False,
              "behavioral_validation": "not_run", "outcomes": []}
    if not valid_java(source):
        result["status"] = "invalid_java"
    elif ex.normalize_java_for_hash(source) == ex.normalize_java_for_hash(case["before"]):
        result["status"] = "no_op"
    else:
        detected = ex.detect(case, source, output / "operation", tool)
        matching = [e for e in detected.get("events", []) if identity(e) == case["target_event"]]
        detected["matching"] = matching
        detected["status"] = ("detector_error" if detected["status"] == "detector_error" else
                              "matched" if matching else "operation_missing")
        result["operation"] = detected
        success = bool(matching)
        if success and case.get("extraction_expression"):
            success = any(ex.normalize_java_for_hash(extracted_initializer(source, e) or "")
                          == ex.normalize_java_for_hash(case["extraction_expression"]) for e in matching)
        result.update(status="detector_error" if detected["status"] == "detector_error" else
                      "structural_pass" if success else "checks_failed",
                      structural_success=success)
        result["scored_endpoint"] = "requested_operation_and_target_only"
        result["other_changes_policy"] = "not_scored"
    ex.write(output / "evaluation.json", result)
    return result


def extracted_initializer(source, event):
    loc = event["right"][0]
    name = loc.get("codeElement", "").split(":", 1)[0].strip()
    raw, values = source.encode(), []
    def visit(node):
        if node.type == "variable_declarator" and loc["startLine"] <= node.start_point.row + 1 <= loc["endLine"]:
            ident, value = node.child_by_field_name("name"), node.child_by_field_name("value")
            if value is not None and raw[ident.start_byte:ident.end_byte].decode() == name:
                values.append(raw[value.start_byte:value.end_byte].decode())
        for child in node.named_children:
            visit(child)
    visit(parser().parse(raw).root_node)
    return values[0] if len(values) == 1 else None
