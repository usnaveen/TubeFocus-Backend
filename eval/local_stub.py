"""Local scorer adapters for eval.

Prefers Bot 2 `tubefocus_ml.score.LocalRelevanceScorer` when a SetFit dir is
available; otherwise uses a heuristic that mirrors the extension stub and the
confidence formula: confidence = abs(p_rel - 0.5) * 2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class EvalLocalResult:
    score: int
    confidence: float
    relevant: bool
    backend: str
    reason: str = ""


_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "what", "when",
    "where", "why", "how", "learn", "learning", "video", "videos", "about",
    "into", "a", "an", "to", "of", "in", "on", "is", "are",
}


def _tokens(text: str) -> list[str]:
    return [
        t
        for t in re.split(r"[^a-z0-9]+", (text or "").lower())
        if len(t) > 2 and t not in _STOP
    ]


def heuristic_score(goal: str, title: str, description: str = "") -> EvalLocalResult:
    goal_toks = _tokens(goal)
    video_toks = set(_tokens(f"{title} {description}"))
    if not goal_toks:
        return EvalLocalResult(50, 0.0, True, "heuristic-stub", "empty_goal")
    hits = sum(1 for t in goal_toks if t in video_toks)
    ratio = hits / len(goal_toks)
    p_rel = max(0.05, min(0.95, 0.15 + ratio * 0.8))
    score = int(round(p_rel * 100))
    confidence = abs(p_rel - 0.5) * 2.0
    return EvalLocalResult(
        score=score,
        confidence=float(round(confidence, 4)),
        relevant=score >= 50,
        backend="heuristic-stub",
        reason=f"overlap={ratio:.3f} hits={hits}/{len(goal_toks)}",
    )


def score_local(
    goal: str,
    title: str,
    description: str = "",
    setfit_dir: Optional[Path] = None,
) -> EvalLocalResult:
    if setfit_dir and Path(setfit_dir).exists():
        try:
            from tubefocus_ml.score import LocalRelevanceScorer  # type: ignore

            result = LocalRelevanceScorer(Path(setfit_dir)).score(goal, title, description)
            return EvalLocalResult(
                score=int(result.score),
                confidence=float(result.confidence),
                relevant=bool(result.relevant),
                backend=str(result.backend),
                reason="setfit",
            )
        except Exception as exc:  # noqa: BLE001 — eval must not crash
            fallback = heuristic_score(goal, title, description)
            fallback.reason = f"setfit_failed:{exc}; {fallback.reason}"
            return fallback
    return heuristic_score(goal, title, description)
