"""SPARQL views over the project ontology, verbalised as a short deterministic block.

The graph is the source of truth; prompts only ever see the text these queries render.
Output is sorted, capped and contains nothing that is not in the supplied source.
"""
from __future__ import annotations

import re

from llm_ontology.ontology.graph import LO, build_graph

PREFIX = f"PREFIX lo: <{LO}>\n"
MAX_ITEMS = 12
MAX_VARIABLES = 6
IDENTIFIER = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
OPEN, CLOSE = "<project-ontology>", "</project-ontology>"


def _rows(graph, query: str, **bindings) -> list[tuple]:
    from rdflib import Literal
    from rdflib.term import Identifier
    init = {k: (v if isinstance(v, Identifier) else Literal(v)) for k, v in bindings.items()}
    return [tuple(None if x is None else x.toPython() for x in row)
            for row in graph.query(PREFIX + query, initBindings=init)]


def _cap(items: list[str]) -> str:
    items = list(dict.fromkeys(items))
    extra = len(items) - MAX_ITEMS
    return ", ".join(items[:MAX_ITEMS]) + (f" (+{extra} more)" if extra > 0 else "")


def _lines(values) -> str:
    values = sorted(set(values))
    return _cap([str(v) for v in values]) if values else "none"


def _short(text: str, limit: int = 60) -> str:
    """Long expressions are cut (marked with ...) so one initialiser cannot dominate the block."""
    if len(text) <= limit:
        return text
    cut = text[: limit - 3]
    if text[limit - 3].isalnum() or text[limit - 3] in "_$":  # never split a name in two
        cut = re.sub(r"[A-Za-z0-9_$]+$", "", cut)
    return cut.rstrip() + "..."


def _wrap(lines: list[str]) -> str:
    return OPEN + "\n" + "\n".join(lines) + "\n" + CLOSE


def boundary_values(operator: str, value: str) -> list[str]:
    """Integer neighbours on both sides of a comparison with a literal."""
    try:
        number = int(value.replace("_", "").rstrip("lL"), 0)
    except ValueError:
        return [value]
    return [str(v) for v in {"<": (number - 1, number), "<=": (number, number + 1),
                              ">": (number, number + 1), ">=": (number - 1, number),
                              "==": (number - 1, number, number + 1),
                              "!=": (number - 1, number, number + 1)}[operator]]


# ---------------------------------------------------------------------------- testing


