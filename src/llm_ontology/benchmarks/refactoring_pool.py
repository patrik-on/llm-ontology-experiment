"""Deterministic audited SWE pool and AST-based, model-free negative controls."""
from __future__ import annotations

import json
from collections import Counter

from llm_ontology.benchmarks import refactoring_execution as ex

SUPPORTED = {"Extract Method", "Inline Method"}


def pool(repo, plan):
    dataset = repo / plan["dataset"]
    audit_path = repo / plan["overlap_cases"]
    audit = {r["id"]: r for r in json.loads(audit_path.read_text())}
    records = json.loads(dataset.read_text())
    eligible, excluded, seen = [], Counter(), set()
    for record in records:
        ident = record["uniqueId"]
        if ident in seen:
            raise ValueError("Duplicate SWE ID: " + ident)
        seen.add(ident)
        evidence = audit.get(ident)
        reason = None
        if (not evidence or evidence["commit"] != record["commitId"]
                or evidence["project"] != record["projectName"]):
            raise ValueError("Missing/mismatching overlap evidence: " + ident)
        if evidence["matches"] or record["projectName"].lower() in plan["excluded_projects"]:
            reason = "overlap_flag"
        elif record["type"] not in SUPPORTED:
            reason = "unsupported_operation"
        elif (record["filePathBefore"] != record["filePathAfter"]
              or "/test/" in "/" + record["filePathBefore"]
              or not record.get("sourceCodeBeforeForWhole")
              or not record.get("sourceCodeAfterForWhole")):
            reason = "not_single_production_file"
        if reason:
            excluded[reason] += 1
        else:
            eligible.append(record)
    # Preserve the known, predeclared controls first, then official dataset order.
    overrides = {}
    for spec in plan["candidates"]:
        matches = [r for r in eligible if r["uniqueId"].startswith(spec["prefix"])]
        if len(matches) != 1:
            raise ValueError("Candidate override is not unique in audited pool")
        overrides[matches[0]["uniqueId"]] = spec
    positions = {r["uniqueId"]: i for i, r in enumerate(records)}
    ordered = sorted(eligible, key=lambda r: (
        list(overrides).index(r["uniqueId"]) if r["uniqueId"] in overrides else len(overrides),
        positions[r["uniqueId"]] if r["uniqueId"] not in overrides else 0))
    dataset_sha = ex.file_sha256(dataset)
    report = json.loads((repo / plan["overlap_evidence"]).read_text())
    pinned = [r["sha256"] for r in report["inputs"] if r["path"] == plan["dataset"]]
    if pinned != [dataset_sha]:
        raise ValueError("Dataset differs from overlap audit; refresh audit before selection")
    identity = {"dataset_sha256": dataset_sha,
                "audit_sha256": ex.file_sha256(audit_path),
                "ids": [r["uniqueId"] for r in ordered], "excluded": dict(excluded)}
    return ordered, overrides, identity


def behavior_mutants(before, gold, limit, focus=None):
    """Replace changed/new method bodies, never unrelated methods or test files.

    An unconditional throw is valid for any return type. Only a compiled mutant
    killed twice by the unchanged original test identities counts as a control.
    Surviving/uncompilable mutants are evidence, never a reason to relax QA.
    """
    def methods(source):
        raw = source.encode()
        root = ex.JavaParser().parser.parse(raw).root_node
        if root.has_error:
            raise ValueError("Invalid Java for mutation controls")
        result = {}
        def visit(node, owners=()):
            if node.type in {"class_declaration", "interface_declaration", "enum_declaration",
                             "record_declaration", "annotation_type_declaration"}:
                name = node.child_by_field_name("name")
                owners = (*owners, raw[name.start_byte:name.end_byte].decode())
            if node.type == "method_declaration":
                body = node.child_by_field_name("body")
                if body is not None:
                    header = raw[node.start_byte:body.start_byte].decode()
                    key = (*owners, ex.normalize_java_for_hash(header))
                    # Duplicate signatures (e.g. anonymous classes) are ambiguous.
                    if key in result:
                        raise ValueError("Ambiguous method identity for mutation")
                    result[key] = (body.start_byte, body.end_byte,
                                   ex.normalize_java_for_hash(raw[body.start_byte:body.end_byte].decode()),
                                   ex.normalize_java_for_hash(raw[node.start_byte:node.end_byte].decode()))
            for child in node.named_children:
                visit(child, owners)
        visit(root)
        return raw, result
    _, original = methods(before)
    raw, updated = methods(gold)
    mutants = []
    for key, (start, end, body, whole_method) in updated.items():
        if focus is not None and whole_method not in ex.normalize_java_for_hash(focus):
            continue
        if key not in original or original[key][2] != body:
            replacement = b'{ throw new java.lang.AssertionError("EVALUATOR_BEHAVIOR_CONTROL"); }'
            mutants.append({"method": list(key), "source": (raw[:start] + replacement + raw[end:]).decode()})
            if len(mutants) == limit:
                break
    return mutants
