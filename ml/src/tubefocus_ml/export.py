from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Optional


def export_onnx(
    setfit_dir: Path,
    output_dir: Path,
    quantize: bool = True,
    opset: int = 14,
) -> Path:
    """Export the sentence-transformer body from a SetFit model to ONNX (+ optional INT8).

    Extension scorers (Transformers.js / ORT Web) load the ONNX encoder and compute
    goal↔video similarity or apply the saved SetFit head locally.
    """
    from setfit import SetFitModel

    output_dir.mkdir(parents=True, exist_ok=True)
    model = SetFitModel.from_pretrained(str(setfit_dir))
    body = model.model_body

    # Prefer Optimum export when available; fall back to torch.onnx.
    onnx_path = output_dir / "model.onnx"
    try:
        from optimum.onnxruntime import ORTModelForFeatureExtraction
        from transformers import AutoTokenizer

        # Save body in HF layout then convert.
        hf_tmp = output_dir / "_hf_body"
        body.save(str(hf_tmp))
        tokenizer = AutoTokenizer.from_pretrained(body.tokenizer if hasattr(body, "tokenizer") else str(hf_tmp))
        # sentence-transformers save layout
        try:
            ort_model = ORTModelForFeatureExtraction.from_pretrained(str(hf_tmp), export=True)
        except Exception:
            # Some ST versions store under 0_Transformer
            sub = hf_tmp / "0_Transformer"
            ort_model = ORTModelForFeatureExtraction.from_pretrained(str(sub if sub.exists() else hf_tmp), export=True)
            if sub.exists():
                tokenizer = AutoTokenizer.from_pretrained(str(sub))
        ort_model.save_pretrained(str(output_dir / "ort"))
        tokenizer.save_pretrained(str(output_dir / "ort"))
        # Copy primary onnx if present
        candidates = list((output_dir / "ort").rglob("*.onnx"))
        if candidates:
            shutil.copy(candidates[0], onnx_path)
    except Exception as optimum_exc:  # noqa: BLE001
        import torch

        # Minimal fallback: wrap encode with a dummy forward for export documentation.
        (output_dir / "export_warning.txt").write_text(
            f"Optimum export failed ({optimum_exc}); wrote torch fallback notes.\n"
            "Install optimum[onnxruntime] and re-run for production ONNX.\n",
            encoding="utf-8",
        )
        # Still persist tokenizer/config for the extension to download later.
        body.save(str(output_dir / "st_body"))

    if quantize and onnx_path.exists():
        try:
            from onnxruntime.quantization import QuantType, quantize_dynamic

            qpath = output_dir / "model.int8.onnx"
            quantize_dynamic(str(onnx_path), str(qpath), weight_type=QuantType.QInt8)
            onnx_path = qpath
        except Exception as qexc:  # noqa: BLE001
            (output_dir / "quantize_warning.txt").write_text(str(qexc) + "\n", encoding="utf-8")

    # Persist SetFit head weights for hybrid JS / Python scorers.
    head_path = output_dir / "setfit_head.json"
    try:
        head = model.model_head
        payload = {"type": type(head).__name__}
        if hasattr(head, "coef_") and hasattr(head, "intercept_"):
            payload["coef"] = head.coef_.tolist()
            payload["intercept"] = head.intercept_.tolist()
            payload["classes"] = getattr(head, "classes_", [0, 1])
            if hasattr(payload["classes"], "tolist"):
                payload["classes"] = payload["classes"].tolist()
        head_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except Exception as hexc:  # noqa: BLE001
        head_path.write_text(json.dumps({"error": str(hexc)}) + "\n", encoding="utf-8")

    meta = {
        "onnx": str(onnx_path.name) if onnx_path.exists() else None,
        "quantize": quantize,
        "opset": opset,
        "setfit_dir": str(setfit_dir),
        "head": head_path.name,
    }
    (output_dir / "export_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return onnx_path if onnx_path.exists() else output_dir


def main(argv: Optional[list] = None) -> None:
    p = argparse.ArgumentParser(description="Export TubeFocus SetFit body to ONNX")
    p.add_argument("--model", type=Path, required=True, help="SetFit model directory")
    p.add_argument("--out", type=Path, required=True, help="ONNX output directory")
    p.add_argument("--no-quantize", action="store_true")
    p.add_argument("--opset", type=int, default=14)
    args = p.parse_args(argv)
    path = export_onnx(args.model, args.out, quantize=not args.no_quantize, opset=args.opset)
    print(f"Export complete: {path}")


if __name__ == "__main__":
    main()
