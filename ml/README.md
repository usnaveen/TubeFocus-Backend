# TubeFocus ML (Tier A)

On-device relevance for Gatekeeper: fine-tune a tiny **SetFit / MiniLM** dual-encoder-style
classifier on `goal ↔ title/description` labels, export **ONNX** (INT8), and hand artifacts to
the Chrome MV3 Transformers.js / WebGPU scorer.

## Layout

| Path | Purpose |
|------|---------|
| `schema/relevance_label.schema.json` | Label contract |
| `data/sample_labels.jsonl` | Tiny synthetic starter set |
| `src/tubefocus_ml/` | Schema, dataset prep, train, export, local score |
| `scripts/` | CLIs |
| `artifacts/` | Local train/export outputs (gitignored binaries) |

## Label schema (summary)

Each JSONL row:

- `goal` (string), `title` (string), `description` (optional)
- `label`: `0|1` or graded `0–100` (threshold 50 → binary)
- `source`: `human` | `gemini_distill` | `heuristic` | `synthetic`
- `split`: `train` | `val` | `test`

Text fed to SetFit:

```text
goal: <goal>
video: <title>
<description>
```

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r ml/requirements.txt

python ml/scripts/prepare_dataset.py \
  --input ml/data/sample_labels.jsonl \
  --out ml/artifacts/prepared

python ml/scripts/train_setfit.py \
  --labels ml/data/sample_labels.jsonl \
  --out ml/artifacts/run1 \
  --epochs 1 \
  --batch-size 8

python ml/scripts/export_onnx.py \
  --model ml/artifacts/run1/setfit-model \
  --out ml/artifacts/onnx

python ml/scripts/smoke_score.py \
  --model ml/artifacts/run1/setfit-model \
  --goal "learn KV cache for LLM inference interviews" \
  --title "KV Cache Explained for Transformers"
```

Distill from existing Gemini scores:

```bash
python ml/scripts/prepare_dataset.py \
  --input path/to/gemini_scores.jsonl \
  --from-gemini \
  --out ml/artifacts/prepared
```

## Integration notes

- **Coder Bot 1 (extension):** load `model.int8.onnx` (+ tokenizer) via Transformers.js / WebGPU,
  WASM fallback; replace Gatekeeper Gemini score path.
- **Coder Bot 3 (hybrid + eval):** use `LocalRelevanceScorer.confidence` (or JS equivalent) for
  local-first routing; cloud only on low confidence / deep audit+coach.
- Root `score_model.py` already prototypes MiniLM cosine scoring — this package supersedes it with
  **labeled SetFit fine-tune + ONNX** for offline parity.

## Acceptance (this slice)

- [x] Label schema + sample data + prep pipeline
- [x] SetFit (MiniLM) train script
- [x] ONNX export + dynamic INT8 quantization script
- [ ] Trained weights committed or published to HF (run train on real labels, then upload)
