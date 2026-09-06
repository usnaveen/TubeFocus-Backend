#!/usr/bin/env python3
"""Prepare TubeFocus relevance JSONL for SetFit training."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tubefocus_ml.dataset import from_gemini_debug_exports, prepare  # noqa: E402
from tubefocus_ml.schema import dump_jsonl, load_jsonl  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True, help="labels JSONL or Gemini dump JSONL")
    p.add_argument("--out", type=Path, required=True, help="output directory")
    p.add_argument("--from-gemini", action="store_true", help="treat input as Gemini score dumps")
    p.add_argument("--resplit", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    if args.from_gemini:
        rows = from_gemini_debug_exports(args.input)
        tmp = args.out / "_gemini_converted.jsonl"
        args.out.mkdir(parents=True, exist_ok=True)
        dump_jsonl(tmp, rows)
        path, meta = prepare(tmp, args.out, resplit=True, seed=args.seed)
    else:
        path, meta = prepare(args.input, args.out, resplit=args.resplit, seed=args.seed)
    print(path)
    print(meta)


if __name__ == "__main__":
    main()
