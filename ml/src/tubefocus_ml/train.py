from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from .dataset import prepare, to_hf_dict
from .schema import load_jsonl


DEFAULT_BASE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def train_setfit(
    labels_path: Path,
    output_dir: Path,
    base_model: str = DEFAULT_BASE_MODEL,
    num_epochs: int = 1,
    batch_size: int = 16,
    max_steps: Optional[int] = None,
    seed: int = 42,
) -> Path:
    """Fine-tune a tiny SetFit classifier on goal↔video relevance labels."""
    from datasets import Dataset
    from setfit import SetFitModel, Trainer, TrainingArguments

    prepared_dir = output_dir / "prepared"
    prepared_path, meta = prepare(labels_path, prepared_dir, resplit=False, seed=seed)
    rows = load_jsonl(prepared_path)

    train_dict = to_hf_dict(rows, split="train")
    val_dict = to_hf_dict(rows, split="val")
    if not train_dict["text"]:
        raise SystemExit("No train rows found — check label splits")

    train_ds = Dataset.from_dict(train_dict)
    eval_ds = Dataset.from_dict(val_dict) if val_dict["text"] else None

    model = SetFitModel.from_pretrained(base_model)
    args = TrainingArguments(
        output_dir=str(output_dir / "runs"),
        batch_size=batch_size,
        num_epochs=num_epochs,
        evaluation_strategy="epoch" if eval_ds is not None else "no",
        save_strategy="epoch",
        load_best_model_at_end=bool(eval_ds),
        seed=seed,
        max_steps=max_steps if max_steps is not None else -1,
    )
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        metric="accuracy",
    )
    trainer.train()
    if eval_ds is not None:
        metrics = trainer.evaluate()
    else:
        metrics = {}

    model_dir = output_dir / "setfit-model"
    model.save_pretrained(str(model_dir))
    (output_dir / "train_meta.json").write_text(
        json.dumps(
            {
                "base_model": base_model,
                "dataset": meta,
                "metrics": metrics,
                "num_epochs": num_epochs,
                "batch_size": batch_size,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return model_dir


def main(argv: Optional[list] = None) -> None:
    p = argparse.ArgumentParser(description="Train TubeFocus SetFit relevance model")
    p.add_argument("--labels", type=Path, required=True, help="JSONL labels path")
    p.add_argument("--out", type=Path, required=True, help="Output directory")
    p.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--max-steps", type=int, default=None)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args(argv)
    path = train_setfit(
        labels_path=args.labels,
        output_dir=args.out,
        base_model=args.base_model,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        max_steps=args.max_steps,
        seed=args.seed,
    )
    print(f"Saved SetFit model to {path}")


if __name__ == "__main__":
    main()
