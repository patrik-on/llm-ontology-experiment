# configs/skills

Pinned copies of the process skills used by the `skills` arm of both matrices.
They are byte-identical copies from `patrik-on/si-context-eval`, so a fresh clone
can reproduce the arm without a sibling checkout.

| File | Source | SHA-256 |
|---|---|---|
| `testing/SKILL.md` | `si-context-eval@57ce66062f53ed5366741a8add866e136e8f9f2c:skills/testing/SKILL.md` | `b6bfbaa48467a9f759fff61e8a28d804be74a14d8ed840f425dc2c5bfe6afb72` |
| `refactoring/SKILL.md` | `si-context-eval@57ce66062f53ed5366741a8add866e136e8f9f2c:skills/refactoring/SKILL.md` | `c6f3292ceb44f266b6445c53f90c59b64b5a50f12437371cae94d1c61e30dbd3` |

Do not edit these files: the run freezes copy and hash them, and any change is a
new experimental condition. `tests/test_skills_pinned.py` guards the hashes.
To use another copy for a testing run, pass `--skill-file` or set `SI_CONTEXT_EVAL_REPO`.
