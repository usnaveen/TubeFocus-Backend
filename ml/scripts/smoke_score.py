#!/usr/bin/env python3
"""Quick local score check after training."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tubefocus_ml.score import LocalRelevanceScorer  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--goal", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    args = p.parse_args()
    r = LocalRelevanceScorer(args.model).score(args.goal, args.title, args.description)
    print(r)


if __name__ == "__main__":
    main()
