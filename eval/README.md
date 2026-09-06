# `eval/` — Offline / hybrid scoring harness (Coder Bot 3)

Compares **local** relevance scores (Bot 2 SetFit via `LocalRelevanceScorer`,
or heuristic stub) against **Gemini** reference scores, measures latency, and
simulates Extension hybrid routing.

> Placed at repo-root `eval/` so it does **not** overwrite Bot 2's `ml/` package.

## Offline mode

Never calls cloud. Uses fixture `gemini_score` fields.

```bash
# from TubeFocus-Backend root
python -m eval.run_offline_eval \
  --fixtures eval/fixtures/sample_eval.jsonl \
  --offline \
  --out eval/artifacts/last_eval.json
```

## Live Gemini

```bash
export GOOGLE_API_KEY=...
python -m eval.run_offline_eval --fixtures eval/fixtures/sample_eval.jsonl --live-gemini
```

## Hybrid routing simulation

If `local_confidence < --confidence-threshold` (default **0.55**),
`would_route_to=cloud`; else `local`. Offline always reports `local`.
Mirrors Extension `hybridScorer.js`.

## SetFit (Bot 2 `ml/`)

```bash
python -m eval.run_offline_eval --offline --setfit-dir ml/artifacts/run1/setfit-model
```

## Outputs

`last_eval.json`: `summary` (MAE, agreement, latencies, route counts) + `rows`.
