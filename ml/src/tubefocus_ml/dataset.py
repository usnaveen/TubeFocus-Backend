from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .schema import RelevanceLabel, dump_jsonl, load_jsonl


def pair_text(goal: str, title: str, description: str = "") -> str:
    desc = (description or "").strip()
    video = f"{title}\n{desc}" if desc else title
    return f"goal: {goal}\nvideo: {video}"


def from_gemini_debug_exports(path: Path, default_split: str = "train") -> List[RelevanceLabel]:
    """Convert distilled Gemini score dumps into binary relevance labels.

    Expected JSONL fields: goal, title, description?, score (0-100), video_id?, id?
    """
    out: List[RelevanceLabel] = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            score = int(raw["score"])
            out.append(
                RelevanceLabel(
                    id=raw.get("id") or f"gemini-{i}",
                    goal=raw["goal"],
                    title=raw["title"],
                    description=raw.get("description", ""),
                    label=1 if score >= 50 else 0,
                    source="gemini_distill",
                    video_id=raw.get("video_id"),
                    split=raw.get("split", default_split),
                )
            )
    return out


def stratified_split(
    rows: Sequence[RelevanceLabel],
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> List[RelevanceLabel]:
    """Assign train/val/test when rows lack an explicit split."""
    rng = random.Random(seed)
    by_label: Dict[int, List[RelevanceLabel]] = {0: [], 1: []}
    for row in rows:
        by_label[row.binary_label].append(row.model_copy(deep=True))

    out: List[RelevanceLabel] = []
    for label, group in by_label.items():
        rng.shuffle(group)
        n = len(group)
        n_test = max(1, int(round(n * test_ratio))) if n >= 5 else (1 if n >= 3 else 0)
        n_val = max(1, int(round(n * val_ratio))) if n - n_test >= 4 else (1 if n - n_test >= 2 else 0)
        for i, row in enumerate(group):
            if i < n_test:
                row.split = "test"
            elif i < n_test + n_val:
                row.split = "val"
            else:
                row.split = "train"
            out.append(row)
    return out


def to_hf_dict(rows: Iterable[RelevanceLabel], split: Optional[str] = None) -> Dict[str, List]:
    texts: List[str] = []
    labels: List[int] = []
    for row in rows:
        if split and row.split != split:
            continue
        texts.append(row.text_pair)
        labels.append(row.binary_label)
    return {"text": texts, "label": labels}


def summarize(rows: Sequence[RelevanceLabel]) -> Dict[str, object]:
    splits = Counter(r.split for r in rows)
    labels = Counter(r.binary_label for r in rows)
    sources = Counter(r.source for r in rows)
    return {
        "n": len(rows),
        "splits": dict(splits),
        "labels": {str(k): v for k, v in labels.items()},
        "sources": dict(sources),
    }


def prepare(
    input_path: Path,
    output_dir: Path,
    resplit: bool = False,
    seed: int = 42,
) -> Tuple[Path, Dict[str, object]]:
    rows = load_jsonl(input_path)
    if resplit or all(r.split == "train" for r in rows):
        rows = stratified_split(rows, seed=seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "labels.prepared.jsonl"
    dump_jsonl(out_path, rows)
    meta = summarize(rows)
    (output_dir / "dataset_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return out_path, meta
