from pathlib import Path

import numpy as np
import pytest

from frozen_head import decode, distance, export_head, lfr, normalized, train


def test_lfr_preserves_both_short_audio_edges():
    frames = np.arange(3 * 80, dtype=np.float32).reshape(3, 80)
    result = lfr(frames)
    assert result.shape == (1, 560)
    assert np.array_equal(result.reshape(7, 80), frames[[0, 0, 0, 0, 1, 2, 2]])


def test_decode_drops_metadata_frames_and_preserves_blank_separated_repetitions():
    symbols = [1, 2, 3, 4, 5, 5, 0, 5, 6]
    logits = np.full((len(symbols), 8), -10, dtype=np.float32)
    logits[np.arange(len(symbols)), symbols] = 10

    class Tokenizer:
        def decode(self, ids):
            return ",".join(str(value) for value in ids)

    assert decode(logits, Tokenizer()) == "5,5,6"


def test_validation_is_rejected_before_loading_torch_or_touching_a_checkpoint(tmp_path):
    output = tmp_path / "checkpoint.pt"
    with pytest.raises(ValueError, match="Validation must never"):
        train(Path("missing_cache"), "valid", output, 1)
    assert not output.exists()


def test_export_never_overwrites_an_existing_model_even_before_optional_imports(tmp_path):
    model = tmp_path / "model.onnx"
    model.write_bytes(b"Original deployed model placeholder")
    with pytest.raises(ValueError, match="never overwrite"):
        export_head(model, Path("missing_checkpoint.pt"), model)
    assert model.read_bytes() == b"Original deployed model placeholder"


@pytest.mark.parametrize(("reference", "hypothesis"), [
    ("ＡＩ 课程：９点。", "AI课程：九点"), ("今天上课", "今天课"),
    ("", "嗯。"), ("好", "坏坏坏"),
])
def test_standalone_mps_scoring_matches_existing_backend_contract(reference, hypothesis):
    from scripts.evaluate_asr import character_distance, normalize_text

    assert normalized(reference) == normalize_text(reference)
    assert normalized(hypothesis) == normalize_text(hypothesis)
    assert distance(normalized(reference), normalized(hypothesis)) == character_distance(
        normalize_text(reference), normalize_text(hypothesis))
