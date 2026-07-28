"""工程级真实验证脚本（不依赖 FER2013，不产生正式指标）。

执行 10 项验证：
1. 三个模型前向传播
2. 输出维度 = 7
3. CPU 与 CUDA 张量前向
4. checkpoint 保存与重新加载
5. ONNX 导出
6. ONNX Runtime 推理
7. PyTorch 与 ONNX Top-1 一致性
8. 标签顺序检查
9. 输出模型参数量
10. 记录测试命令与真实结果

输出写到 stdout 与 artifacts/engineering_verification.json。
不写 best_model.pt / metrics.json / confusion_matrix.png 等正式训练产物。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

# 确保导入本地包
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from expression_recognition.config import ExperimentConfig, InputConfig, ModelConfig
from expression_recognition.constants import (
    EXPRESSION_LABELS,
    NUM_CLASSES,
    LABEL_TO_INDEX,
    assert_label_order,
)
from expression_recognition.models.build import (
    build_model,
    count_parameters,
    dummy_input,
    get_input_shape,
)
from expression_recognition.training.checkpoint import save_checkpoint, load_checkpoint
from expression_recognition.export.onnx_export import export_onnx
from expression_recognition.utils.io import sha256_of_file, file_size_bytes, format_size, write_json


def _section(title: str):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main() -> int:
    out_dir = ROOT / "artifacts" / "engineering_verification"
    out_dir.mkdir(parents=True, exist_ok=True)
    device_cpu = torch.device("cpu")
    device_cuda = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    report: dict = {
        "torch_version": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "capability": torch.cuda.get_device_capability(0) if torch.cuda.is_available() else None,
        "label_order": list(EXPRESSION_LABELS),
        "num_classes": NUM_CLASSES,
        "note": "本验证使用单元测试式合成张量，不是 FER2013 指标。",
        "checks": {},
    }

    # ------------------------------------------------------------------
    # 检查 8：标签顺序（先做，作为后续校验基础）
    # ------------------------------------------------------------------
    _section("检查 8: 标签顺序")
    try:
        assert_label_order(list(EXPRESSION_LABELS))
        ok = True
    except ValueError as e:
        ok = False
        report["checks"]["label_order"] = {"ok": False, "error": str(e)}
        print(f"FAIL: {e}")
        return 1
    print(f"labels = {EXPRESSION_LABELS}")
    print(f"label_to_index = {LABEL_TO_INDEX}")
    report["checks"]["label_order"] = {"ok": ok, "labels": list(EXPRESSION_LABELS)}

    # ------------------------------------------------------------------
    # 三个模型配置
    # ------------------------------------------------------------------
    model_specs = [
        ("custom_cnn", InputConfig(size=48, channels=1, mean=(0.5,), std=(0.5,)),
         ModelConfig(name="custom_cnn", num_classes=NUM_CLASSES, pretrained=False,
                     freeze_backbone=False, dropout=0.0)),
        ("resnet18", InputConfig(size=224, channels=3, mean=(0.485, 0.456, 0.406),
                                  std=(0.229, 0.224, 0.225)),
         ModelConfig(name="resnet18", num_classes=NUM_CLASSES, pretrained=False,
                     freeze_backbone=True, dropout=0.0)),
        ("mobilenet_v3_small", InputConfig(size=224, channels=3, mean=(0.485, 0.456, 0.406),
                                            std=(0.229, 0.224, 0.225)),
         ModelConfig(name="mobilenet_v3_small", num_classes=NUM_CLASSES, pretrained=False,
                     freeze_backbone=True, dropout=0.0)),
    ]

    # ------------------------------------------------------------------
    # 检查 1,2,3,9: 前向传播 / 输出维度 / CPU+CUDA / 参数量
    # ------------------------------------------------------------------
    _section("检查 1,2,3,9: 前向传播 / 输出维度=7 / CPU+CUDA / 参数量")
    forward_results = {}
    for name, inp_cfg, model_cfg in model_specs:
        r: dict = {"input_shape": list(get_input_shape(inp_cfg))}
        # CPU
        model = build_model(model_cfg, inp_cfg).to(device_cpu).eval()
        x_cpu = dummy_input(inp_cfg).to(device_cpu)
        with torch.no_grad():
            t0 = time.perf_counter()
            out_cpu = model(x_cpu)
            dt_cpu = (time.perf_counter() - t0) * 1000.0
        r["cpu_output_shape"] = list(out_cpu.shape)
        r["cpu_output_dtype"] = str(out_cpu.dtype)
        r["cpu_forward_ms"] = dt_cpu
        r["cpu_ok"] = out_cpu.shape == (1, NUM_CLASSES)
        r["param_counts"] = count_parameters(model)

        # CUDA（若可用）
        if torch.cuda.is_available():
            model_cuda = build_model(model_cfg, inp_cfg).to(device_cuda).eval()
            x_cuda = dummy_input(inp_cfg).to(device_cuda)
            with torch.no_grad():
                # warmup
                for _ in range(3):
                    model_cuda(x_cuda)
                torch.cuda.synchronize()
                t0 = time.perf_counter()
                out_cuda = model_cuda(x_cuda)
                torch.cuda.synchronize()
                dt_cuda = (time.perf_counter() - t0) * 1000.0
            r["cuda_output_shape"] = list(out_cuda.shape)
            r["cuda_forward_ms"] = dt_cuda
            r["cuda_ok"] = out_cuda.shape == (1, NUM_CLASSES)
            # 数值一致性（CPU vs CUDA）
            max_diff = float((out_cpu - out_cuda.cpu()).abs().max())
            r["cpu_cuda_max_abs_diff"] = max_diff
        else:
            r["cuda_ok"] = None
            r["cuda_skipped"] = "CUDA 不可用"

        forward_results[name] = r
        print(f"\n[{name}]")
        print(f"  input_shape = {r['input_shape']}")
        print(f"  CPU out shape = {r['cpu_output_shape']}  ok={r['cpu_ok']}  {dt_cpu:.2f}ms")
        print(f"  params: total={r['param_counts']['total']} "
              f"trainable={r['param_counts']['trainable']}")
        if torch.cuda.is_available():
            print(f"  CUDA out shape = {r['cuda_output_shape']}  ok={r['cuda_ok']}  {dt_cuda:.2f}ms")
            print(f"  CPU vs CUDA max abs diff = {r['cpu_cuda_max_abs_diff']:.6e}")
    report["checks"]["forward"] = forward_results

    # ------------------------------------------------------------------
    # 检查 4: checkpoint 保存与重新加载
    # ------------------------------------------------------------------
    _section("检查 4: checkpoint 保存与重新加载")
    ckpt_results = {}
    for name, inp_cfg, model_cfg in model_specs:
        model = build_model(model_cfg, inp_cfg).eval()
        opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-3)
        ckpt_path = out_dir / f"{name}_ckpt.pt"
        save_checkpoint(ckpt_path, model=model, optimizer=opt, epoch=7,
                        best_metric=0.123, metric_name="val_macro_f1")
        # 重新加载到新模型
        model2 = build_model(model_cfg, inp_cfg).eval()
        opt2 = torch.optim.AdamW([p for p in model2.parameters() if p.requires_grad], lr=1e-3)
        meta = load_checkpoint(ckpt_path, model=model2, optimizer=opt2)
        # 权重一致
        all_close = all(torch.allclose(p1, p2)
                        for p1, p2 in zip(model.parameters(), model2.parameters()))
        ckpt_results[name] = {
            "checkpoint_path": str(ckpt_path),
            "epoch": meta["epoch"],
            "best_metric": meta["best_metric"],
            "metric_name": meta["metric_name"],
            "weights_match": all_close,
            "sha256": sha256_of_file(ckpt_path),
            "size": format_size(file_size_bytes(ckpt_path)),
        }
        print(f"[{name}] epoch={meta['epoch']} best={meta['best_metric']} "
              f"weights_match={all_close} sha256={ckpt_results[name]['sha256'][:16]}...")
    report["checks"]["checkpoint"] = ckpt_results

    # ------------------------------------------------------------------
    # 检查 5,6,7: ONNX 导出 / Runtime 推理 / Top-1 一致性
    # ------------------------------------------------------------------
    _section("检查 5,6,7: ONNX 导出 / Runtime 推理 / PyTorch↔ONNX Top-1 一致性")
    onnx_results = {}
    for name, inp_cfg, model_cfg in model_specs:
        # 构造一个完整 cfg 供 export_onnx 使用
        cfg = ExperimentConfig(
            experiment_name=f"verify_{name}",
            output_dir=str(out_dir / name),
            input=inp_cfg,
            model=model_cfg,
        )
        (out_dir / name).mkdir(parents=True, exist_ok=True)
        ckpt_path = out_dir / f"{name}_ckpt.pt"
        onnx_path = out_dir / name / "model.onnx"

        info = export_onnx(cfg, ckpt_path, onnx_path)
        # 用固定 seed 输入做 PyTorch vs ONNX 一致性
        torch.manual_seed(0)
        np.random.seed(0)
        shape = (8, inp_cfg.channels, inp_cfg.size, inp_cfg.size)
        x_np = np.random.randn(*shape).astype(np.float32)
        x = torch.from_numpy(x_np)
        model = build_model(model_cfg, inp_cfg).eval()
        load_checkpoint(ckpt_path, model=model)
        with torch.no_grad():
            pt_out = model(x).numpy()
        import onnxruntime as ort
        sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        onx_out = sess.run(["logits"], {"input": x_np})[0]
        pt_labels = pt_out.argmax(axis=1)
        onx_labels = onx_out.argmax(axis=1)
        max_abs = float(np.max(np.abs(pt_out - onx_out)))
        mean_abs = float(np.mean(np.abs(pt_out - onx_out)))
        top1_mismatch = int((pt_labels != onx_labels).sum())

        onnx_results[name] = {
            "onnx_path": str(onnx_path),
            "onnx_sha256": info["sha256"],
            "onnx_size": info["size"],
            "onnxruntime_ok": info.get("onnxruntime_ok", False),
            "onnx_output_shape": info.get("onnxruntime_output_shape"),
            "pt_output_shape": list(pt_out.shape),
            "max_abs_diff": max_abs,
            "mean_abs_diff": mean_abs,
            "top1_mismatch": top1_mismatch,
            "top1_consistency_rate": float((pt_labels == onx_labels).mean()),
            "pt_labels": [int(x) for x in pt_labels.tolist()],
            "onx_labels": [int(x) for x in onx_labels.tolist()],
        }
        print(f"\n[{name}]")
        print(f"  ONNX shape = {onnx_results[name]['onnx_output_shape']}")
        print(f"  max_abs_diff = {max_abs:.6e}  mean_abs_diff = {mean_abs:.6e}")
        print(f"  top1_mismatch = {top1_mismatch}/8  consistency = {onnx_results[name]['top1_consistency_rate']:.3f}")
        print(f"  sha256 = {info['sha256']}")
    report["checks"]["onnx"] = onnx_results

    # ------------------------------------------------------------------
    # 检查 10: 测试命令与真实结果汇总
    # ------------------------------------------------------------------
    _section("检查 10: 汇总")
    # 整体 pass/fail
    all_ok = True
    for name, r in forward_results.items():
        if not (r["cpu_ok"] and (r["cuda_ok"] is True or r["cuda_ok"] is None)):
            all_ok = False
    for name, r in ckpt_results.items():
        if not r["weights_match"]:
            all_ok = False
    for name, r in onnx_results.items():
        if not (r["onnxruntime_ok"] and r["top1_mismatch"] == 0):
            all_ok = False
    report["all_ok"] = all_ok
    report["commands"] = {
        "pytest": "conda run -n campusmate-cnn python -m pytest -q",
        "help": "conda run -n campusmate-cnn python -m expression_recognition --help",
        "this_script": "conda run -n campusmate-cnn python verify_engineering.py",
    }
    write_json(out_dir / "engineering_verification.json", report)
    print(f"\nall_ok = {all_ok}")
    print(f"报告已写入: {out_dir / 'engineering_verification.json'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
