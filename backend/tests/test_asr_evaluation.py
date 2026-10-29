"""Scoring and input checks for ASR evaluation; no model or network required."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.evaluate_asr import (
    EvaluationEntry,
    artifact_fingerprint,
    character_distance,
    evaluate,
    load_manifest,
    main,
    normalize_text,
    score_result,
    summarize_results,
)


@pytest.mark.parametrize(
    ("reference", "hypothesis", "expected"),
    [("", "", 0), ("", "嗯", 1), ("今天上课", "今天课", 1), ("abc", "axdc", 2)],
)
def test_character_distance(reference: str, hypothesis: str, expected: int) -> None:
    assert character_distance(reference, hypothesis) == expected


def test_normalization_preserves_semantic_number_differences() -> None:
    assert normalize_text("ＡＩ 课程：９点。\n") == "ai课程9点"
    assert normalize_text("九点") != normalize_text("9点")


def test_summary_micro_averages_speech_and_separates_non_speech() -> None:
    entry = lambda text: EvaluationEntry(Path("speech.wav"), text, 1)
    rows = [
        score_result(entry("今天上课"), "今天上课", 2, 0.1),
        score_result(entry("好"), "坏", 1, 0.1),
        score_result(entry(""), "嗯。", 1, 0.02),
        score_result(entry("。"), "", 1, 0.01),
    ]
    summary = summarize_results(rows)
    assert summary["cer"] == pytest.approx(1 / 5)
    assert summary["non_speech_false_positives"] == 1
    assert summary["non_speech_false_positive_rate"] == 0.5
    assert summary["rtf"] == pytest.approx(0.23 / 5)
    assert rows[2]["cer"] is None
    assert rows[2]["non_speech_false_positive"] is True


def test_cer_can_exceed_one_and_is_undefined_without_reference() -> None:
    row = score_result(EvaluationEntry(Path("a.wav"), "好", 1), "坏坏坏", 1, 0.1)
    assert row["cer"] == 3
    summary = summarize_results(
        [score_result(EvaluationEntry(Path("b.wav"), "", 2), "", 0, 0)]
    )
    assert summary["cer"] is None
    assert summary["rtf"] is None


def test_manifest_resolves_audio_relative_to_its_directory(tmp_path: Path) -> None:
    audio = tmp_path / "speech.wav"
    audio.write_bytes(b"not decoded by loader")
    manifest = tmp_path / "set.jsonl"
    manifest.write_text(
        "\ufeff" + json.dumps({"audio": "speech.wav", "text": ""}) + "\n\n",
        encoding="utf-8",
    )
    entries = load_manifest(manifest)
    assert entries == [EvaluationEntry(audio.resolve(), "", 1)]


@pytest.mark.parametrize(
    "content",
    [
        "",
        "not json",
        "[]",
        '{"audio":"missing.wav","text":"好"}',
        '{"audio":2}',
        '{"audio":"speech.wav","text":null}',
    ],
)
def test_invalid_manifest_is_rejected(tmp_path: Path, content: str) -> None:
    manifest = tmp_path / "bad.jsonl"
    manifest.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        load_manifest(manifest)


def test_cli_failure_is_nonzero_and_does_not_write_success_report(
    tmp_path: Path,
) -> None:
    output = tmp_path / "report.json"
    assert (
        main(["--manifest", str(tmp_path / "missing.jsonl"), "--output", str(output)])
        == 2
    )
    assert not output.exists()


def test_warmup_does_not_count_lazy_load_in_measured_inference(
    tmp_path: Path, monkeypatch
) -> None:
    import scripts.evaluate_asr as module

    audio = tmp_path / "a.wav"
    audio.write_bytes(b"stub")
    entries = [EvaluationEntry(audio, "", 1), EvaluationEntry(audio, "好", 2)]
    monkeypatch.setattr(module, "decode_wav_pcm16_mono", lambda *a, **kw: ([0.0], 1))

    class FakeEngine:
        is_loaded = False
        calls = 0

        def ensure_available(self):
            pass

        def transcribe(self, samples, sample_rate):
            self.calls += 1
            if self.calls >= 2:
                self.is_loaded = True
            return "好" if self.calls % 2 == 0 else ""

    engine = FakeEngine()
    report = evaluate(entries, engine, max_seconds=60)
    assert engine.calls == 4
    assert report["warmup_utterances"] == 2
    assert report["model_loaded_after_warmup"] is True
    assert report["summary"]["cer"] == 0
    assert len(report["results"]) == 2


@pytest.mark.parametrize("disable_vad", [False, True])
def test_cli_records_vad_overrides(
    tmp_path: Path, monkeypatch, disable_vad: bool
) -> None:
    import scripts.evaluate_asr as module

    audio = tmp_path / "a.wav"
    audio.write_bytes(b"stub")
    vad = tmp_path / "silero.onnx"
    vad.write_bytes(b"stub")
    manifest = tmp_path / "set.jsonl"
    manifest.write_text(json.dumps({"audio": "a.wav", "text": ""}), encoding="utf-8")
    output = tmp_path / "report.json"
    settings = SimpleNamespace(
        asr_model_file=Path("model.onnx"),
        asr_tokens_file=Path("tokens.txt"),
        asr_num_threads=2,
        asr_language="zh",
        asr_use_itn=True,
        asr_min_rms=0.008,
        asr_min_crest=1.5,
        asr_min_dynamic_seconds=0.35,
        asr_max_audio_seconds=60,
        asr_vad_model_file=vad,
        asr_vad_threshold=0.5,
        asr_denoise_enabled=False,
        asr_denoise_model_file=tmp_path / "missing-gtcrn.onnx",
        asr_denoise_observation_weight=0.5,
    )
    captured = {}

    def make_engine(*args, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(module, "Settings", lambda: settings)
    monkeypatch.setattr(module, "LocalAsrEngine", make_engine)
    monkeypatch.setattr(module, "evaluate", lambda *a, **kw: {})
    assert (
        main(
            [
                "--manifest",
                str(manifest),
                "--output",
                str(output),
                "--vad-model-path",
                "" if disable_vad else str(vad),
                "--vad-threshold",
                "0.7",
            ]
        )
        == 0
    )
    assert captured["vad_model_path"] == (None if disable_vad else vad)
    assert captured["vad_threshold"] == 0.7
    configuration = json.loads(output.read_text(encoding="utf-8"))["configuration"]
    assert configuration["gate"] == ("energy" if disable_vad else "silero_vad")


def test_artifact_fingerprints_match_local_bytes_and_allow_missing_optional_asset(
    tmp_path: Path,
) -> None:
    model = tmp_path / "model.onnx"
    model.write_bytes(b"actual model bytes")
    assert artifact_fingerprint(model) == {
        "filename": "model.onnx",
        "bytes": len(b"actual model bytes"),
        "sha256": hashlib.sha256(b"actual model bytes").hexdigest(),
    }
    assert artifact_fingerprint(None) is None
    assert artifact_fingerprint(tmp_path / "missing.onnx") == {
        "filename": "missing.onnx",
        "bytes": None,
        "sha256": None,
    }


@pytest.fixture
def cli_assets(tmp_path: Path, monkeypatch):
    import scripts.evaluate_asr as module

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"stub")
    manifest = tmp_path / "set.jsonl"
    manifest.write_text(
        json.dumps({"audio": "audio.wav", "text": "好"}), encoding="utf-8"
    )
    model, tokens, denoiser = (
        tmp_path / "model.onnx",
        tmp_path / "tokens.txt",
        tmp_path / "gtcrn.onnx",
    )
    model.write_bytes(b"acoustic model")
    tokens.write_bytes(b"vocabulary")
    denoiser.write_bytes(b"enhancement model")
    settings = SimpleNamespace(
        asr_model_file=model,
        asr_tokens_file=tokens,
        asr_num_threads=2,
        asr_language="zh",
        asr_use_itn=True,
        asr_min_rms=0.008,
        asr_min_crest=1.5,
        asr_min_dynamic_seconds=0.35,
        asr_max_audio_seconds=60,
        asr_vad_model_file=None,
        asr_vad_threshold=0.5,
        asr_denoise_enabled=False,
        asr_denoise_model_file=denoiser,
        asr_denoise_observation_weight=0.5,
    )
    captured = {}

    def make_engine(*args, **kwargs):
        captured["model_path"], captured["tokens_path"] = args
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(module, "Settings", lambda: settings)
    monkeypatch.setattr(module, "LocalAsrEngine", make_engine)
    monkeypatch.setattr(module, "evaluate", lambda *a, **kw: {})
    monkeypatch.setattr(module, "sherpa_version", lambda: "test-version")
    return SimpleNamespace(
        manifest=manifest,
        output=tmp_path / "report.json",
        settings=settings,
        captured=captured,
    )


@pytest.mark.parametrize(
    ("configured", "arguments", "enabled", "weight"),
    [
        (False, [], False, 0.5),
        (False, ["--denoise"], True, 0.5),
        (False, ["--denoise", "--observation-weight", "0"], True, 0.0),
        (False, ["--denoise", "--observation-weight", "1"], True, 1.0),
        (True, ["--no-denoise"], False, 0.5),
    ],
)
def test_cli_compares_original_pure_enhancement_and_observation_addition(
    cli_assets, configured, arguments, enabled, weight
) -> None:
    assets = cli_assets
    assets.settings.asr_denoise_enabled = configured
    assert (
        main(
            [
                "--manifest",
                str(assets.manifest),
                "--output",
                str(assets.output),
                *arguments,
            ]
        )
        == 0
    )
    assert assets.captured["denoise_enabled"] is enabled
    assert assets.captured["denoise_observation_weight"] == weight
    report = json.loads(assets.output.read_text(encoding="utf-8"))
    assert report["configuration"]["denoise_enabled"] is enabled
    assert report["configuration"]["denoise_observation_weight"] == weight
    active = enabled and weight < 1
    assert report["configuration"]["enhancement_active"] is active
    assert (report["artifacts"]["denoiser"] is not None) is active
    assert report["runtime"]["sherpa_onnx"] == "test-version"


def test_cli_hashes_actual_overridden_models(cli_assets, tmp_path: Path) -> None:
    acoustic = tmp_path / "override.onnx"
    acoustic.write_bytes(b"other acoustic model")
    denoiser = tmp_path / "other-gtcrn.onnx"
    denoiser.write_bytes(b"other enhancement model")
    assert (
        main(
            [
                "--manifest",
                str(cli_assets.manifest),
                "--output",
                str(cli_assets.output),
                "--model-path",
                str(acoustic),
                "--denoise",
                "--denoise-model-path",
                str(denoiser),
                "--observation-weight",
                "0.25",
            ]
        )
        == 0
    )
    assert cli_assets.captured["model_path"] == acoustic
    assert cli_assets.captured["denoise_model_path"] == denoiser
    report = json.loads(cli_assets.output.read_text(encoding="utf-8"))
    assert (
        report["artifacts"]["asr_model"]["sha256"]
        == hashlib.sha256(acoustic.read_bytes()).hexdigest()
    )
    assert (
        report["artifacts"]["denoiser"]["sha256"]
        == hashlib.sha256(denoiser.read_bytes()).hexdigest()
    )
    assert report["configuration"]["denoise_observation_weight"] == 0.25


def test_disabled_denoiser_does_not_require_or_hash_its_model(cli_assets) -> None:
    cli_assets.settings.asr_denoise_enabled = True
    cli_assets.settings.asr_denoise_model_file.unlink()
    assert (
        main(
            [
                "--manifest",
                str(cli_assets.manifest),
                "--output",
                str(cli_assets.output),
                "--no-denoise",
            ]
        )
        == 0
    )
    report = json.loads(cli_assets.output.read_text(encoding="utf-8"))
    assert report["artifacts"]["denoiser"] is None
    assert cli_assets.captured["denoise_enabled"] is False
