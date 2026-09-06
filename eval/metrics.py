"""Agreement / latency metrics for local vs Gemini eval."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def binary_label(score: int, threshold: int = 50) -> int:
    return 1 if score >= threshold else 0


def summarize_rows(rows: List[Dict[str, Any]], decision_threshold: int = 50) -> Dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {"n": 0}

    local_scores = [r["local_score"] for r in rows]
    gemini_scores = [r.get("gemini_score") for r in rows if r.get("gemini_score") is not None]
    abs_errs = [
        abs(r["local_score"] - r["gemini_score"])
        for r in rows
        if r.get("gemini_score") is not None
    ]
    agree = [
        binary_label(r["local_score"], decision_threshold)
        == binary_label(r["gemini_score"], decision_threshold)
        for r in rows
        if r.get("gemini_score") is not None
    ]
    label_agree = [
        binary_label(r["local_score"], decision_threshold) == int(r["label"])
        for r in rows
        if r.get("label") is not None
    ]
    route_counts: Dict[str, int] = {}
    for r in rows:
        k = r.get("would_route_to", "unknown")
        route_counts[k] = route_counts.get(k, 0) + 1

    def avg(xs: List[float]) -> Optional[float]:
        return round(sum(xs) / len(xs), 4) if xs else None

    return {
        "n": n,
        "n_with_gemini": len(gemini_scores),
        "local_mean_score": avg([float(x) for x in local_scores]),
        "gemini_mean_score": avg([float(x) for x in gemini_scores]) if gemini_scores else None,
        "mae_local_vs_gemini": avg([float(x) for x in abs_errs]) if abs_errs else None,
        "binary_agreement_vs_gemini": avg([float(x) for x in agree]) if agree else None,
        "binary_accuracy_vs_label": avg([float(x) for x in label_agree]) if label_agree else None,
        "mean_local_confidence": avg([float(r["local_confidence"]) for r in rows]),
        "mean_local_latency_ms": avg(
            [float(r["local_latency_ms"]) for r in rows if r.get("local_latency_ms") is not None]
        ),
        "mean_gemini_latency_ms": avg(
            [
                float(r["gemini_latency_ms"])
                for r in rows
                if r.get("gemini_latency_ms") is not None
            ]
        ),
        "hybrid_route_counts": route_counts,
        "decision_threshold": decision_threshold,
    }
