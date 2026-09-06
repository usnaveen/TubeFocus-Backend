# Model artifacts

Train + export outputs land here (not committed by default — files are large).

```bash
# from repo root
python ml/scripts/prepare_dataset.py --input ml/data/sample_labels.jsonl --out ml/artifacts/prepared
python ml/scripts/train_setfit.py --labels ml/data/sample_labels.jsonl --out ml/artifacts/run1 --epochs 1
python ml/scripts/export_onnx.py --model ml/artifacts/run1/setfit-model --out ml/artifacts/onnx
```

Ship quantized ONNX (`model.int8.onnx`) + `setfit_head.json` + tokenizer files to the extension
(`TubeFocus-Extension`) or Hugging Face. Prefer Git LFS / HF Hub for binaries over git blobs.
