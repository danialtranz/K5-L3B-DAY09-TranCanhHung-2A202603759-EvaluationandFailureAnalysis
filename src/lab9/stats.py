"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import comb

import numpy as np
from scipy.stats import bootstrap

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    tp = fp = fn = tn = 0
    for h, j in zip(human, judge):
        h_pos, j_pos = h == POS, j == POS
        if h_pos and j_pos:
            tp += 1
        elif not h_pos and j_pos:
            fp += 1
        elif h_pos and not j_pos:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    prec_den = cm["tp"] + cm["fp"]
    rec_den = cm["tp"] + cm["fn"]
    precision = cm["tp"] / prec_den if prec_den else 0.0
    recall = cm["tp"] / rec_den if rec_den else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    n = len(human)
    if n == 0:
        raise ValueError("empty labels")
    agree = sum(h == j for h, j in zip(human, judge)) / n
    labels = set(human) | set(judge)
    p_e = 0.0
    for lab in labels:
        p_e += (sum(h == lab for h in human) / n) * (sum(j == lab for j in judge) / n)
    if p_e == 1.0:
        raise ValueError("kappa undefined when expected agreement is 1")
    return (agree - p_e) / (1.0 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    den = sensitivity + specificity - 1.0
    if den == 0:
        return 0.0
    raw = (observed_rate + specificity - 1.0) / den
    return float(min(1.0, max(0.0, raw)))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    aa = np.asarray(list(a), dtype=float)
    bb = np.asarray(list(b), dtype=float)
    if aa.shape != bb.shape:
        raise ValueError("paired bootstrap requires equal-length sequences")
    if np.array_equal(aa, bb):
        return (0.0, 0.0, 0.0)

    def statistic(x: np.ndarray, y: np.ndarray) -> float:
        return float(np.mean(x) - np.mean(y))

    res = bootstrap(
        (aa, bb),
        statistic,
        n_resamples=n_resamples,
        paired=True,
        method="percentile",
        confidence_level=confidence,
        rng=np.random.default_rng(rng),
    )
    d = float(np.mean(aa) - np.mean(bb))
    return (d, float(res.confidence_interval.low), float(res.confidence_interval.high))


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    if k < 1 or n < 0 or c < 0 or c > n or k > n:
        raise ValueError(f"invalid (n, c, k)=({n}, {c}, {k})")
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    if k < 1 or n < 0 or c < 0 or c > n or k > n:
        raise ValueError(f"invalid (n, c, k)=({n}, {c}, {k})")
    if c < k:
        return 0.0
    return comb(c, k) / comb(n, k)
