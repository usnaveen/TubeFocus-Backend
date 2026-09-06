#!/usr/bin/env python3
"""CLI alias: compare local vs Gemini (defaults to --offline)."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from eval.run_offline_eval import main

if __name__ == "__main__":
    argv = list(sys.argv[1:])
    if "--live-gemini" not in argv and "--offline" not in argv:
        argv.append("--offline")
    raise SystemExit(main(argv))
