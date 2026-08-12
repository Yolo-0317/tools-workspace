from __future__ import annotations

from .models import ProbabilityAdjustment, ProbabilityPaths


def adjust_probabilities(base: ProbabilityPaths, score: float) -> ProbabilityAdjustment:
    if score >= 8:
        shift = min(10, round(score))
        delta = ProbabilityPaths(shift, -max(1, shift // 2), -(shift - max(1, shift // 2)))
    elif score >= 3:
        shift = min(6, max(3, round(score)))
        delta = ProbabilityPaths(shift, -max(1, shift // 2), -(shift - max(1, shift // 2)))
    elif score <= -8:
        shift = min(15, max(10, round(abs(score))))
        delta = ProbabilityPaths(-(shift // 2), -(shift - shift // 2), shift)
    elif score <= -3:
        shift = min(8, max(5, round(abs(score))))
        delta = ProbabilityPaths(-(shift // 2), -(shift - shift // 2), shift)
    else:
        delta = ProbabilityPaths(0, 0, 0)
    final = ProbabilityPaths(base.strong + delta.strong, base.neutral + delta.neutral, base.weak + delta.weak)
    return ProbabilityAdjustment(base, delta, final)
