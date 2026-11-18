"""Project ontology: TBox schema + ABox graph built from syntactic Java facts."""
from __future__ import annotations

import hashlib
from urllib.parse import quote

from llm_ontology.ontology.extract import JavaUnit

LO = "https://w3id.org/llm-ontology/project#"
SCHEMA_VERSION = "project-ontology-v1"  # not yet frozen in any run

# TBox. Kept deliberately small: only concepts the extractor can establish with
# certainty from the code the model sees.
SCHEMA_TTL = """@prefix lo: <https://w3id.org/llm-ontology/project#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

lo:Type a owl:Class ; rdfs:comment "A class, interface, enum or record declaration." .
lo:Member a owl:Class .
lo:Method a owl:Class ; rdfs:subClassOf lo:Member .
lo:Field a owl:Class ; rdfs:subClassOf lo:Member .
lo:Variable a owl:Class ; rdfs:comment "A parameter or local variable of one method." .
lo:ThrowSite a owl:Class ; rdfs:comment "A throw statement, its enclosing branches and earlier exits (not when it fires)." .
lo:Branch a owl:Class ; rdfs:comment "An if/switch/ternary/loop decision point." .
lo:Comparison a owl:Class ; rdfs:comment "A comparison of an expression with a literal." .
lo:CodeBlock a owl:Class ; rdfs:comment "A line range of one method (refactoring target)." .

lo:declaredIn a owl:ObjectProperty ; rdfs:domain lo:Member ; rdfs:range lo:Type .
lo:inMethod a owl:ObjectProperty ; rdfs:range lo:Method .
lo:hasParameter a owl:ObjectProperty ; rdfs:domain lo:Method ; rdfs:range lo:Variable .
lo:readsField a owl:ObjectProperty ; rdfs:domain lo:Method ; rdfs:range lo:Field .
lo:requiresInput a owl:ObjectProperty ; rdfs:domain lo:CodeBlock ; rdfs:range lo:Variable .
lo:producesOutput a owl:ObjectProperty ; rdfs:domain lo:CodeBlock ; rdfs:range lo:Variable .
lo:writesField a owl:ObjectProperty ; rdfs:domain lo:CodeBlock ; rdfs:range lo:Field .

lo:name a owl:DatatypeProperty .
lo:typeName a owl:DatatypeProperty .
lo:kind a owl:DatatypeProperty .
lo:signature a owl:DatatypeProperty .
lo:returns a owl:DatatypeProperty .
lo:modifier a owl:DatatypeProperty .
lo:declaresThrows a owl:DatatypeProperty .
lo:exceptionType a owl:DatatypeProperty .
lo:enclosedBy a owl:DatatypeProperty ; rdfs:comment "Enclosing branches, outermost first, joined by ' > '." .
lo:earlierExitAt a owl:DatatypeProperty ; rdfs:range xsd:integer .
lo:overloads a owl:DatatypeProperty ; rdfs:range xsd:integer .
lo:condition a owl:DatatypeProperty .
lo:subject a owl:DatatypeProperty .
lo:operator a owl:DatatypeProperty .
lo:value a owl:DatatypeProperty .
lo:nullCheck a owl:DatatypeProperty .
lo:calls a owl:DatatypeProperty .
lo:initializer a owl:DatatypeProperty .
lo:line a owl:DatatypeProperty ; rdfs:range xsd:integer .
lo:startLine a owl:DatatypeProperty ; rdfs:range xsd:integer .
lo:endLine a owl:DatatypeProperty ; rdfs:range xsd:integer .
lo:position a owl:DatatypeProperty ; rdfs:range xsd:integer .
lo:usedAt a owl:DatatypeProperty ; rdfs:range xsd:integer .
lo:calledAt a owl:DatatypeProperty ; rdfs:range xsd:integer ; rdfs:comment "Unqualified/this/super call (constructor: new) by name only." .
lo:referencedAt a owl:DatatypeProperty ; rdfs:range xsd:integer .
lo:containsReturn a owl:DatatypeProperty ; rdfs:range xsd:boolean .
lo:containsJump a owl:DatatypeProperty ; rdfs:range xsd:boolean .
"""


def schema_sha256() -> str:
    return hashlib.sha256(SCHEMA_TTL.encode()).hexdigest()


def _rdf():
    try:
        import rdflib
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError("The project ontology needs rdflib: pip install -e '.[ontology]'") from exc
    return rdflib