def testing_view(source: str, method_name: str, class_name: str = "") -> str:
    graph = build_graph(source)
    methods = _rows(graph, """SELECT ?m ?sig ?start WHERE { ?m a lo:Method ; lo:name ?name ;
        lo:signature ?sig ; lo:startLine ?start . } ORDER BY ?start""", name=method_name)
    if not methods:
        raise ValueError("Focal method not found in supplied source: " + method_name)
    lines = []
    from rdflib import URIRef

    for m, signature, _ in methods:
        m = URIRef(m)
        lines.append(f"Focal method: {signature}" + (f" in {class_name}" if class_name else ""))
        declared = [r[0] for r in _rows(graph, "SELECT ?e WHERE { ?m lo:declaresThrows ?e } ORDER BY ?e", m=m)]
        if declared:
            lines.append("Declared throws: " + _cap(declared))
        for s, exc, path, line in _rows(graph, """SELECT ?s ?e ?g ?l WHERE { ?s a lo:ThrowSite ; lo:inMethod ?m ;
                lo:exceptionType ?e ; lo:line ?l . OPTIONAL { ?s lo:enclosedBy ?g } } ORDER BY ?l""", m=m):
            exits = [e for (e,) in _rows(graph, "SELECT ?x WHERE { ?s lo:earlierExitAt ?x } ORDER BY ?x", s=URIRef(s))]
            lines.append(f"throw {exc} at line {line}; enclosing branches: {path or 'none'}; "
                         f"earlier return/throw at lines {_lines(exits)}")
        branches = [f"{kind} {cond}".replace("if if", "if") for kind, cond, _ in _rows(graph, """
            SELECT ?k ?c ?l WHERE { ?b a lo:Branch ; lo:inMethod ?m ; lo:kind ?k ; lo:condition ?c ;
            lo:line ?l } ORDER BY ?l""", m=m)]
        lines.append(f"Decision points ({len(branches)}): " + (_cap(branches) if branches else "none"))
        constants = {name: init for name, init in _rows(graph, """SELECT ?n ?i WHERE { ?f a lo:Field ;
            lo:name ?n ; lo:initializer ?i ; lo:modifier "final" }""")}
        boundaries = []
        for subject, op, value, _ in _rows(graph, """SELECT ?s ?o ?v ?l WHERE { ?c a lo:Comparison ;
                lo:inMethod ?m ; lo:subject ?s ; lo:operator ?o ; lo:value ?v ; lo:line ?l } ORDER BY ?l""", m=m):
            literal = constants.get(value, value)
            if boundary_values(op, literal) == [literal]:
                continue  # no integer value known for certain: nothing to suggest
            shown = f"{value} (= {literal})" if literal != value else value
            boundaries.append(f"{subject} {op} {shown} -> try {subject} = {' / '.join(boundary_values(op, literal))}")
        if boundaries:
            lines.append("Boundary candidates: " + "; ".join(dict.fromkeys(boundaries[:MAX_ITEMS])))
        nulls = [r[0] for r in _rows(graph, "SELECT ?n WHERE { ?m lo:nullCheck ?n } ORDER BY ?n", m=m)]
        if nulls:
            lines.append("Null checks: " + _cap(nulls))
        read = [f"{name} : {type_}" + (f" = {_short(init)}" if init is not None else "")
                for name, type_, init in _rows(graph, """SELECT ?n ?t ?i WHERE { ?m lo:readsField ?f .
                ?f lo:name ?n ; lo:typeName ?t . OPTIONAL { ?f lo:initializer ?i } } ORDER BY ?n""", m=m)]
        if read:
            lines.append("Reads fields: " + _cap(read))
        calls = [r[0] for r in _rows(graph, "SELECT ?c WHERE { ?m lo:calls ?c } ORDER BY ?c", m=m)]
        if calls:
            lines.append("Calls: " + _cap(calls))
    others = [sig for sig, name in _rows(graph, """SELECT ?sig ?n WHERE { ?x a lo:Method ; lo:signature ?sig ;
        lo:name ?n ; lo:modifier "public" } ORDER BY ?sig""") if name != method_name]
    lines.append("Other public methods in supplied source: " + (_cap(others) if others else "none"))
    return _wrap(lines)


# ------------------------------------------------------------------------ refactoring

VARIABLE_OPERATIONS = {"Rename Variable", "Inline Variable", "Extract Variable", "Parameterize Variable",
                       "Replace Variable With Attribute"}
PARAMETER_OPERATIONS = {"Rename Parameter", "Remove Parameter"}
METHOD_OPERATIONS = {"Rename Method", "Inline Method"}


def _enclosing_method(graph, start: int):
    rows = _rows(graph, """SELECT ?m ?sig ?s ?e ?owner WHERE { ?m a lo:Method ; lo:signature ?sig ;
        lo:startLine ?s ; lo:endLine ?e ; lo:declaredIn ?t . ?t lo:name ?owner .
        FILTER(?s <= ?line && ?line <= ?e) }""", line=start)
    return min(rows, key=lambda r: (r[3] - r[2], r[2])) if rows else None


