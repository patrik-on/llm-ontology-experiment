"""Syntactic Java facts for the project ontology (tree-sitter only, no semantics guessed).

Every fact here is something the parser can establish with certainty from the code the
model is shown: declarations, signatures, ``throw`` sites with their guarding condition,
branch conditions, comparisons against literals, identifier uses and simple def/use data
flow inside one method. Nothing is inferred from names, documentation or other files.
Line numbers are 1-based and refer to the supplied source.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator

from llm_ontology.benchmarks.refactoring_structural import parser

TYPE_NODES = {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration"}
METHOD_NODES = {"method_declaration", "constructor_declaration"}
BRANCH_NODES = {"if_statement": "if", "switch_expression": "switch", "switch_statement": "switch",
                "ternary_expression": "ternary", "while_statement": "loop", "for_statement": "loop",
                "enhanced_for_statement": "loop", "do_statement": "loop"}
COMPARISONS = {"<", "<=", ">", ">=", "==", "!="}
CONSTANT_NAME = re.compile(r"[A-Z][A-Z0-9_]*")  # compared against; resolved only via a final field
NUMBER_LITERALS = {"decimal_integer_literal", "decimal_floating_point_literal", "hex_integer_literal"}


@dataclass(frozen=True)
class Param:
    name: str
    type: str


@dataclass(frozen=True)
class ThrowSite:
    exception: str
    guard: str | None
    line: int


@dataclass(frozen=True)
class Branch:
    kind: str
    condition: str
    line: int


@dataclass(frozen=True)
class Comparison:
    subject: str
    operator: str
    value: str
    line: int


@dataclass
class MethodFacts:
    owner: str
    name: str
    kind: str  # method | constructor
    modifiers: tuple[str, ...]
    return_type: str
    params: tuple[Param, ...]
    declared_throws: tuple[str, ...]
    start: int
    end: int
    throws: list[ThrowSite] = field(default_factory=list)
    branches: list[Branch] = field(default_factory=list)
    comparisons: list[Comparison] = field(default_factory=list)
    null_checks: list[str] = field(default_factory=list)
    fields_read: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    @property
    def signature(self) -> str:
        params = ", ".join(f"{p.type} {p.name}" for p in self.params)
        head = " ".join([*self.modifiers, *([self.return_type] if self.kind == "method" else [])])
        return f"{head + ' ' if head else ''}{self.name}({params})"


@dataclass(frozen=True)
class FieldFacts:
    owner: str
    name: str
    type: str
    modifiers: tuple[str, ...]
    initializer: str | None
    line: int


@dataclass
class BlockFacts:
    method: str
    start: int
    end: int
    inputs: list[Param]
    outputs: list[Param]
    fields_written: list[str]
    has_return: bool
    has_jump: bool


@dataclass
class LocalFacts:
    """A local variable or parameter declared in a method, with every use."""
    method: str
    name: str
    type: str
    kind: str  # local | parameter
    line: int
    initializer: str | None
    uses: list[int]


class JavaUnit:
    def __init__(self, source: str):
        self.raw = source.encode()
        self.root = parser().parse(self.raw).root_node
        if self.root.has_error:
            raise ValueError("Source does not parse")

    # -- helpers -----------------------------------------------------------------------
    def text(self, node) -> str:
        return " ".join(self.raw[node.start_byte:node.end_byte].decode().split())

    @staticmethod
    def line(node) -> int:
        return node.start_point.row + 1

    @staticmethod
    def end_line(node) -> int:
        return node.end_point.row + 1

    def walk(self, node=None) -> Iterator:
        stack = [node or self.root]
        while stack:
            current = stack.pop()
            yield current
            stack.extend(reversed(current.named_children))

    def owner_of(self, node) -> str:
        names, current = [], node.parent
        while current is not None:
            if current.type in TYPE_NODES:
                names.append(self.text(current.child_by_field_name("name")))
            current = current.parent
        return ".".join(reversed(names))

    def modifiers(self, node) -> tuple[str, ...]:
        for child in node.named_children:
            if child.type == "modifiers":
                return tuple(c.type if c.is_named and c.type != "identifier" else self.text(c)
                             for c in child.children if not c.type.endswith("annotation"))
        return ()

    # -- declarations ------------------------------------------------------------------
    def types(self) -> list[tuple[str, str, int, int]]:
        return [(self.text(n.child_by_field_name("name")), n.type.removesuffix("_declaration"),
                 self.line(n), self.end_line(n)) for n in self.walk() if n.type in TYPE_NODES]

    def fields(self) -> list[FieldFacts]:
        result = []
        for node in self.walk():
            if node.type != "field_declaration":
                continue
            type_ = self.text(node.child_by_field_name("type"))
            for declarator in node.named_children:
                if declarator.type == "variable_declarator":
                    value = declarator.child_by_field_name("value")
                    result.append(FieldFacts(self.owner_of(node), self.text(declarator.child_by_field_name("name")),
                                             type_, self.modifiers(node), self.text(value) if value else None,
                                             self.line(node)))
        return result

    def method_nodes(self) -> list:
        return [n for n in self.walk() if n.type in METHOD_NODES]

    def params(self, method) -> tuple[Param, ...]:
        params = method.child_by_field_name("parameters")
        return tuple(Param(self.text(p.child_by_field_name("name")), self.text(p.child_by_field_name("type")))
                     for p in (params.named_children if params else [])
                     if p.type in {"formal_parameter", "spread_parameter"} and p.child_by_field_name("name"))

    def method_facts(self, method) -> MethodFacts:
        type_node = method.child_by_field_name("type")
        throws = next((c for c in method.named_children if c.type == "throws"), None)
        field_names = {f.name for f in self.fields()}
        params = self.params(method)
        local_names = {p.name for p in params} | {n.name for n in self.locals(method)}
        facts = MethodFacts(
            owner=self.owner_of(method), name=self.text(method.child_by_field_name("name")),
            kind="constructor" if method.type == "constructor_declaration" else "method",
            modifiers=self.modifiers(method), return_type=self.text(type_node) if type_node else "",
            params=params,
            declared_throws=tuple(self.text(t) for t in throws.named_children) if throws else (),
            start=self.line(method), end=self.end_line(method))
        body = method.child_by_field_name("body")
        if body is None:
            return facts
        for node in self.walk(body):
            if node.type == "throw_statement":
                created = node.named_children[0] if node.named_children else None
                exception = (self.text(created.child_by_field_name("type"))
                             if created is not None and created.type == "object_creation_expression"
                             else self.text(created) if created is not None else "?")
                facts.throws.append(ThrowSite(exception, self.guard(node, method), self.line(node)))
            elif node.type in BRANCH_NODES:
                facts.branches.append(Branch(BRANCH_NODES[node.type], self.condition_text(node), self.line(node)))
            elif node.type == "binary_expression" and self.text_of_operator(node) in COMPARISONS:
                self.comparison(node, facts)
            elif node.type == "identifier" and node.parent.type not in {"method_invocation"} \
                    and self.text(node) in field_names and self.text(node) not in local_names:
                facts.fields_read.append(self.text(node))
            elif node.type == "field_access" and self.text(node.child_by_field_name("object")) == "this":
                facts.fields_read.append(self.text(node.child_by_field_name("field")))
            elif node.type == "method_invocation":
                obj = node.child_by_field_name("object")
                name = self.text(node.child_by_field_name("name"))
                facts.calls.append((self.text(obj) + "." if obj else "") + name)
        facts.fields_read = sorted(set(facts.fields_read))
        facts.calls = sorted(set(facts.calls))
        facts.null_checks = sorted(set(facts.null_checks))
        return facts

    def text_of_operator(self, node) -> str:
        operator = node.child_by_field_name("operator")
        return self.text(operator) if operator is not None else ""

    def comparison(self, node, facts: MethodFacts) -> None:
        left, right, op = node.child_by_field_name("left"), node.child_by_field_name("right"), self.text_of_operator(node)
        for subject, value in ((left, right), (right, left)):
            if value.type == "null_literal":
                facts.null_checks.append(f"{self.text(subject)} {op} null")
                return
            literal = value.type in NUMBER_LITERALS or (
                value.type == "unary_expression" and value.named_children
                and value.named_children[0].type in NUMBER_LITERALS)
            constant = value.type == "identifier" and CONSTANT_NAME.fullmatch(self.text(value)) is not None
            if (literal or constant) and subject.type not in NUMBER_LITERALS and not (
                    constant and subject.type == "identifier" and CONSTANT_NAME.fullmatch(self.text(subject))):
                if subject is right:  # normalise "0 < x" to "x > 0"
                    op = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}.get(op, op)
                facts.comparisons.append(Comparison(self.text(subject), op, self.text(value), self.line(node)))
                return

    def condition_text(self, node) -> str:
        if node.type == "switch_expression" or node.type == "switch_statement":
            labels = [self.text(label).removeprefix("case ").rstrip(":") for label in self.walk(node)
                      if label.type == "switch_label"]
            return f"switch {self.text(node.child_by_field_name('condition'))} cases: {', '.join(labels)}"
        if node.type == "enhanced_for_statement":
            return f"for {self.text(node.child_by_field_name('name'))} : {self.text(node.child_by_field_name('value'))}"
        condition = node.child_by_field_name("condition")
        if condition is None:
            return node.type.removesuffix("_statement")
        text = self.text(condition)
        return text[1:-1].strip() if condition.type == "parenthesized_expression" else text

    def guard(self, node, method) -> str | None:
        """Condition under which ``node`` runs, from the nearest enclosing ``if``."""
        child, current = node, node.parent
        while current is not None and current != method:
            if current.type == "if_statement":
                condition = self.condition_text(current)
                alternative = current.child_by_field_name("alternative")
                if alternative is not None and alternative.start_byte <= child.start_byte \
                        and child.end_byte <= alternative.end_byte:
                    return f"!({condition})"
                return condition
            child, current = current, current.parent
        return None

    # -- locals and data flow ------------------------------------------------------------
    def enclosing_method(self, line: int):
        candidates = [m for m in self.method_nodes() if self.line(m) <= line <= self.end_line(m)]
        return min(candidates, key=lambda m: m.end_byte - m.start_byte) if candidates else None

    def locals(self, method) -> list[LocalFacts]:
        name = self.text(method.child_by_field_name("name"))
        found = [LocalFacts(name, p.name, p.type, "parameter", self.line(method), None, [])
                 for p in self.params(method)]
        body = method.child_by_field_name("body")
        for node in self.walk(body) if body is not None else []:
            if node.type in {"local_variable_declaration", "resource"}:
                type_ = self.text(node.child_by_field_name("type"))
                declarators = [d for d in node.named_children if d.type == "variable_declarator"] or [node]
                for d in declarators:
                    value = d.child_by_field_name("value")
                    found.append(LocalFacts(name, self.text(d.child_by_field_name("name")), type_, "local",
                                            self.line(d), self.text(value) if value else None, []))
            elif node.type in {"enhanced_for_statement", "catch_formal_parameter"}:
                ident = node.child_by_field_name("name")
                if ident is not None:
                    type_node = node.child_by_field_name("type")
                    found.append(LocalFacts(name, self.text(ident), self.text(type_node) if type_node else "?",
                                            "local", self.line(node), None, []))
        uses = self.identifier_lines(body) if body is not None else {}
        for local in found:
            local.uses = sorted(line for line in uses.get(local.name, []) if line != local.line
                                or local.kind == "parameter")
        return found

    def identifier_lines(self, node) -> dict[str, list[int]]:
        lines: dict[str, list[int]] = {}
        for ident in self.walk(node):
            if ident.type != "identifier":
                continue
            parent = ident.parent
            # Skip member names that are not variable references: obj.name / name(...)
            if parent.type == "field_access" and parent.child_by_field_name("field") == ident:
                continue
            if parent.type == "method_invocation" and parent.child_by_field_name("name") == ident:
                continue
            lines.setdefault(self.text(ident), []).append(self.line(ident))
        return lines

    def block_facts(self, start: int, end: int) -> BlockFacts | None:
        method = self.enclosing_method(start)
        if method is None:
            return None
        locals_ = self.locals(method)
        fields = {f.name for f in self.fields()}
        local_names = {v.name for v in locals_}
        inputs, outputs, written = [], [], set()
        assigned_in_block = set()
        body = method.child_by_field_name("body")
        has_return = has_jump = False
        for node in self.walk(body):
            if not (start <= self.line(node) <= end):
                continue
            if node.type == "return_statement":
                has_return = True
            elif node.type in {"break_statement", "continue_statement"}:
                has_jump = True
            elif node.type in {"assignment_expression", "update_expression"}:
                target = node.child_by_field_name("left") or (node.named_children[0] if node.named_children else None)
                if target is None:
                    continue
                if target.type == "identifier":
                    name = self.text(target)
                    if name in local_names:
                        assigned_in_block.add(name)
                    elif name in fields:
                        written.add(name)
                elif target.type == "field_access":
                    written.add(self.text(target.child_by_field_name("field")))
        for local in locals_:
            declared_before = local.line < start or local.kind == "parameter"
            declared_inside = start <= local.line <= end
            used_inside = any(start <= u <= end for u in local.uses)
            used_after = any(u > end for u in local.uses)
            if declared_before and used_inside:
                inputs.append(Param(local.name, local.type))
            if (declared_inside or local.name in assigned_in_block) and used_after:
                outputs.append(Param(local.name, local.type))
        return BlockFacts(self.text(method.child_by_field_name("name")), start, end,
                          sorted(set(inputs), key=lambda p: p.name), sorted(set(outputs), key=lambda p: p.name),
                          sorted(written), has_return, has_jump)

    def call_sites(self, name: str) -> list[int]:
        return sorted(self.line(n) for n in self.walk() if n.type == "method_invocation"
                      and self.text(n.child_by_field_name("name")) == name)

    def type_references(self, name: str) -> list[int]:
        return sorted({self.line(n) for n in self.walk() if n.type == "type_identifier" and self.text(n) == name})
