from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PINNED = {
    "configs/skills/testing/SKILL.md": "b6bfbaa48467a9f759fff61e8a28d804be74a14d8ed840f425dc2c5bfe6afb72",
    "configs/skills/refactoring/SKILL.md": "c6f3292ceb44f266b6445c53f90c59b64b5a50f12437371cae94d1c61e30dbd3",
}


def test_vendored_skills_match_pinned_hashes():
    for path, expected in PINNED.items():
        assert hashlib.sha256((REPO / path).read_bytes()).hexdigest() == expected, path
