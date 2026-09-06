from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


@dataclass
class LocalScoreResult:
    score: int  # 0-100
    confidence: float  # 0-1
    relevant: bool
    backend: str


class LocalRelevanceScorer:
    """Python reference scorer mirroring the extension on-device path."""

    def __init__(self, setfit_dir: Path):
        from setfit import SetFitModel

        self.model = SetFitModel.from_pretrained(str(setfit_dir))
        self.setfit_dir = setfit_dir

    def score(self, goal: str, title: str, description: str = "") -> LocalScoreResult:
        from .dataset import pair_text

        text = pair_text(goal, title, description)
        # SetFit predict_proba when available
        if hasattr(self.model, "predict_proba"):
            import numpy as np

            proba = self.model.predict_proba([text])[0]
            # assume classes [0,1]
            if hasattr(proba, "tolist"):
                proba = proba.tolist() if not hasattr(proba, "shape") else proba
            import numpy as np

            arr = np.asarray(self.model.predict_proba([text])[0]).reshape(-1)
            p_rel = float(arr[-1])
        else:
            pred = int(self.model.predict([text])[0])
            p_rel = 0.9 if pred == 1 else 0.1

        score = int(round(p_rel * 100))
        confidence = abs(p_rel - 0.5) * 2.0
        return LocalScoreResult(
            score=score,
            confidence=confidence,
            relevant=score >= 50,
            backend="setfit-local",
        )


def score_pair(
    setfit_dir: Path,
    goal: str,
    title: str,
    description: str = "",
) -> Tuple[int, float]:
    result = LocalRelevanceScorer(setfit_dir).score(goal, title, description)
    return result.score, result.confidence
