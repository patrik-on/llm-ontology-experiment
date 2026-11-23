"""Overí SHACL tvary návrhu na ručne zostavených dátach (bez modelu a bez Javy).

Spustenie z koreňa repa:  python thesis_materials/2026-11-23_navrh_slucka_c_d/priklady/validate.py
Potrebuje: pip install pyshacl  (rdflib 7 je už v extra 'ontology')
"""
from pathlib import Path

from pyshacl import validate
from rdflib import Graph
from rdflib.namespace import SH

HERE = Path(__file__).resolve().parent
for task in ("testing", "refactoring"):
    data = Graph().parse(HERE / f"{task}_data.ttl")
    shapes = Graph().parse(HERE.parent / f"shapes_{task}.ttl")
    conforms, report, _ = validate(data, shacl_graph=shapes, advanced=True)
    messages = sorted(str(m) for m in report.objects(None, SH.resultMessage))
    print(f"{task}: conforms={conforms}, violations={len(messages)}")
    for message in messages:
        print("  -", message)
