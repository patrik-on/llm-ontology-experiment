"""Overí SHACL tvary návrhu na správnom aj chybnom riešení (bez modelu a bez Javy).

Každé pravidlo musí na správnom riešení prejsť a na chybnom ho zachytiť. Výsledok má tri hodnoty:
porušenie (sh:Violation), „nevieme posúdiť“ (sh:Info) a v poriadku.

Spustenie z koreňa repa:  python thesis_materials/2026-11-23_navrh_slucka_c_d/priklady/validate.py
Potrebuje: pip install pyshacl  (rdflib 7 je už v extra 'ontology')
"""
import sys
from collections import Counter
from pathlib import Path

from pyshacl import validate
from rdflib import Graph
from rdflib.namespace import SH

HERE = Path(__file__).resolve().parent
EXPECTED = {  # (porušenia, nevieme posúdiť)
    ("testing", "spravne"): (0, 0), ("testing", "chybne"): (8, 2),
    ("refactoring", "spravne"): (0, 0), ("refactoring", "chybne"): (13, 1),
}
failed = False
for (task, variant), expected in EXPECTED.items():
    data = Graph().parse(HERE / f"{task}_{variant}.ttl")
    shapes = Graph().parse(HERE.parent / f"shapes_{task}.ttl")
    _, report, _ = validate(data, shacl_graph=shapes, advanced=True)
    rows = sorted((str(report.value(r, SH.resultSeverity)).rsplit("#", 1)[-1], str(report.value(r, SH.resultMessage)))
                  for r in report.subjects(SH.resultSeverity, None))
    counts = Counter(severity for severity, _ in rows)
    got = (counts["Violation"], counts["Info"])
    status = "OK" if got == expected else "NEZHODA"
    failed |= got != expected
    print(f"{task}/{variant}: porušenia={got[0]}, nevieme posúdiť={got[1]} (očakávané {expected}) {status}")
    for severity, message in rows:
        print(f"  [{severity}] {message}")
sys.exit(1 if failed else 0)
