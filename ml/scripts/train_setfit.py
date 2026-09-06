#!/usr/bin/env python3
"""CLI wrapper for SetFit fine-tune."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tubefocus_ml.train import main  # noqa: E402

if __name__ == "__main__":
    main()
