"""Profile-aware presentation helpers for transparent match scores."""

from __future__ import annotations


DEFAULT_MINIMUM_RAW_MATCH_SCORE = 50
READY_NORMALIZED_SCORE = 80


def normalize_match_score(raw_score: int | float, minimum_raw_score: int | None) -> int:
    """Map an evidence score onto a candidate-friendly 0–100 scale.

    The candidate's own "good enough to apply" setting is always the 80-point
    mark on the calibrated scale. This preserves the raw score for auditability
    while making the decision threshold visually consistent across profiles.
    """
    raw = max(0.0, min(100.0, float(raw_score)))
    anchor = max(1, min(99, int(minimum_raw_score or DEFAULT_MINIMUM_RAW_MATCH_SCORE)))
    if raw <= anchor:
        return round(raw * READY_NORMALIZED_SCORE / anchor)
    return round(READY_NORMALIZED_SCORE + (raw - anchor) * (100 - READY_NORMALIZED_SCORE) / (100 - anchor))
