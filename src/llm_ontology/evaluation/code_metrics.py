from __future__ import annotations

import re
from statistics import mean
from typing import Any


JAVA_KEYWORDS = {
    "String",
    "Integer",
    "Boolean",
    "Long",
    "Double",
    "Float",
    "Object",
    "List",
    "Map",
    "Set",
    "Exception",
}


def safe_mean(values: list[int | float]) -> float:
    return float(mean(values)) if values else 0.0


def lines(code: str) -> list[str]:
    return (code or "").splitlines()


def method_signatures(code: str) -> list[re.Match[str]]:
    pattern = re.compile(
        r"(?:public|private|protected|static|final|synchronized|\s)+[\w<>\[\], ?]+\s+(\w+)\s*\(([^)]*)\)\s*\{",
        re.MULTILINE,
    )
    return list(pattern.finditer(code or ""))


def method_parameter_counts(code: str) -> list[int]:
    counts: list[int] = []
    for match in method_signatures(code):
        params = match.group(2).strip()
        if not params:
            counts.append(0)
        else:
            counts.append(len([part for part in params.split(",") if part.strip()]))
    return counts


def method_lengths_proxy(code: str) -> list[int]:
    text = code or ""
    lengths: list[int] = []
    for match in method_signatures(text):
        depth = 0
        start_line = text[: match.start()].count("\n")
        end_line = start_line
        for index in range(match.start(), len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end_line = text[: index].count("\n")
                    break
        lengths.append(max(1, end_line - start_line + 1))
    return lengths


def max_brace_nesting_depth(code: str) -> int:
    depth = 0
    max_depth = 0
    for char in code or "":
        if char == "{":
            depth += 1
            max_depth = max(max_depth, depth)
        elif char == "}":
            depth = max(0, depth - 1)
    return max_depth


def identifier_reuse_proxy(code: str) -> float:
    identifiers = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", code or "")
    identifiers = [item for item in identifiers if item not in JAVA_KEYWORDS and len(item) > 1]
    if not identifiers:
        return 0.0
    unique = len(set(identifiers))
    return max(0.0, min(1.0, 1.0 - (unique / len(identifiers))))


def compute_code_metrics(code: str) -> dict[str, Any]:
    try:
        code_lines = lines(code)
        non_empty = [line for line in code_lines if line.strip()]
        comment = [line for line in non_empty if line.strip().startswith(("//", "/*", "*"))]
        methods = method_signatures(code)
        params = method_parameter_counts(code)
        lengths = method_lengths_proxy(code)
        logical_ops = len(re.findall(r"&&|\|\|", code or ""))
        if_count = len(re.findall(r"\bif\s*\(", code or ""))
        for_count = len(re.findall(r"\bfor\s*\(", code or ""))
        while_count = len(re.findall(r"\bwhile\s*\(", code or ""))
        case_count = len(re.findall(r"\bcase\b", code or ""))
        catch_count = len(re.findall(r"\bcatch\s*\(", code or ""))
        imports = len(re.findall(r"^\s*import\s+", code or "", flags=re.MULTILINE))
        dot_calls = len(re.findall(r"\b[a-zA-Z_][\w]*\.[a-zA-Z_][\w]*\s*\(", code or ""))
        new_objects = len(re.findall(r"\bnew\s+[A-Z][A-Za-z0-9_]*\s*\(", code or ""))
        class_like = set(re.findall(r"\b[A-Z][A-Za-z0-9_]+\b", code or "")) - JAVA_KEYWORDS
        local_vars = len(re.findall(r"\b(?:String|int|long|double|float|boolean|var|List|Map|Set)\s+\w+\s*(?:=|;)", code or ""))
        complexity = 1 + if_count + for_count + while_count + case_count + catch_count + logical_ops
        return {
            "lines_of_code": len(code_lines),
            "non_empty_lines": len(non_empty),
            "comment_lines": len(comment),
            "method_count_proxy": len(methods),
            "class_count_proxy": len(re.findall(r"\bclass\s+[A-Z]\w*", code or "")),
            "import_count": imports,
            "average_line_length": safe_mean([len(line) for line in code_lines]),
            "max_line_length": max([len(line) for line in code_lines], default=0),
            "if_count": if_count,
            "else_count": len(re.findall(r"\belse\b", code or "")),
            "for_count": for_count,
            "while_count": while_count,
            "switch_count": len(re.findall(r"\bswitch\s*\(", code or "")),
            "case_count": case_count,
            "catch_count": catch_count,
            "logical_operator_count": logical_ops,
            "complexity_proxy_score": complexity,
            "max_brace_nesting_depth": max_brace_nesting_depth(code),
            "dot_call_count": dot_calls,
            "new_object_count": new_objects,
            "unique_class_like_identifiers": len(class_like),
            "method_parameter_count_avg_proxy": safe_mean(params),
            "avg_method_length_proxy": safe_mean(lengths),
            "max_method_length_proxy": max(lengths, default=0),
            "avg_parameter_count_proxy": safe_mean(params),
            "local_variable_count_proxy": local_vars,
            "identifier_reuse_proxy": identifier_reuse_proxy(code),
        }
    except Exception as exc:
        return {"metrics_warning": str(exc)}


def cohesion_proxy_score(metrics: dict[str, Any]) -> float:
    score = 10.0
    score -= min(3.0, float(metrics.get("avg_method_length_proxy", 0)) / 30.0)
    score -= min(2.0, float(metrics.get("avg_parameter_count_proxy", 0)) / 2.0)
    score -= 2.0 if float(metrics.get("identifier_reuse_proxy", 0)) < 0.1 else 0.0
    method_count = int(metrics.get("method_count_proxy", 0))
    if method_count == 0:
        score -= 2.0
    elif method_count <= 6:
        score += 0.5
    return max(0.0, min(10.0, score))


def coupling_proxy_score(metrics: dict[str, Any]) -> float:
    score = (
        float(metrics.get("import_count", 0)) * 0.4
        + float(metrics.get("dot_call_count", 0)) * 0.15
        + float(metrics.get("new_object_count", 0)) * 0.6
        + float(metrics.get("unique_class_like_identifiers", 0)) * 0.25
        + float(metrics.get("avg_parameter_count_proxy", 0)) * 0.8
    )
    return max(0.0, min(10.0, score))
