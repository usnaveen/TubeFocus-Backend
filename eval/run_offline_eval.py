#!/usr/bin/env python3
"""Offline / hybrid eval harness: local vs Gemini agreement + latency.

Lives at repo-root `eval/` (Coder Bot 3) so it does not collide with Bot 2's
`ml/` SetFit/ONNX package. Hooks `LocalRelevanceScorer.confidence` when a
SetFit dir is provided.

Examples:
  python -m eval.run_offline_eval --fixtures eval/fixtures/sample_eval.jsonl --offline
  python -m eval.run_offline_eval --fixtures eval/fixtures/sample_eval.jsonl --live-gemini
  python -m eval.run_offline_eval --offline --setfit-dir ml/artifacts/run1/setfit-model
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
# Bot 2 package layouts (Backend ml/ or sibling checkout)
for _extra in (
    _REPO / "ml" / "src",
    Path("/workspace/tubefocus-ml/src"),
):
    if _extra.is_dir() and str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from eval.local_stub import score_local  # noqa: E402
from eval.metrics import summarize_rows  # noqa: E402


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def maybe_live_gemini(
    goal: str, title: str, description: str
) -> tuple[Optional[int], Optional[float], Optional[str]]:
    """Return (score, latency_ms, error)."""
    api_key = None
    try:
        from config import Config  # type: ignore

        api_key = getattr(Config, "GOOGLE_API_KEY", None)
    except Exception:
        pass
    if not api_key:
        import os

        api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None, None, "GOOGLE_API_KEY missing"

    try:
        from google import genai

        prompt = f"""Rate the relevance of this YouTube video to the user's goal on a scale of 0 to 100.
Video Title: {title}
Description: {(description or '')[:1000]}
User Goal: {goal}

Respond with valid JSON only:
{{ "score": <integer_0_to_100>, "reasoning": "<short>" }}
"""
        t0 = time.perf_counter()
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        latency = (time.perf_counter() - t0) * 1000.0
        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        return int(data.get("score", 0)), round(latency, 2), None
    except Exception as exc:  # noqa: BLE001
        return None, None, str(exc)


def eval_row(
    row: Dict[str, Any],
    *,
    confidence_threshold: float,
    offline: bool,
    live_gemini: bool,
    setfit_dir: Optional[Path],
) -> Dict[str, Any]:
    goal = row.get("goal", "")
    title = row.get("title", "")
    description = row.get("description", "")

    t0 = time.perf_counter()
    local = score_local(goal, title, description, setfit_dir=setfit_dir)
    local_ms = (time.perf_counter() - t0) * 1000.0

    gemini_score = row.get("gemini_score")
    gemini_ms = None
    gemini_err = None
    if live_gemini and not offline:
        live_score, gemini_ms, gemini_err = maybe_live_gemini(goal, title, description)
        if live_score is not None:
            gemini_score = live_score

    low_conf = local.confidence < confidence_threshold
    if offline:
        would_route, route_reason = "local", "offline_mode"
    elif low_conf:
        would_route, route_reason = "cloud", "low_local_confidence"
    else:
        would_route, route_reason = "local", "high_local_confidence"

    return {
        "id": row.get("id"),
        "goal": goal,
        "title": title,
        "label": row.get("label"),
        "local_score": local.score,
        "local_confidence": local.confidence,
        "local_backend": local.backend,
        "local_reason": local.reason,
        "local_latency_ms": round(local_ms, 2),
        "gemini_score": gemini_score,
        "gemini_latency_ms": gemini_ms,
        "gemini_error": gemini_err,
        "would_route_to": would_route,
        "route_reason": route_reason,
        "confidence_threshold": confidence_threshold,
        "offline": offline,
    }


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="TubeFocus offline / hybrid score eval")
    p.add_argument(
        "--fixtures",
        type=Path,
        default=Path("eval/fixtures/sample_eval.jsonl"),
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("eval/artifacts/last_eval.json"),
    )
    p.add_argument("--offline", action="store_true", help="Never call Gemini")
    p.add_argument("--live-gemini", action="store_true", help="Call Gemini per row")
    p.add_argument("--confidence-threshold", type=float, default=0.55)
    p.add_argument("--setfit-dir", type=Path, default=None)
    p.add_argument("--decision-threshold", type=int, default=50)
    args = p.parse_args(argv)

    if args.live_gemini and args.offline:
        print("ERROR: --live-gemini and --offline are mutually exclusive", file=sys.stderr)
        return 2

    offline_flag = args.offline or not args.live_gemini
    fixtures = load_jsonl(args.fixtures)
    rows = [
        eval_row(
            r,
            confidence_threshold=args.confidence_threshold,
            offline=offline_flag,
            live_gemini=args.live_gemini,
            setfit_dir=args.setfit_dir,
        )
        for r in fixtures
    ]
    for r in rows:
        r["offline"] = offline_flag

    summary = summarize_rows(rows, decision_threshold=args.decision_threshold)
    payload = {
        "summary": summary,
        "config": {
            "fixtures": str(args.fixtures),
            "offline": offline_flag,
            "live_gemini": bool(args.live_gemini),
            "confidence_threshold": args.confidence_threshold,
            "setfit_dir": str(args.setfit_dir) if args.setfit_dir else None,
        },
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
