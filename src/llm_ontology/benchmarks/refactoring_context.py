"""AST-member context selection, aligned before/after; never arbitrary line cuts."""
from __future__ import annotations

from llm_ontology.benchmarks.refactoring_structural import parser, valid_java

TYPES = {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration", "annotation_type_declaration"}


class Unit:
    def __init__(self, source):
        self.raw = source.encode()
        self.root = parser().parse(self.raw).root_node
        if self.root.has_error:
            raise ValueError("Context source does not parse")
        self.types, self.members = {}, {}
        def walk(node, owner=()):
            if node.type in TYPES:
                name = node.child_by_field_name("name")
                owner = (*owner, self.text(name))
                self.types[owner] = node
                body = node.child_by_field_name("body")
                if body is not None:
                    for child in body.named_children:
                        if child.type in TYPES or child.type.endswith("comment"):
                            continue
                        name = child.child_by_field_name("name")
                        names = self.text(name) if name is not None else self.text(child).split("=", 1)[0].strip()
                        key = (owner, child.type, names)
                        self.members.setdefault(key, []).append(child)
            for child in node.named_children:
                walk(child, owner)
        walk(self.root)

    def text(self, node):
        return self.raw[node.start_byte:node.end_byte].decode()

    def targets(self, locations):
        keys, full = set(), set()
        for loc in locations:
            start, end = loc["startLine"], loc["endLine"]
            if loc.get("codeElementType") in {"TYPE_DECLARATION", "ENUM_DECLARATION", "RECORD_DECLARATION"}:
                matches = [(o, n) for o, n in self.types.items()
                           if n.start_point.row + 1 <= start and n.end_point.row + 1 >= end]
                if matches:
                    full.add(max(matches, key=lambda row: len(row[0]))[0])
                    continue
            matches = [(key, node) for key, nodes in self.members.items() for node in nodes
                       if node.start_point.row + 1 <= start and node.end_point.row + 1 >= end]
            if matches:
                # Columns distinguish declarations sharing a single source line.
                row = start - 1
                line = self.raw.splitlines(keepends=True)[row].decode()
                col = len(line.encode("utf-16-le")[:(loc["startColumn"]-1)*2].decode("utf-16-le").encode())
                precise = [(k, n) for k, n in matches if n.start_point <= (row, col) < n.end_point]
                chosen = min(precise or matches, key=lambda pair: pair[1].end_byte-pair[1].start_byte)
                keys.add(chosen[0])
        if not keys and not full:
            raise ValueError("Cannot locate a complete target member for context")
        return keys, full

    def neighbors(self, keys):
        result = set(keys)
        owners = {key[0] for key in keys}
        for owner in owners:
            ordered = sorted((key for key in self.members if key[0] == owner),
                             key=lambda key: self.members[key][0].start_byte)
            for i, key in enumerate(ordered):
                if key in keys:
                    result.update(ordered[max(0, i-1):i+2])
                if key[1] in {"field_declaration", "constant_declaration"}:
                    result.add(key)
        return result

    def render(self, keys, full):
        owners = {key[0] for key in keys} | full
        def wanted(owner):
            return any(path[:len(owner)] == owner for path in owners)
        def render_type(owner, node):
            if owner in full:
                return self.text(node)
            body = node.child_by_field_name("body")
            if body is None:
                return self.text(node)
            pieces = []
            children = []
            for key, nodes in self.members.items():
                if key[0] == owner and key in keys:
                    children.extend((n.start_byte, self.text(n)) for n in nodes)
            for path, child in self.types.items():
                if path[:-1] == owner and wanted(path):
                    children.append((child.start_byte, render_type(path, child)))
            for _, text in sorted(children):
                pieces.append(text)
            return (self.raw[node.start_byte:body.start_byte].decode() + "{\n" + "\n\n".join(pieces)
                    + "\n}" + self.raw[body.end_byte:node.end_byte].decode())
        result = []
        for node in self.root.named_children:
            if node.type in TYPES:
                owner = next(path for path, value in self.types.items() if value == node)
                if wanted(owner):
                    result.append(render_type(owner, node))
            else:
                result.append(self.text(node))
        return "\n\n".join(result) + "\n"


def contextual_pair(before, after, event):
    left, right = Unit(before), Unit(after)
    before_keys, before_full = left.targets(event["left"])
    after_keys, after_full = right.targets(event["right"])
    # Shared logical keys keep corresponding context on BOTH sides, including
    # renamed/added/removed methods where a member only exists on one side.
    keys = left.neighbors(before_keys) | right.neighbors(after_keys)
    full = before_full | after_full
    a, b = left.render(keys, full), right.render(keys, full)
    if not valid_java(a) or not valid_java(b):
        raise ValueError("Context selection is not a Java compilation unit")
    return a, b, {"policy": "target_members_plus_neighbor_each_side_and_fields",
                  "original_before_lines": [min(x["startLine"] for x in event["left"]), max(x["endLine"] for x in event["left"])],
                  "original_after_lines": [min(x["startLine"] for x in event["right"]), max(x["endLine"] for x in event["right"])],
                  "before_bytes": len(before.encode()), "after_bytes": len(after.encode()),
                  "context_before_bytes": len(a.encode()), "context_after_bytes": len(b.encode())}
