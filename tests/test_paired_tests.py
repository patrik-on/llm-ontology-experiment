from __future__ import annotations

from itertools import product

import pytest

from llm_ontology.benchmarks.paired_tests import _ranks, holm, mcnemar_exact, wilcoxon_signed_rank


def test_mcnemar_exact_matches_binomial():
    assert mcnemar_exact(0, 5)["p_value"] == pytest.approx(2 / 32)
    assert mcnemar_exact(3, 3)["p_value"] == 1.0
    assert mcnemar_exact(2, 10)["p_value"] == pytest.approx(0.0385742187, abs=1e-9)
    assert mcnemar_exact(0, 0)["p_value"] is None


def test_wilcoxon_exact_without_ties():
    result = wilcoxon_signed_rank([0.1, 0.2, 0.3, 0.4, 0.5])
    assert result["p_value"] == pytest.approx(2 / 32)
    assert result["w_plus"] == 15 and result["w_minus"] == 0
    assert wilcoxon_signed_rank([0, 0])["reason"] == "all_differences_zero"
    assert wilcoxon_signed_rank([])["reason"] == "no_pairs"


@pytest.mark.parametrize("diffs", [[0.1, -0.1, 0.2, 0.2, 0, 0.3], [0.5, 0.5, -0.5, 0.25, 0.25, 0.25, -0.1]])
def test_wilcoxon_with_ties_matches_brute_force(diffs):
    nonzero = [d for d in diffs if d]
    ranks = _ranks([abs(d) for d in nonzero])
    total = sum(ranks)
    observed = sum(r for r, d in zip(ranks, nonzero) if d > 0)
    extreme = min(observed, total - observed)
    hits = sum(
        min(s, total - s) <= extreme + 1e-9
        for s in (sum(r for r, sign in zip(ranks, signs) if sign) for signs in product([0, 1], repeat=len(ranks)))
    )
    assert wilcoxon_signed_rank(diffs)["p_value"] == pytest.approx(min(1.0, hits / 2 ** len(ranks)))


def test_holm_is_monotone_and_keeps_untested():
    adjusted = holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": None})
    assert adjusted["a"]["p_holm"] == pytest.approx(0.03)
    assert adjusted["c"]["p_holm"] == pytest.approx(0.06)
    assert adjusted["b"]["p_holm"] == pytest.approx(0.06)
    assert adjusted["a"]["reject_at_0_05"] and not adjusted["b"]["reject_at_0_05"]
    assert adjusted["d"] == {"p_holm": None, "reject_at_0_05": None, "family_size": 3}
