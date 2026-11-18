"Read-only JUnit testcase outcome parsing for the current Methods2Test evaluator."

from __future__ import annotations

from pathlib import Path

import xml.etree.ElementTree as ET


def test_outcomes(reports: Path) -> list[dict]:
    result = []
    for p in sorted(reports.glob("TEST-*.xml")):
        root = ET.parse(p).getroot()
        for test in root.iter("testcase"):
            name = test.get("classname", "")
            if not name.endswith(".GeneratedBodyTests"):
                continue
            states = [
                state for state in ["failure", "error", "skipped"] if test.find(state) is not None
            ]
            result.append(
                {
                    "class": name,
                    "test": test.get("name"),
                    "status": states[0] if states else "passed",
                    "type": test.find(states[0]).get("type") if states else None,
                }
            )
    return sorted(result, key=lambda r: (r["class"], r["test"]))