def refactoring_view(source: str, operation: str, start: int, end: int, request: str = "") -> str:
    """``request`` is the public task text every arm receives; it only orders and selects facts."""
    from rdflib import URIRef

    graph = build_graph(source, block=(start, end))
    lines = []
    enclosing = _enclosing_method(graph, start)
    covered = None
    if enclosing is None:  # e.g. a target range that starts at a method's Javadoc
        inside = _rows(graph, """SELECT ?m ?sig ?s ?e ?owner WHERE { ?m a lo:Method ; lo:signature ?sig ;
            lo:startLine ?s ; lo:endLine ?e ; lo:declaredIn ?t . ?t lo:name ?owner .
            FILTER(?start <= ?s && ?e <= ?end) }""", start=start, end=end)
        covered = inside[0] if len(inside) == 1 else None
    types = _rows(graph, """SELECT ?n ?k ?s ?e WHERE { ?t a lo:Type ; lo:name ?n ; lo:kind ?k ;
        lo:startLine ?s ; lo:endLine ?e . FILTER(?s <= ?line && ?line <= ?e) }""", line=start)
    owner = min(types, key=lambda r: r[3] - r[2])[0] if types else None
    if enclosing is not None:
        lines.append(f"Target lines {start}..{end} are inside {enclosing[1]} of {enclosing[4]} "
                     f"(lines {enclosing[2]}..{enclosing[3]})")
    elif covered is not None:
        lines.append(f"Target lines {start}..{end} contain the whole method {covered[1]} of {covered[4]} "
                     f"(lines {covered[2]}..{covered[3]})")
    elif owner:
        lines.append(f"Target lines {start}..{end} are declarations of type {owner}")
    if owner:
        members = _rows(graph, """SELECT ?n ?kind WHERE { ?x lo:declaredIn ?t ; lo:name ?n ; a ?kind .
            ?t lo:name ?owner . } ORDER BY ?n""", owner=owner)
        fields = [n for n, kind in members if kind.endswith("Field")]
        methods = [n for n, kind in members if kind.endswith("Method")]
        lines.append(f"Fields of {owner}: " + (_cap(fields) if fields else "none"))
        lines.append(f"Methods of {owner}: " + (_cap(methods) if methods else "none"))
    m = URIRef(enclosing[0]) if enclosing is not None else None

    if m is not None:
        scope = [n for (n,) in _rows(graph, "SELECT ?n WHERE { ?v a lo:Variable ; lo:inMethod ?m ; lo:name ?n } ORDER BY ?n", m=m)]
        lines.append(f"Names already declared in {_name(graph, m)}: " + (_cap(scope) if scope else "none"))

    if operation in {"Extract Method", "Extract Variable"} and m is not None:
        block = _rows(graph, """SELECT ?b ?r ?j WHERE { ?b a lo:CodeBlock ; lo:containsReturn ?r ;
            lo:containsJump ?j }""")
        if block:
            b = URIRef(block[0][0])
            inputs = [f"{n} : {t}" for n, t in _rows(graph, """SELECT ?n ?t WHERE { ?b lo:requiresInput ?v .
                ?v lo:name ?n ; lo:typeName ?t } ORDER BY ?n""", b=b)]
            outputs = [f"{n} : {t}" for n, t in _rows(graph, """SELECT ?n ?t WHERE { ?b lo:producesOutput ?v .
                ?v lo:name ?n ; lo:typeName ?t } ORDER BY ?n""", b=b)]
            written = [n for (n,) in _rows(graph, """SELECT ?n WHERE { ?b lo:writesField ?f . ?f lo:name ?n }
                ORDER BY ?n""", b=b)]
            lines.append(f"Lines {start}..{end} read variables declared earlier: " + (_cap(inputs) if inputs else "none"))
            lines.append(f"Lines {start}..{end} assign variables used after line {end}: "
                         + (_cap(outputs) if outputs else "none"))
            lines.append(f"Lines {start}..{end} write fields: " + (_cap(written) if written else "none"))
            lines.append(f"Lines {start}..{end} contain return: {'yes' if block[0][1] else 'no'}; "
                         f"break/continue: {'yes' if block[0][2] else 'no'}")

    if operation in VARIABLE_OPERATIONS and m is not None:
        declared = _rows(graph, """SELECT ?n ?t ?k ?l ?i WHERE { ?v a lo:Variable ;
                lo:inMethod ?m ; lo:name ?n ; lo:typeName ?t ; lo:kind ?k ; lo:line ?l .
                OPTIONAL { ?v lo:initializer ?i } FILTER(?l >= ?s && ?l <= ?e) } ORDER BY ?l ?n""",
                m=m, s=start, e=end)
        named = set(IDENTIFIER.findall(request))
        # Variables the public request names come first; the rest is capped.
        declared.sort(key=lambda r: (r[0] not in named, r[3], r[0]))
        for name, type_, kind, line, init in declared[:MAX_VARIABLES]:
            uses = [u for (u,) in _rows(graph, """SELECT ?u WHERE { ?v lo:inMethod ?m ; lo:name ?n ; lo:line ?l ;
                lo:usedAt ?u }""", m=m, n=name, l=line)]
            lines.append(f"{'Parameter' if kind == 'parameter' else 'Local'} {name} : {type_} declared at line {line}"
                         + (f", initialised with {_short(init)}" if init else "") + f"; used at lines {_lines(uses)}")
        if len(declared) > MAX_VARIABLES:
            lines.append(f"(+{len(declared) - MAX_VARIABLES} more variables declared in lines {start}..{end})")

    if operation in PARAMETER_OPERATIONS and m is not None:
        parameters = _rows(graph, """SELECT ?n ?t ?p WHERE { ?m lo:hasParameter ?v . ?v lo:name ?n ;
                lo:typeName ?t ; lo:position ?p } ORDER BY ?p""", m=m)
        named = set(IDENTIFIER.findall(request))
        parameters.sort(key=lambda r: (r[0] not in named, r[2]))
        for name, type_, _ in parameters[:MAX_VARIABLES]:
            uses = [u for (u,) in _rows(graph, """SELECT ?u WHERE { ?m lo:hasParameter ?v . ?v lo:name ?n ;
                lo:usedAt ?u }""", m=m, n=name)]
            lines.append(f"Parameter {name} : {type_} used at lines {_lines(uses)}")
        if len(parameters) > MAX_VARIABLES:
            lines.append(f"(+{len(parameters) - MAX_VARIABLES} more parameters)")
        lines.append(_call_line(graph, m, f"Calls to {_name(graph, m)}"))

    if operation in METHOD_OPERATIONS:
        target = _rows(graph, """SELECT ?x ?sig ?s ?e WHERE { ?x a lo:Method ; lo:signature ?sig ;
            lo:startLine ?s ; lo:endLine ?e . FILTER(?s <= ?end && ?e >= ?start) } ORDER BY ?s""",
            start=start, end=end)
        for x, sig, s, e in target[:3]:
            lines.append(f"Method {sig} spans lines {s}..{e}; " + _call_line(graph, URIRef(x), "calls"))

    if operation == "Rename Class":
        for name, s, e in _rows(graph, """SELECT ?n ?s ?e WHERE { ?t a lo:Type ; lo:name ?n ; lo:startLine ?s ;
                lo:endLine ?e . FILTER(?s <= ?end && ?e >= ?start) } ORDER BY ?s""", start=start, end=end):
            refs = [r for (r,) in _rows(graph, "SELECT ?r WHERE { ?t lo:name ?n ; lo:referencedAt ?r }", n=name)]
            ctors = [c for (c,) in _rows(graph, """SELECT ?l WHERE { ?c a lo:Method ; lo:kind "constructor" ;
                lo:name ?n ; lo:startLine ?l }""", n=name)]
            lines.append(f"Type {name} spans lines {s}..{e}; constructors at lines {_lines(ctors)}; "
                         f"type name referenced at lines {_lines(refs)}")
    return _wrap(lines)


def _name(graph, m) -> str:
    rows = _rows(graph, "SELECT ?n WHERE { ?m lo:name ?n }", m=m)
    return rows[0][0] if rows else "?"


def _call_line(graph, m, label: str) -> str:
    """Call sites matched by name only; flagged when the name is overloaded in the source."""
    calls = [c for (c,) in _rows(graph, "SELECT ?c WHERE { ?m lo:calledAt ?c }", m=m)]
    overloads = _rows(graph, "SELECT ?o WHERE { ?m lo:overloads ?o }", m=m)
    count = overloads[0][0] if overloads else 1
    constructor = bool(_rows(graph, 'SELECT ?k WHERE { ?m lo:kind "constructor" }', m=m))
    how = "as new expressions" if constructor else "by name (unqualified or this/super)"
    text = f"{label} {how} at lines {_lines(calls)}"
    return text + (f"; name has {count} declarations, calls not resolved to one" if count > 1 else "")
