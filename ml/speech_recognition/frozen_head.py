"""Small-memory CTC-head adaptation on frozen INT8 SenseVoice features.

Experimental float head checkpoints only: no production model is overwritten or
exported. Scores are raw acoustic-model CER, without application VAD gating.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
import unicodedata
import wave
from pathlib import Path

import numpy as np


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as reader:
        for chunk in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text).lower()
                   if not c.isspace() and not unicodedata.category(c).startswith("P"))


def distance(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        following = [i]
        for j, y in enumerate(b, 1):
            following.append(min(row[j] + 1, following[-1] + 1, row[j - 1] + (x != y)))
        row = following
    return row[-1]


def lfr(features, window=7, shift=6):
    if len(features) == 0 or features.ndim != 2:
        raise ValueError("Need nonempty frame-by-feature input")
    indices = np.clip(np.arange(0, len(features), shift)[:, None]
                      + np.arange(window) - (window - 1) // 2, 0, len(features) - 1)
    return features[indices].reshape(-1, features.shape[1] * window)


def waveform_features(path, metadata):
    import kaldi_native_fbank as knf

    with wave.open(str(path), "rb") as reader:
        if (reader.getnchannels(), reader.getsampwidth(), reader.getframerate()) != (1, 2, 16000):
            raise ValueError("Expected mono PCM16/16-kHz WAV")
        samples = np.frombuffer(reader.readframes(reader.getnframes()), dtype="<i2").astype(np.float32)
    if metadata.get("normalize_samples") != "0":
        raise ValueError("This frontend only supports the inspected unnormalized SenseVoice export")
    options = knf.FbankOptions()
    options.frame_opts.window_type = "hamming"
    options.frame_opts.dither = 0
    options.frame_opts.snip_edges = True
    options.mel_opts.num_bins = 80
    options.mel_opts.high_freq = 0
    bank = knf.OnlineFbank(options)
    bank.accept_waveform(16000, samples.tolist())
    bank.input_finished()
    if not bank.num_frames_ready:
        raise ValueError("Audio is too short for one feature frame")
    frames = np.stack([bank.get_frame(i) for i in range(bank.num_frames_ready)])
    frames = lfr(frames, int(metadata["lfr_window_size"]), int(metadata["lfr_window_shift"]))
    mean = np.fromstring(metadata["neg_mean"], sep=",", dtype=np.float32)
    inverse_std = np.fromstring(metadata["inv_stddev"], sep=",", dtype=np.float32)
    return ((frames + mean) * inverse_std).astype(np.float32)


def decode(logits, tokenizer):
    # Four fixed rich-transcription positions precede ordinary acoustic frames.
    ids = np.asarray(logits).argmax(-1).tolist()[4:]
    collapsed = [value for i, value in enumerate(ids) if value != 0 and (i == 0 or value != ids[i - 1])]
    return tokenizer.decode(collapsed).strip()


def prepare_cache(model_path, tokenizer_path, bundle, output, parity_report=None):
    import onnx
    import onnxruntime as ort
    import sentencepiece as spm
    from onnx import numpy_helper

    if output.exists():
        raise ValueError("Feature cache already exists; do not overwrite prior experiments")
    model = onnx.load(model_path)
    metadata = {p.key: p.value for p in model.metadata_props}
    if metadata.get("model_type") != "sense_voice_ctc":
        raise ValueError("Only the inspected SenseVoice CTC export is supported")
    initializers = {x.name: numpy_helper.to_array(x) for x in model.graph.initializer}
    matmul = next(n for n in model.graph.node if n.name == "/ctc_lo/MatMul_quant")
    quantizer = next(n for n in model.graph.node if n.output[0] == matmul.input[0])
    scale_node = next(n for n in model.graph.node if n.name == "/ctc_lo/MatMul_quant_scales_mul")
    weights = ((initializers[matmul.input[1]].astype(np.float32)
                - initializers[matmul.input[3]].astype(np.float32))
               * initializers[scale_node.input[1]]).T.copy()
    bias = initializers["ctc.ctc_lo.bias"].copy()
    tokenizer = spm.SentencePieceProcessor(model_file=str(tokenizer_path))
    if tokenizer.get_piece_size() != weights.shape[0] or weights.shape[1] != 512:
        raise ValueError("Tokenizer/head vocabulary or hidden dimension does not match")
    output.mkdir(parents=True)
    np.savez(output / "initial_head.npz", weight=weights, bias=bias)
    for name, dtype, shape in zip(quantizer.output,
            (onnx.TensorProto.UINT8, onnx.TensorProto.FLOAT, onnx.TensorProto.UINT8),
            ([None, None, 512], [], [])):
        model.graph.output.append(onnx.helper.make_tensor_value_info(name, dtype, shape))
    extractor = output / "extractor.onnx"
    onnx.save(model, extractor)
    del model, initializers
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(str(extractor), options, providers=["CPUExecutionProvider"])
    expected = {}
    if parity_report:
        previous = json.loads(parity_report.read_text(encoding="utf-8"))
        expected = {row["group"]: row["hypothesis"] for row in previous["rows"]["baseline"]
                    if row["condition"] == "clean" and row["reference_characters"]}
    indexes, cached, parity_checked, excluded = {}, {}, 0, {}
    training_rows = [json.loads(line) for line in (bundle / "train_clean.jsonl").read_text(encoding="utf-8").splitlines()]
    for row in training_rows:
        ids = tokenizer.encode(row["target"])
        if not ids or 0 in ids:
            excluded[row["source_group"]] = "Empty/OOV target would collide with CTC blank ID 0; entire source excluded from both training arms"
    for split in ("train_clean", "train_augmented", "valid"):
        rows = [json.loads(line) for line in (bundle / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()]
        result = []
        for index, row in enumerate(rows):
            if split.startswith("train_") and row["source_group"] in excluded:
                continue
            source = row["source"]
            if source not in cached:
                feature = waveform_features(bundle / source, metadata)
                logits, quantized, scale, zero = session.run(None, {
                    "x": feature[None], "x_length": np.array([len(feature)], dtype=np.int32),
                    "language": np.array([int(metadata["lang_zh"])], dtype=np.int32),
                    "text_norm": np.array([int(metadata["with_itn"])], dtype=np.int32),
                })
                hidden = (quantized[0].astype(np.float32) - zero) * scale
                original = decode(logits[0], tokenizer)
                rebuilt = decode(hidden @ weights.T + bias, tokenizer)
                if normalized(original) != normalized(rebuilt):
                    raise ValueError("Reconstructed float head differs from original INT8 decoding")
                filename = f"features_{len(cached):05d}.npz"
                np.savez(output / filename, quantized=quantized[0], scale=scale, zero=zero)
                cached[source] = (filename, original)
            filename, original = cached[source]
            target_ids = tokenizer.encode(row["target"])
            if split.startswith("train_") and (not target_ids or 0 in target_ids):
                raise ValueError("Unexpected invalid training labels after source-level filtering")
            if split == "valid" and row["condition"] == "clean" and expected:
                if row["source_group"] not in expected or normalized(original) != normalized(expected[row["source_group"]]):
                    raise ValueError("Reconstructed frontend differs from recorded native clean-speech baseline")
                parity_checked += 1
            result.append({**row, "feature": filename, "target_ids": target_ids, "original": original})
            if index % 64 == 0:
                print(f"Cached {split}: {index + 1}/{len(rows)}", flush=True)
        indexes[split] = result
    if not indexes["train_clean"] or len(indexes["train_clean"]) != len(indexes["train_augmented"]):
        raise ValueError("Both training arms must have equal nonzero exposure after filtering")
    info = {"schema": 1, "model_sha256": fingerprint(model_path),
            "tokenizer_sha256": fingerprint(tokenizer_path), "bundle_sha256": fingerprint(bundle / "provenance.json"),
            "native_clean_parity_checked": parity_checked, "float_head_parity_checked": len(cached),
            "excluded_training_sources": excluded,
            "scope": "Raw CTC model; no application VAD and no new quantized/exported runtime model", "indexes": indexes}
    (output / "bundle_provenance.json").write_bytes((bundle / "provenance.json").read_bytes())
    (output / "index.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"unique_audio": len(cached), "native_clean_parity_checked": parity_checked}


def train(cache, split, output, steps, learning_rate=0.00002):
    if split not in ("train_clean", "train_augmented"):
        raise ValueError("Validation must never be used for optimizer updates")
    if output.exists() or not 1 <= steps <= 10000:
        raise ValueError("Use a new checkpoint path and 1..10000 optimizer steps")
    import torch
    if not torch.backends.mps.is_available():
        raise RuntimeError("This pilot requires a verified MPS backend")
    torch.mps.set_per_process_memory_fraction(0.35)
    torch.manual_seed(73029)
    info = json.loads((cache / "index.json").read_text(encoding="utf-8"))
    arrays = np.load(cache / "initial_head.npz")
    head = torch.nn.Linear(arrays["weight"].shape[1], arrays["weight"].shape[0], device="mps")
    with torch.no_grad():
        head.weight.copy_(torch.from_numpy(arrays["weight"]).to("mps"))
        head.bias.copy_(torch.from_numpy(arrays["bias"]).to("mps"))
    optimizer = torch.optim.AdamW(head.parameters(), lr=learning_rate, weight_decay=0)
    criterion = torch.nn.CTCLoss(blank=0, zero_infinity=False)
    rows = list(info["indexes"][split])
    random.Random(73029).shuffle(rows)
    losses, started = [], time.perf_counter()
    peak_allocated, peak_driver = 0, 0
    for step in range(steps):
        row = rows[step % len(rows)]
        feature = np.load(cache / row["feature"])
        hidden = ((feature["quantized"].astype(np.float32) - feature["zero"]) * feature["scale"])[4:]
        inputs = torch.from_numpy(hidden).to("mps")
        targets = torch.tensor(row["target_ids"], dtype=torch.long, device="mps")
        optimizer.zero_grad(set_to_none=True)
        log_probabilities = head(inputs).log_softmax(-1)[:, None, :]
        loss = criterion(log_probabilities, targets, torch.tensor([len(hidden)]), torch.tensor([len(targets)]))
        if not torch.isfinite(loss):
            raise RuntimeError("Non-finite CTC loss; stop without publishing a checkpoint")
        loss.backward()
        gradient_norm = torch.nn.utils.clip_grad_norm_(head.parameters(), 5, error_if_nonfinite=True)
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
        peak_allocated = max(peak_allocated, torch.mps.current_allocated_memory())
        peak_driver = max(peak_driver, torch.mps.driver_allocated_memory())
        if step % 8 == 0:
            print(f"MPS {split}: step {step + 1}/{steps}, loss={losses[-1]:.5f}", flush=True)
    torch.mps.synchronize()
    checkpoint = {"weight": head.weight.detach().cpu(), "bias": head.bias.detach().cpu(),
                  "model_sha256": info["model_sha256"], "index_sha256": fingerprint(cache / "index.json"),
                  "split": split, "steps": steps, "learning_rate": learning_rate,
                  "elapsed_seconds": time.perf_counter() - started, "losses": losses,
                  "device": "mps", "torch": str(torch.__version__),
                  "automatic_mps_operator_fallback_enabled": os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK") == "1",
                  "last_gradient_norm": float(gradient_norm.detach().cpu()),
                  "observed_mps_tensor_peak_bytes": peak_allocated,
                  "observed_mps_driver_peak_bytes": peak_driver, "mps_memory_fraction": 0.35,
                  "training_scope": "CTC linear head only; encoder frozen"}
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, output)
    return {key: checkpoint[key] for key in ("split", "steps", "elapsed_seconds", "device", "training_scope")}


def evaluate(cache, tokenizer_path, checkpoints, output):
    import sentencepiece as spm
    import torch

    info = json.loads((cache / "index.json").read_text(encoding="utf-8"))
    tokenizer = spm.SentencePieceProcessor(model_file=str(tokenizer_path))
    if fingerprint(tokenizer_path) != info["tokenizer_sha256"]:
        raise ValueError("Tokenizer differs from cached experiment")
    models = {}
    for path in checkpoints:
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        if checkpoint["index_sha256"] != fingerprint(cache / "index.json"):
            raise ValueError("Checkpoint does not belong to this frozen feature cache")
        models[path.stem] = (checkpoint["weight"].numpy(), checkpoint["bias"].numpy())
    results = {name: [] for name in ("original", *models)}
    for row in info["indexes"]["valid"]:
        reference = normalized(row["target"])
        predictions = {"original": row["original"]}
        feature = np.load(cache / row["feature"])
        hidden = (feature["quantized"].astype(np.float32) - feature["zero"]) * feature["scale"]
        for name, (weight, bias) in models.items():
            predictions[name] = decode(hidden @ weight.T + bias, tokenizer)
        for name, hypothesis in predictions.items():
            results[name].append({"key": row["key"], "source_group": row["source_group"],
                                  "condition": row["condition"], "reference": row["target"], "hypothesis": hypothesis,
                                  "errors": distance(reference, normalized(hypothesis)), "characters": len(reference)})
    summaries = {}
    for name, rows in results.items():
        errors, characters = sum(r["errors"] for r in rows), sum(r["characters"] for r in rows)
        summaries[name] = {"errors": errors, "characters": characters, "cer": errors / characters}
    report = {"scope": info["scope"], "model_sha256": info["model_sha256"],
              "index_sha256": fingerprint(cache / "index.json"), "summaries": summaries, "results": results,
              "final_test": False, "automatic_adoption": False}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summaries


def export_head(model_path, checkpoint_path, output, precision="int8"):
    """Export an INT8 or float CTC head on the same frozen INT8 encoder and I/O."""
    if output.exists():
        raise ValueError("Export target already exists; never overwrite the deployed model")
    if precision not in ("int8", "float32"):
        raise ValueError("Head precision must be int8 or float32")
    import onnx
    import torch
    from onnx import numpy_helper

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if checkpoint["model_sha256"] != fingerprint(model_path):
        raise ValueError("Checkpoint/base-model fingerprint mismatch")
    model = onnx.load(model_path)
    tensors = {value.name: value for value in model.graph.initializer}
    matmul = next(node for node in model.graph.node if node.name == "/ctc_lo/MatMul_quant")
    scale_node = next(node for node in model.graph.node if node.name == "/ctc_lo/MatMul_quant_scales_mul")
    original = numpy_helper.to_array(tensors[matmul.input[1]])
    scale = numpy_helper.to_array(tensors[scale_node.input[1]])
    zero = numpy_helper.to_array(tensors[matmul.input[3]])
    weight, bias = checkpoint["weight"].numpy().T, checkpoint["bias"].numpy()
    if weight.shape != original.shape or bias.shape != numpy_helper.to_array(tensors["ctc.ctc_lo.bias"]).shape:
        raise ValueError("Head dimensions differ from the original model")
    if not np.isfinite(weight).all() or not np.isfinite(bias).all():
        raise ValueError("Head weights must be finite")
    tensors["ctc.ctc_lo.bias"].CopyFrom(numpy_helper.from_array(bias.astype(np.float32), "ctc.ctc_lo.bias"))
    details = {"head_precision": precision}
    if precision == "int8":
        bounds = np.iinfo(original.dtype)
        rounded = np.rint(weight / scale + zero)
        quantized = np.clip(rounded, bounds.min, bounds.max).astype(original.dtype)
        tensors[matmul.input[1]].CopyFrom(numpy_helper.from_array(quantized, matmul.input[1]))
        details.update(changed_quantized_weights=int(np.count_nonzero(quantized != original)),
                       clipped_weights=int(np.count_nonzero((rounded < bounds.min) | (rounded > bounds.max))))
    else:
        quantizer = next(node for node in model.graph.node if node.output[0] == matmul.input[0])
        helper = onnx.helper
        weight_name = "campusmate_head_float_weight"
        head_nodes = [
            helper.make_node("Cast", [quantizer.output[0]], ["campusmate_head_qfloat"], to=onnx.TensorProto.FLOAT),
            helper.make_node("Cast", [quantizer.output[2]], ["campusmate_head_zfloat"], to=onnx.TensorProto.FLOAT),
            helper.make_node("Sub", ["campusmate_head_qfloat", "campusmate_head_zfloat"], ["campusmate_head_centered"]),
            helper.make_node("Mul", ["campusmate_head_centered", quantizer.output[1]], ["campusmate_head_features"]),
            helper.make_node("MatMul", ["campusmate_head_features", weight_name], ["campusmate_head_projection"]),
            helper.make_node("Add", ["campusmate_head_projection", "ctc.ctc_lo.bias"], ["logits"]),
        ]
        body = [node for node in model.graph.node if not node.name.startswith("/ctc_lo/")]
        del model.graph.node[:]
        model.graph.node.extend(body + head_nodes)
        used = {name for node in model.graph.node for name in node.input}
        obsolete = {matmul.input[1], matmul.input[3], scale_node.input[1]} - used
        retained = [tensor for tensor in model.graph.initializer if tensor.name not in obsolete]
        del model.graph.initializer[:]
        model.graph.initializer.extend(retained)
        model.graph.initializer.append(numpy_helper.from_array(weight.astype(np.float32), weight_name))
    onnx.checker.check_model(model)
    output.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, output)
    return {"export_sha256": fingerprint(output), "base_sha256": checkpoint["model_sha256"],
            "checkpoint_sha256": fingerprint(checkpoint_path), "steps": checkpoint["steps"],
            "split": checkpoint["split"],
            "io_and_metadata": "External I/O and metadata preserved; encoder frozen; only CTC head changed",
            **details}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prep = sub.add_parser("cache")
    for name in ("model", "tokenizer", "bundle", "output"):
        prep.add_argument(f"--{name}", required=True, type=Path)
    prep.add_argument("--parity-report", type=Path)
    fit = sub.add_parser("train")
    fit.add_argument("--cache", required=True, type=Path)
    fit.add_argument("--split", required=True, choices=("train_clean", "train_augmented"))
    fit.add_argument("--output", required=True, type=Path)
    fit.add_argument("--steps", type=int, default=64)
    score = sub.add_parser("evaluate")
    for name in ("cache", "tokenizer", "output"):
        score.add_argument(f"--{name}", required=True, type=Path)
    score.add_argument("--checkpoints", nargs="+", type=Path, required=True)
    export = sub.add_parser("export")
    for name in ("model", "checkpoint", "output"):
        export.add_argument(f"--{name}", required=True, type=Path)
    export.add_argument("--precision", choices=("int8", "float32"), default="int8")
    args = parser.parse_args(argv)
    try:
        if args.action == "cache":
            result = prepare_cache(args.model, args.tokenizer, args.bundle, args.output, args.parity_report)
        elif args.action == "train":
            result = train(args.cache, args.split, args.output, args.steps)
        elif args.action == "evaluate":
            result = evaluate(args.cache, args.tokenizer, args.checkpoints, args.output)
        else:
            result = export_head(args.model, args.checkpoint, args.output, args.precision)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError, StopIteration) as exc:
        parser.exit(2, f"Frozen-head experiment failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
