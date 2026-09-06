# On-device scoring & hybrid routing (Tier A)

TubeFocus Gatekeeper scores videos for goal relevance. Tier A moves the hot
path **on-device** (local MiniLM/SetFit → ONNX → Transformers.js) and keeps
**Gemini / Cloud Run** for low-confidence cases and deep audit/coach.

## Architecture

```
┌──────────────────────── Extension (MV3) ─────────────────────────┐
│  content.js ──FETCH_SCORE──▶ background.js                       │
│       │                         │                                │
│       │                    hybridScorer.js                       │
│       │                    ┌────┴────┐                           │
│       │                    ▼         ▼                           │
│       │         localRelevanceScorer   cloud POST /score         │
│       │         (heuristic stub now;   (Gemini via Backend)      │
│       │          ONNX hook later)                                │
└───────┴──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────── Backend ─────────────────────────────────┐
│  /score → simple_scoring.py (Gemini)                             │
│  ml/    → Bot 2 SetFit train + ONNX export + LocalRelevanceScorer│
│  eval/  → Bot 3 offline harness (local vs Gemini, latency)       │
└──────────────────────────────────────────────────────────────────┘
```

### Confidence hybrid routing

Implemented in Extension `hybridScorer.js` (wired into `FETCH_SCORE` / `videoData`):

1. **Always try local first** (`localRelevanceScorer.js`).
2. If `confidence >= HYBRID_CONFIDENCE_THRESHOLD` (default **0.55**) → use local.
3. Else **or** `forceCloud` (audit / coach) → call existing Cloud Run `/score`.
4. **`OFFLINE_MODE` / `chrome.storage.offlineMode`** → never call cloud; keep local
   even when confidence is low.
5. If cloud fails and local exists → soft-fallback to local.

Confidence formula (matches Bot 2 `LocalRelevanceScorer`):

```text
confidence = abs(p_rel - 0.5) * 2   # 0..1, higher = more decisive
```

Knobs:

| Location | Key | Default |
|----------|-----|---------|
| `config.js` / `background.js` CONFIG | `HYBRID_CONFIDENCE_THRESHOLD` | `0.55` |
| | `OFFLINE_MODE` | `false` |
| | `ENABLE_LOCAL_SCORER` | `true` |
| `chrome.storage.local` | `hybridConfidenceThreshold`, `offlineMode`, `enableLocalScorer` | override |

Force cloud from callers:

```js
chrome.runtime.sendMessage({
  type: 'FETCH_SCORE',
  url, goal, title, description,
  forceCloud: true,   // or deepAudit / coach
});
```

### Local scorer stubs / Bot 1 hook

Until Transformers.js + ONNX lands, `localRelevanceScorer.js` uses a token-overlap
heuristic with the same confidence shape. Bot 1 can register:

```js
globalThis.__TubeFocusLocalOnnxScorer = async (goal, title, description) => ({
  score: 0-100,
  confidence: 0-1,
  relevant: boolean,
  backend: 'onnx-local',
});
```

## Offline eval harness

```bash
python -m eval.run_offline_eval \
  --fixtures eval/fixtures/sample_eval.jsonl \
  --offline
```

See `eval/README.md`. Metrics JSON includes MAE vs Gemini fixtures, binary
agreement, mean local latency, and simulated hybrid route counts.

Live comparison (optional):

```bash
GOOGLE_API_KEY=... python -m eval.run_offline_eval --live-gemini
```

## How to retrain / export (Bot 2 `ml/`)

After Bot 2's package is merged under Backend `ml/`:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r ml/requirements.txt

python ml/scripts/prepare_dataset.py \
  --input ml/data/sample_labels.jsonl \
  --out ml/artifacts/prepared

python ml/scripts/train_setfit.py \
  --labels ml/data/sample_labels.jsonl \
  --out ml/artifacts/run1 \
  --epochs 1 --batch-size 8

python ml/scripts/export_onnx.py \
  --model ml/artifacts/run1/setfit-model \
  --out ml/artifacts/onnx

python ml/scripts/smoke_score.py \
  --model ml/artifacts/run1/setfit-model \
  --goal "learn KV cache for LLM inference interviews" \
  --title "KV Cache Explained for Transformers"
```

Distill from Gemini scores:

```bash
python ml/scripts/prepare_dataset.py \
  --input path/to/gemini_scores.jsonl \
  --from-gemini \
  --out ml/artifacts/prepared
```

Point the eval harness at the new checkpoint:

```bash
python -m eval.run_offline_eval --offline \
  --setfit-dir ml/artifacts/run1/setfit-model
```

Ship `model.int8.onnx` (+ tokenizer) to the Extension for Bot 1's on-device path.

## Related files

| Path | Role |
|------|------|
| Extension `hybridScorer.js` | Local-first routing |
| Extension `localRelevanceScorer.js` | Local score + confidence stub / ONNX hook |
| Extension `background.js` | `FETCH_SCORE` / `videoData` use hybrid |
| Backend `eval/` | Offline harness |
| Backend `ml/` | Bot 2 train/export (do not overwrite from this slice) |
| Backend `simple_scoring.py` | Cloud Gemini scorer |
