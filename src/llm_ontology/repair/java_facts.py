"""Facts for the repair-loop rules, extracted with tree-sitter from public inputs only.

Refactoring (Parameterize Variable): the input unit (``before``), the model's output
(``after``) and the request text. The graph uses the ``lo:`` vocabulary of the handwritten
shapes (R1, R2) plus ``lo:usageRole`` and ``lo:isLoggingHelper``. Nothing here reads the
reference output or ``target_event``.

A use of the old variable in ``before`` is paired with a place in ``after`` by matching its
source line to the most similar line of the target method and aligning the tokens. If no
line is similar enough, the use stays unpaired and R2 reports "undecided" (``sh:Info``).
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re

from rdflib import Graph, Literal, Namespace, RDF, URIRef

LO = Namespace("https://w3id.org/llm-ontology/project#")
FACTS_VERSION = "repair-facts-v2"  # v2: presence of the requested method in input and output

# Fact names a rule may rely on. A proposal that needs anything else is deferred.
VOCABULARY = frozenset({
    "lo:Decl", "lo:Method", "lo:RefactoringRequest", "lo:ParameterizeVariableRequest", "lo:side",
    "lo:checkScope", "lo:display", "lo:line", "lo:modifiers", "lo:hasCounterpart", "lo:declaredIn",
    "lo:name", "lo:hasParameter", "lo:declaresLocal", "lo:initializer", "lo:hasUse",
    "lo:resolvesKind", "lo:usageRole", "lo:isLoggingHelper", "lo:statementCount", "lo:oldName",
    "lo:newName", "lo:newType", "lo:targetMethodBefore", "lo:targetMethodAfter",
    # testing (T3); extracted only from the TTL fixtures in this pilot
    "lo:Argument", "lo:argumentOf", "lo:position", "lo:producedBy", "lo:inExpectedException",
    "lo:factoryName", "lo:resultMutability", "lo:mutableAlternative", "lo:resolvesTo",
    "lo:mutatesParameter", "lo:mutatedBy", "lo:mutationOnSuccessPath", "lo:inBody",
})
VOCABULARY_V1 = VOCABULARY
# v2: is the requested method declared in the input, is its requested signature in the output,
# and the method that held the old variable in the input as found in the output
VOCABULARY_V2_ADDED = frozenset({"lo:requestedSignature", "lo:targetMethodInInput", "lo:targetSignatureInOutput",
                                 "lo:sourceMethodAfter"})
VOCABULARY = VOCABULARY_V1 | VOCABULARY_V2_ADDED

LOG_METHODS = frozenset({"debug", "info", "warn", "warning", "error", "trace", "fine", "finer", "finest",
                         "log", "verbose", "println", "print", "printf"})
LOG_RECEIVER = re.compile(r"(?i)(log|logger|message|system\.(out|err))")
REQUEST = re.compile(r"^Parameterize Variable\s+(?P<old>\w+) : (?P<old_type>.+?) to (?P<new>\w+) : "
                     r"(?P<new_type>.+?) in method (?P<sig>.+?) from class (?P<cls>[\w.$]+)\s*$")


def _parser():
    from llm_ontology.benchmarks.refactoring_structural import parser
    return parser()


@dataclass(frozen=True)
class PVRequest:
    old: str
    old_type: str
    new: str
    new_type: str
    method: str
    arity: int
    class_name: str
    param_types: tuple[str, ...] = ()

    @property
    def signature(self) -> str:
        return f"{self.method}({', '.join(self.param_types)})"


def parse_request(text: str) -> PVRequest:
    match = REQUEST.match(text.strip())
    if not match:
        raise ValueError("Not a Parameterize Variable request: " + text[:80])
    sig = match["sig"]
    name = sig.split("(", 1)[0].split()[-1]
    inner = sig[sig.index("(") + 1:sig.rindex(")")].strip()
    params = _split_top(inner) if inner else []
    types = tuple(_norm_type(p.strip().split(None, 1)[1]) if len(p.strip().split(None, 1)) == 2 else p.strip()
                  for p in params)
    return PVRequest(match["old"], match["old_type"].strip(), match["new"], match["new_type"].strip(),
                     name, len(params), match["cls"].rsplit(".", 1)[-1], types)


def _norm_type(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("final ", ""))


def _split_top(text: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in text:
        depth += ch == "<"
        depth -= ch == ">"
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    return [p for p in [*parts, cur] if p.strip()]


class _Unit:
    def __init__(self, source: str):
        self.raw = source.encode("utf-8")
        self.root = _parser().parse(self.raw).root_node

    def text(self, node) -> str:
        return self.raw[node.start_byte:node.end_byte].decode("utf-8")

    def walk(self, node=None):
        node = node or self.root
        yield node
        for child in node.named_children:
            yield from self.walk(child)

    def methods(self):
        return [n for n in self.walk() if n.type in {"method_declaration", "constructor_declaration"}]

    def members(self):
        kinds = {"class_declaration", "interface_declaration", "enum_declaration", "method_declaration",
                 "constructor_declaration", "field_declaration"}
        return [n for n in self.walk() if n.type in kinds]

    def name(self, node) -> str:
        if node.type == "field_declaration":
            decl = next((c for c in node.named_children if c.type == "variable_declarator"), None)
            return self.text(decl.child_by_field_name("name")) if decl else ""
        ident = node.child_by_field_name("name")
        return self.text(ident) if ident else ""

    def modifiers(self, node) -> str:
        mods = next((c for c in node.children if c.type == "modifiers"), None)
        if mods is None:
            return "(none)"
        words = [self.text(c) for c in mods.children if "annotation" not in c.type]
        return " ".join(sorted(words)) or "(none)"

    def params(self, method) -> list[tuple[str, str]]:
        plist = method.child_by_field_name("parameters")
        out = []
        for p in (plist.named_children if plist else []):
            if p.type in {"formal_parameter", "spread_parameter"}:
                name = p.child_by_field_name("name")
                typ = p.child_by_field_name("type")
                if name is None:  # spread_parameter: last named child holds the declarator
                    decl = p.named_children[-1]
                    name = decl.child_by_field_name("name") if decl.type == "variable_declarator" else decl
                out.append((self.text(name), self.text(typ) if typ else ""))
        return out

    def key(self, node):
        if node.type in {"method_declaration", "constructor_declaration"}:
            return (node.type, self.name(node), tuple(t for _, t in self.params(node)))
        return (node.type, self.name(node))

    def display(self, node) -> str:
        kind = {"method_declaration": "method", "constructor_declaration": "constructor",
                "field_declaration": "field"}.get(node.type, node.type.split("_")[0])
        if node.type in {"method_declaration", "constructor_declaration"}:
            return f"{kind} {self.name(node)}({', '.join(t for _, t in self.params(node))})"
        return f"{kind} {self.name(node)}"

    def body_statements(self, method) -> int:
        body = method.child_by_field_name("body")
        return sum(1 for n in self.walk(body) if n.type.endswith("_statement")
                   or n.type == "local_variable_declaration") if body else 0

    def locals(self, method):
        body = method.child_by_field_name("body")
        for node in (self.walk(body) if body else []):
            if node.type == "local_variable_declaration":
                for decl in node.named_children:
                    if decl.type == "variable_declarator":
                        value = decl.child_by_field_name("value")
                        yield (self.text(decl.child_by_field_name("name")), decl.start_point.row + 1,
                               self.text(value) if value else "", decl.child_by_field_name("name"))

    def identifier_uses(self, method, names):
        body = method.child_by_field_name("body")
        declared = {_k(d[3]) for d in self.locals(method)}
        for node in (self.walk(body) if body else []):
            if node.type == "identifier" and self.text(node) in names and _k(node) not in declared:
                parent = node.parent
                if parent is not None and parent.type == "field_access" and parent.child_by_field_name("field") == node:
                    continue  # x.name is not a use of the variable name
                if parent is not None and parent.type == "method_invocation" and parent.child_by_field_name("name") == node:
                    continue
                yield node

    def role(self, node) -> str:
        cur = node.parent
        while cur is not None and cur.type not in {"method_declaration", "constructor_declaration"}:
            if cur.type == "method_invocation":
                name = cur.child_by_field_name("name")
                obj = cur.child_by_field_name("object")
                if name is not None and self.text(name) in LOG_METHODS and (
                        obj is None or LOG_RECEIVER.search(self.text(obj))):
                    return "logging"
            cur = cur.parent
        return "computation"

    def line_tokens(self, method, row):
        body = method.child_by_field_name("body")
        leaves = []
        def visit(n):
            if n.child_count == 0:
                if n.start_point.row == row and n.type != "comment":
                    leaves.append(n)
                return
            if n.start_point.row <= row <= n.end_point.row:
                for c in n.children:
                    visit(c)
        if body is not None:
            visit(body)
        return leaves

    def is_logging_helper(self, method) -> bool:
        body = method.child_by_field_name("body")
        stmts = [c for c in (body.named_children if body else []) if c.type != "comment"]
        return bool(stmts) and all(self._top_is_log(s) for s in stmts)

    def _top_is_log(self, stmt) -> bool:
        expr = stmt.named_children[0] if stmt.type == "expression_statement" and stmt.named_children else None
        if expr is None or expr.type != "method_invocation":
            return False
        name, obj = expr.child_by_field_name("name"), expr.child_by_field_name("object")
        return self.text(name) in LOG_METHODS and (obj is None or bool(LOG_RECEIVER.search(self.text(obj))))


def _k(node):
    """Stable node key: tree-sitter returns a new wrapper object on every access."""
    return (node.start_byte, node.end_byte, node.type)


def _resolve(unit: _Unit, method, node) -> str:
    if node.type != "identifier":
        return "literal" if "literal" in node.type or node.type in {"true", "false", "null"} else "other"
    name, line = unit.text(node), node.start_point.row + 1
    if any(n == name and ln <= line for n, ln, _, _ in unit.locals(method)):
        return "local"
    if any(n == name for n, _ in unit.params(method)):
        return "parameter"
    fields = {unit.name(f) for f in unit.members() if f.type == "field_declaration"}
    return "field" if name in fields else "unknown"


def refactoring_graph(before: str, after: str, request: str, target_start: int) -> Graph:
    """Facts for R1 and R2 (and template rules) on one Parameterize Variable answer."""
    req = parse_request(request)
    b, a = _Unit(before), _Unit(after)
    g = Graph()
    g.bind("lo", LO)
    ns = lambda side, i: URIRef(f"{LO}{side}_{i}")  # noqa: E731
    lit = Literal

    source = next((m for m in b.methods() if m.start_point.row + 1 <= target_start <= m.end_point.row + 1), None)
    if source is None:
        raise ValueError("No method encloses the target line in the input")
    excluded = {b.key(source)} | {b.key(m) for m in b.methods() if b.name(m) == req.method}
    after_members = {a.key(n): n for n in a.members()}
    after_nodes = {}
    for i, node in enumerate(a.members()):
        after_nodes[_k(node)] = ns("a", i)
        g.add((ns("a", i), RDF.type, LO.Decl))
        g.add((ns("a", i), LO.side, lit("after")))
        g.add((ns("a", i), LO.display, lit(a.display(node))))
        g.add((ns("a", i), LO.modifiers, lit(a.modifiers(node))))
    for i, node in enumerate(b.members()):
        uri = ns("b", i)
        g.add((uri, RDF.type, LO.Decl))
        g.add((uri, LO.side, lit("before")))
        g.add((uri, LO.display, lit(b.display(node))))
        g.add((uri, LO.line, lit(node.start_point.row + 1)))
        g.add((uri, LO.modifiers, lit(b.modifiers(node))))
        if b.key(node) not in excluded:
            g.add((uri, LO.checkScope, lit(True)))
        twin = after_members.get(b.key(node))
        if twin is not None:
            g.add((uri, LO.hasCounterpart, after_nodes[_k(twin)]))

    members = [_k(m) for m in b.members()]
    mb = ns("b", members.index(_k(source))) if _k(source) in members else ns("b", "src")
    g.add((mb, RDF.type, LO.Method))
    g.add((mb, LO.statementCount, lit(b.body_statements(source))))
    req_uri = URIRef(f"{LO}request")
    g.add((req_uri, RDF.type, LO.RefactoringRequest))
    g.add((req_uri, RDF.type, LO.ParameterizeVariableRequest))
    g.add((req_uri, LO.oldName, lit(req.old)))
    g.add((req_uri, LO.newName, lit(req.new)))
    g.add((req_uri, LO.newType, lit(req.new_type)))
    g.add((req_uri, LO.targetMethodBefore, mb))
    candidates = [m for m in a.methods() if a.name(m) == req.method]
    target = min(candidates, key=lambda m: abs(len(a.params(m)) - req.arity), default=None)
    g.add((req_uri, LO.requestedSignature, lit(req.signature)))
    g.add((req_uri, LO.targetMethodInInput, lit(any(b.name(m) == req.method for m in b.methods()))))
    g.add((req_uri, LO.targetSignatureInOutput, lit(any(
        a.name(m) == req.method and tuple(_norm_type(t) for _, t in a.params(m)) == req.param_types
        for m in a.methods()))))
    source_after = after_members.get(b.key(source)) or next(
        (m for m in a.methods() if a.name(m) == b.name(source) and m.type == source.type), None)
    if source_after is not None:
        sa = after_nodes[_k(source_after)]
        g.add((req_uri, LO.sourceMethodAfter, sa))
        same_as_target = target is not None and _k(source_after) == _k(target)
        for i, (lname, line, init, _) in enumerate([] if same_as_target else a.locals(source_after)):
            loc = URIRef(f"{sa}_sl{i}")
            g.add((sa, LO.declaresLocal, loc))
            g.add((loc, LO.name, lit(lname)))
            g.add((loc, LO.line, lit(line)))

    if target is None:
        return g
    ma = after_nodes[_k(target)]
    g.add((req_uri, LO.targetMethodAfter, ma))
    g.add((ma, RDF.type, LO.Method))
    g.add((ma, LO.name, lit(req.method)))
    g.add((ma, LO.statementCount, lit(a.body_statements(target))))
    if a.is_logging_helper(target):
        g.add((ma, LO.isLoggingHelper, lit(True)))
    cls = next((n for n in a.members() if n.type == "class_declaration"
                and n.start_byte <= target.start_byte < n.end_byte), None)
    if cls is not None:
        g.add((ma, LO.declaredIn, after_nodes[_k(cls)]))
    for i, (pname, ptype) in enumerate(a.params(target)):
        p = URIRef(f"{ma}_p{i}")
        g.add((ma, LO.hasParameter, p))
        g.add((p, LO.name, lit(pname)))
        g.add((p, LO.typeName, lit(ptype)))
    for i, (lname, line, init, _) in enumerate(a.locals(target)):
        loc = URIRef(f"{ma}_l{i}")
        g.add((ma, LO.declaresLocal, loc))
        g.add((loc, LO.name, lit(lname)))
        g.add((loc, LO.line, lit(line)))
        g.add((loc, LO.initializer, lit(init)))
    a_uses = {}
    for i, node in enumerate(a.identifier_uses(target, {req.old, req.new})):
        u = URIRef(f"{ma}_u{i}")
        a_uses[_k(node)] = u
        g.add((ma, LO.hasUse, u))
        g.add((u, LO.name, lit(a.text(node))))
        g.add((u, LO.line, lit(node.start_point.row + 1)))
        g.add((u, LO.resolvesKind, lit(_resolve(a, target, node))))
        g.add((u, LO.usageRole, lit(a.role(node))))

    # pairing of the old variable's uses in the source method with places in the target method
    after_rows = sorted({n.start_point.row for n in a.walk(target.child_by_field_name("body"))
                         if n.child_count == 0} if target.child_by_field_name("body") else set())
    old_decl_rows = {ln - 1 for n, ln, _, _ in a.locals(target) if n == req.old}
    for i, node in enumerate(b.identifier_uses(source, {req.old})):
        ub = URIRef(f"{mb}_u{i}")
        g.add((mb, LO.hasUse, ub))
        g.add((ub, LO.name, lit(req.old)))
        g.add((ub, LO.resolvesKind, lit("local")))
        g.add((ub, LO.line, lit(node.start_point.row + 1)))
        g.add((ub, LO.usageRole, lit(b.role(node))))
        btoks = b.line_tokens(source, node.start_point.row)
        bidx = next((k for k, t in enumerate(btoks) if t.start_byte == node.start_byte), None)
        best, best_ratio = None, 0.0
        for row in after_rows:
            if row in old_decl_rows:
                continue
            atoks = a.line_tokens(target, row)
            ratio = SequenceMatcher(None, [b.text(t) for t in btoks], [a.text(t) for t in atoks]).ratio()
            if ratio > best_ratio:
                best, best_ratio = atoks, ratio
        if best is None or bidx is None or best_ratio < 0.6:
            continue
        sm = SequenceMatcher(None, [b.text(t) for t in btoks], [a.text(t) for t in best])
        mapped = None
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if i1 <= bidx < i2 and tag in {"equal", "replace"} and (i2 - i1) == (j2 - j1):
                mapped = best[j1 + bidx - i1]
        if mapped is None:
            continue
        ua = a_uses.get(_k(mapped))
        if ua is None:
            ua = URIRef(f"{ub}_a")
            g.add((ua, LO.name, lit(a.text(mapped))))
            g.add((ua, LO.line, lit(mapped.start_point.row + 1)))
            g.add((ua, LO.resolvesKind, lit(_resolve(a, target, mapped))))
            g.add((ua, LO.usageRole, lit(a.role(mapped))))
        g.add((ub, LO.hasCounterpart, ua))
    return g
