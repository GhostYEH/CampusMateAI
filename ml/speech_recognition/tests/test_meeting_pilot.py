import io
import json

import numpy as np
import pytest

sf = pytest.importorskip("soundfile")
pytest.importorskip("requests")
import meeting_pilot


def test_fetch_decodes_resamples_and_preserves_reference(tmp_path, monkeypatch):
    audio = io.BytesIO()
    sf.write(audio, np.zeros(4800, dtype="float32"), 48000, format="WAV", subtype="PCM_16")

    class Response:
        content = audio.getvalue()

        def raise_for_status(self):
            pass

        def json(self):
            return {"rows": [{"row_idx": 2, "row": {"sid": "example", "text": "你好",
                    "audio": [{"src": f"https://example.com/{meeting_pilot.REVISION}/sample"}]}}]}

    monkeypatch.setattr(meeting_pilot.requests, "get", lambda *a, **kw: Response())
    output = tmp_path / "samples"
    meeting_pilot.fetch(output, 2, 1)
    record = json.loads((output / "manifest.jsonl").read_text())
    decoded, rate = sf.read(output / record["audio"])
    assert record["text"] == "你好"
    assert record["source_sample_rate"] == 48000
    assert rate == 16000
    assert abs(len(decoded) - 1600) <= 1
    with pytest.raises(ValueError, match="refusing to overwrite"):
        meeting_pilot.fetch(output, 2, 1)