def build_graph(source: str, *, block: tuple[int, int] | None = None):
    """ABox for one supplied compilation unit (plus an optional target line range)."""
    rdflib = _rdf()
    from rdflib import RDF, Literal, Namespace, URIRef
    from rdflib.namespace import XSD

    lo = Namespace(LO)
    unit = JavaUnit(source)
    graph = rdflib.Graph()
    graph.bind("lo", lo)

    def node(*parts) -> URIRef:
        return URIRef("urn:unit:" + "/".join(quote(str(p), safe="") for p in parts))

    def integer(value: int):
        return Literal(value, datatype=XSD.integer)

    for name, kind, start, end in unit.types():
        t = node("type", name)
        graph.add((t, RDF.type, lo.Type))
        graph.add((t, lo.name, Literal(name)))
        graph.add((t, lo.kind, Literal(kind)))
        graph.add((t, lo.startLine, integer(start)))
        graph.add((t, lo.endLine, integer(end)))
        for line in unit.type_references(name):
            graph.add((t, lo.referencedAt, integer(line)))

    fields = {}
    for f in unit.fields():
        fn = node("field", f.owner, f.name)
        fields[f.name] = fn
        graph.add((fn, RDF.type, lo.Field))
        graph.add((fn, lo.declaredIn, node("type", f.owner.split(".")[-1])))
        graph.add((fn, lo.name, Literal(f.name)))
        graph.add((fn, lo.typeName, Literal(f.type)))
        graph.add((fn, lo.line, integer(f.line)))
        for modifier in f.modifiers:
            graph.add((fn, lo.modifier, Literal(modifier)))
        if f.initializer is not None:
            graph.add((fn, lo.initializer, Literal(f.initializer)))

    for method in unit.method_nodes():
        facts = unit.method_facts(method)
        m = node("method", facts.owner, facts.name, facts.start)
        graph.add((m, RDF.type, lo.Method))
        graph.add((m, lo.declaredIn, node("type", facts.owner.split(".")[-1])))
        graph.add((m, lo.name, Literal(facts.name)))
        graph.add((m, lo.kind, Literal(facts.kind)))
        graph.add((m, lo.signature, Literal(facts.signature)))
        graph.add((m, lo.returns, Literal(facts.return_type)))
        graph.add((m, lo.startLine, integer(facts.start)))
        graph.add((m, lo.endLine, integer(facts.end)))
        for modifier in facts.modifiers:
            graph.add((m, lo.modifier, Literal(modifier)))
        for exc in facts.declared_throws:
            graph.add((m, lo.declaresThrows, Literal(exc)))
        for i, site in enumerate(facts.throws):
            s = node("throw", facts.owner, facts.name, facts.start, i)
            graph.add((s, RDF.type, lo.ThrowSite))
            graph.add((s, lo.inMethod, m))
            graph.add((s, lo.exceptionType, Literal(site.exception)))
            graph.add((s, lo.line, integer(site.line)))
            if site.enclosing:
                graph.add((s, lo.enclosedBy, Literal(" > ".join(site.enclosing))))
            for line in site.earlier_exits:
                graph.add((s, lo.earlierExitAt, integer(line)))
        for i, branch in enumerate(facts.branches):
            b = node("branch", facts.owner, facts.name, facts.start, i)
            graph.add((b, RDF.type, lo.Branch))
            graph.add((b, lo.inMethod, m))
            graph.add((b, lo.kind, Literal(branch.kind)))
            graph.add((b, lo.condition, Literal(branch.condition)))
            graph.add((b, lo.line, integer(branch.line)))
        for i, comparison in enumerate(facts.comparisons):
            c = node("comparison", facts.owner, facts.name, facts.start, i)
            graph.add((c, RDF.type, lo.Comparison))
            graph.add((c, lo.inMethod, m))
            graph.add((c, lo.subject, Literal(comparison.subject)))
            graph.add((c, lo.operator, Literal(comparison.operator)))
            graph.add((c, lo.value, Literal(comparison.value)))
            graph.add((c, lo.line, integer(comparison.line)))
        for check in facts.null_checks:
            graph.add((m, lo.nullCheck, Literal(check)))
        for name in facts.fields_read:
            if name in fields:
                graph.add((m, lo.readsField, fields[name]))
        for call in facts.calls:
            graph.add((m, lo.calls, Literal(call)))
        graph.add((m, lo.overloads, integer(unit.overloads(facts.name))))
        for line in unit.call_sites(facts.name, constructor=facts.kind == "constructor"):
            graph.add((m, lo.calledAt, integer(line)))
        for position, local in enumerate(unit.locals(method)):
            v = node("var", facts.owner, facts.name, facts.start, local.name, local.line)
            graph.add((v, RDF.type, lo.Variable))
            graph.add((v, lo.inMethod, m))
            graph.add((v, lo.name, Literal(local.name)))
            graph.add((v, lo.typeName, Literal(local.type)))
            graph.add((v, lo.kind, Literal(local.kind)))
            graph.add((v, lo.line, integer(local.line)))
            if local.kind == "parameter":
                graph.add((m, lo.hasParameter, v))
                graph.add((v, lo.position, integer(position)))
            if local.initializer is not None:
                graph.add((v, lo.initializer, Literal(local.initializer)))
            for line in local.uses:
                graph.add((v, lo.usedAt, integer(line)))

    if block is not None:
        facts = unit.block_facts(*block)
        if facts is not None:
            b = node("block", block[0], block[1])
            graph.add((b, RDF.type, lo.CodeBlock))
            graph.add((b, lo.startLine, integer(block[0])))
            graph.add((b, lo.endLine, integer(block[1])))
            graph.add((b, lo.containsReturn, Literal(facts.has_return)))
            graph.add((b, lo.containsJump, Literal(facts.has_jump)))
            method = unit.enclosing_method(block[0])
            mf = unit.method_facts(method)
            m = node("method", mf.owner, mf.name, mf.start)
            graph.add((b, lo.inMethod, m))
            for relation, params in ((lo.requiresInput, facts.inputs), (lo.producesOutput, facts.outputs)):
                for param in params:
                    for v in graph.subjects(lo.name, Literal(param.name)):
                        if (v, lo.inMethod, m) in graph and (v, RDF.type, lo.Variable) in graph:
                            graph.add((b, relation, v))
            for name in facts.fields_written:
                if name in fields:
                    graph.add((b, lo.writesField, fields[name]))
    return graph


def graph_ntriples(graph) -> str:
    """Deterministic serialisation (sorted N-Triples) for hashing and freezing."""
    return "\n".join(sorted(graph.serialize(format="nt").strip().splitlines())) + "\n"
