"""Exact paired significance tests shared by both matrix reports (no SciPy).

* McNemar exact test for paired pass/fail outcomes: two-sided binomial test on
  the discordant pairs (``a_only`` vs ``b_only``) with p = 0.5.
* Wilcoxon signed-rank test for paired continuous values (coverage credit):
  zero differences are dropped, tied |d| receive mid-ranks and the p-value is
  the exact two-sided permutation p-value conditional on those ranks.
* Holm step-down correction across the arm pairs of one metric family.

Cases are convenience-selected and may be clustered by project, so the
p-values are conditional on the selected cases, not population inference.
"""

from __future__ import annotations

from math import comb

ALPHA = 0.05


def mcnemar_exact(a_only: int, b_only: int) -> dict:
    """Two-sided exact McNemar test from the two discordant counts."""
    if a_only < 0 or b_only < 0:
        raise ValueError("Discordant counts must be non-negative")
    n = a_only + b_only
    if n == 0:
        return {"test": "mcnemar_exact", "discordant": 0, "a_only": 0, "b_only": 0,
                "p_value": None, "reason": "no_discordant_pairs"}
    k = min(a_only, b_only)
    tail = sum(comb(n, i) for i in range(k + 1)) / 2 ** n
    return {"test": "mcnemar_exact", "discordant": n, "a_only": a_only, "b_only": b_only,
            "p_value": min(1.0, 2 * tail), "reason": None}


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def wilcoxon_signed_rank(differences: list[float]) -> dict:
    """Exact two-sided Wilcoxon signed-rank test (zeros dropped, mid-ranks for ties)."""
    nonzero = [d for d in differences if d != 0]
    n = len(nonzero)
    base = {"test": "wilcoxon_signed_rank_exact", "pairs": len(differences),
            "nonzero_pairs": n, "zero_differences": len(differences) - n}
    if n == 0:
        return {**base, "w_plus": None, "w_minus": None, "p_value": None,
                "reason": "all_differences_zero" if differences else "no_pairs"}
    ranks = _ranks([abs(d) for d in nonzero])
    doubled = [round(2 * r) for r in ranks]  # mid-ranks are multiples of 0.5
    w_plus2 = sum(r for r, d in zip(doubled, nonzero) if d > 0)
    total2 = sum(doubled)
    # Null distribution of the (doubled) positive rank sum: every sign equally likely.
    counts = [0] * (total2 + 1)
    counts[0] = 1
    reach = 0
    for r in doubled:
        reach += r
        for s in range(reach, r - 1, -1):
            counts[s] += counts[s - r]
    observed = min(w_plus2, total2 - w_plus2)
    tail = sum(counts[: observed + 1]) / 2 ** n
    return {**base, "w_plus": w_plus2 / 2, "w_minus": (total2 - w_plus2) / 2,
            "p_value": min(1.0, 2 * tail), "reason": None}


def holm(p_values: dict[str, float | None], alpha: float = ALPHA) -> dict[str, dict]:
    """Holm-Bonferroni adjusted p-values for one family; ``None`` stays untested."""
    tested = sorted((p, key) for key, p in p_values.items() if p is not None)
    m = len(tested)
    adjusted: dict[str, dict] = {}
    running = 0.0
    for index, (p, key) in enumerate(tested):
        running = max(running, min(1.0, (m - index) * p))
        adjusted[key] = {"p_holm": running, "reject_at_0_05": running < alpha, "family_size": m}
    for key, p in p_values.items():
        if p is None:
            adjusted[key] = {"p_holm": None, "reject_at_0_05": None, "family_size": m}
    return adjusted
