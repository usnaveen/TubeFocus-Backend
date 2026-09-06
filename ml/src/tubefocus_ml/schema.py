from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

LabelValue = Union[int, Literal[0, 1]]
Source = Literal["human", "gemini_distill", "heuristic", "synthetic"]
Split = Literal["train", "val", "test"]

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "relevance_label.schema.json"


class RelevanceLabel(BaseModel):
    """goal ↔ title/description relevance example for SetFit / dual-encoder training."""

    id: Optional[str] = None
    goal: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
    label: int
    source: Source = "human"
    video_id: Optional[str] = None
    split: Split = "train"

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: int) -> int:
        if v in (0, 1):
            return v
        if 0 <= v <= 100:
            return v
        raise ValueError("label must be 0/1 or an integer 0-100")

    @property
    def binary_label(self) -> int:
        if self.label in (0, 1):
            return int(self.label)
        return 1 if self.label >= 50 else 0

    @property
    def text_pair(self) -> str:
        desc = (self.description or "").strip()
        video = f"{self.title}\n{desc}" if desc else self.title
        return f"goal: {self.goal}\nvideo: {video}"

    def to_setfit_row(self) -> Dict[str, Any]:
        return {"text": self.text_pair, "label": self.binary_label}


def load_jsonl(path: Path) -> List[RelevanceLabel]:
    rows: List[RelevanceLabel] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(RelevanceLabel.model_validate(json.loads(line)))
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"{path}:{line_no}: {exc}") from exc
    return rows


def dump_jsonl(path: Path, rows: Iterable[RelevanceLabel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(row.model_dump_json(exclude_none=True) + "\n")


def load_schema() -> Dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
