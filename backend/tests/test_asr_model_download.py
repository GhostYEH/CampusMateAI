"""Offline coverage for optional speech assets and atomic model verification."""

from __future__ import annotations

import hashlib
import io
import urllib.error
from pathlib import Path

import pytest

from scripts import download_asr_model as downloader


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def unexpected_request(*args, **kwargs):
        pytest.fail("model-download tests must not access the network")

    monkeypatch.setattr(downloader.urllib.request, "urlopen", unexpected_request)


@pytest.fixture
def assets(tmp_path, monkeypatch):
    target = tmp_path / "acoustic-model"
    target.mkdir()
    monkeypatch.setattr(downloader, "FILES", {"model.int8.onnx": 5, "tokens.txt": 6})
    (target / "model.int8.onnx").write_bytes(b"model")
    (target / "tokens.txt").write_bytes(b"tokens")
    vad = b"verified-vad"
    monkeypatch.setattr(downloader, "VAD_SIZE", len(vad))
    monkeypatch.setattr(downloader, "VAD_SHA256", hashlib.sha256(vad).hexdigest())
    return target, target.parent / downloader.VAD_FILENAME, vad


@pytest.fixture
def denoiser_assets(assets, monkeypatch):
    target, vad_path, vad = assets
    denoiser = b"verified-gtcrn"
    monkeypatch.setattr(downloader, "DENOISER_SIZE", len(denoiser))
    monkeypatch.setattr(
        downloader, "DENOISER_SHA256", hashlib.sha256(denoiser).hexdigest()
    )
    return target, vad_path, vad, target.parent / downloader.DENOISER_FILENAME, denoiser


class DownloadResponse(io.BytesIO):
    def __init__(self, data: bytes, *, status: int = 200):
        super().__init__(data)
        self.status = status
        self.headers = {"Content-Length": str(len(data))}


def test_default_destination_resolves_from_script():
    target = downloader._target_dir(None)
    backend = Path(downloader.__file__).resolve().parents[1]
    assert target == backend / "data" / "asr_models" / downloader.MODEL_DIR_NAME
    assert (
        target.parent / downloader.VAD_FILENAME
        == backend / "data" / "asr_models" / "silero_vad.onnx"
    )


@pytest.mark.parametrize("check", [False, True])
def test_vad_remains_optional_for_existing_model(assets, capsys, check):
    target, vad_path, _ = assets
    args = ["--output-dir", str(target)] + (["--check"] if check else [])
    assert downloader.main(args) == 0
    assert not vad_path.exists()
    assert "silero_vad.onnx" not in capsys.readouterr().out


@pytest.mark.parametrize("with_vad", [False, True])
@pytest.mark.parametrize("with_denoiser", [False, True])
def test_optional_assets_can_be_checked_in_any_combination(
    denoiser_assets, capsys, with_vad, with_denoiser
):
    target, vad_path, vad, denoiser_path, denoiser = denoiser_assets
    args = ["--output-dir", str(target), "--check"]
    if with_vad:
        args.append("--with-vad")
    if with_denoiser:
        args.append("--with-denoiser")
    assert downloader.main(args) == (1 if with_vad or with_denoiser else 0)
    output = capsys.readouterr().out
    assert ("silero_vad.onnx" in output) == with_vad
    assert ("gtcrn_simple.onnx" in output) == with_denoiser
    vad_path.write_bytes(vad)
    denoiser_path.write_bytes(denoiser)
    assert downloader.main(args) == 0
    output = capsys.readouterr().out
    assert ("[已就位] silero_vad.onnx" in output) == with_vad
    assert ("[已就位] gtcrn_simple.onnx" in output) == with_denoiser


@pytest.mark.parametrize("mirror", [None, "https://model-mirror.example/gtcrn.onnx"])
def test_with_denoiser_downloads_only_selected_model_to_sibling_directory(
    denoiser_assets, monkeypatch, mirror
):
    target, vad_path, _, denoiser_path, denoiser = denoiser_assets
    requests = []

    def respond(request, timeout):
        requests.append(request.full_url)
        return DownloadResponse(denoiser)

    monkeypatch.setattr(downloader.urllib.request, "urlopen", respond)
    args = ["--output-dir", str(target), "--with-denoiser"]
    if mirror:
        args.extend(["--denoiser-url", mirror])
    assert downloader.main(args) == 0
    assert requests == [mirror or downloader.DEFAULT_DENOISER_URL]
    assert denoiser_path.read_bytes() == denoiser
    assert not (target / downloader.DENOISER_FILENAME).exists()
    assert not denoiser_path.with_suffix(".onnx.part").exists()
    assert not vad_path.exists()


def test_with_vad_and_denoiser_downloads_both_to_same_parent(
    denoiser_assets, monkeypatch
):
    target, vad_path, vad, denoiser_path, denoiser = denoiser_assets
    requests = []
    payloads = {
        downloader.DEFAULT_VAD_URL: vad,
        downloader.DEFAULT_DENOISER_URL: denoiser,
    }

    def respond(request, timeout):
        requests.append(request.full_url)
        return DownloadResponse(payloads[request.full_url])

    monkeypatch.setattr(downloader.urllib.request, "urlopen", respond)
    assert (
        downloader.main(["--output-dir", str(target), "--with-vad", "--with-denoiser"])
        == 0
    )
    assert requests == [downloader.DEFAULT_VAD_URL, downloader.DEFAULT_DENOISER_URL]
    assert vad_path.parent == denoiser_path.parent == target.parent
    assert vad_path.read_bytes() == vad
    assert denoiser_path.read_bytes() == denoiser


def test_denoiser_check_and_download_reject_same_size_corruption(
    denoiser_assets, monkeypatch, capsys
):
    target, _, _, denoiser_path, denoiser = denoiser_assets
    corrupt = b"x" * len(denoiser)
    denoiser_path.write_bytes(corrupt)
    args = ["--output-dir", str(target), "--with-denoiser"]
    assert downloader.main(args + ["--check"]) == 1
    assert "[不完整] gtcrn_simple.onnx" in capsys.readouterr().out
    monkeypatch.setattr(
        downloader.urllib.request,
        "urlopen",
        lambda request, timeout: DownloadResponse(corrupt),
    )
    assert downloader.main(args) == 1
    assert denoiser_path.read_bytes() == corrupt
    assert denoiser_path.with_suffix(".onnx.part").read_bytes() == corrupt
    assert "SHA256" in capsys.readouterr().err


def test_check_with_vad_reports_all_missing_assets(assets, capsys):
    target, _, _ = assets
    (target / "tokens.txt").unlink()
    assert downloader.main(["--output-dir", str(target), "--check", "--with-vad"]) == 1
    output = capsys.readouterr().out
    assert "[已就位] model.int8.onnx" in output
    assert "[未找到] tokens.txt" in output
    assert "[未找到] silero_vad.onnx" in output


def test_check_with_vad_validates_same_size_corruption(assets, capsys):
    target, vad_path, vad = assets
    vad_path.write_bytes(b"x" * len(vad))
    args = ["--output-dir", str(target), "--check", "--with-vad"]
    assert downloader.main(args) == 1
    assert "[不完整] silero_vad.onnx" in capsys.readouterr().out
    vad_path.write_bytes(vad)
    assert downloader.main(args) == 0
    assert "[已就位] silero_vad.onnx" in capsys.readouterr().out


def test_with_vad_downloads_only_missing_vad_to_sibling_directory(assets, monkeypatch):
    target, vad_path, vad = assets
    requests = []

    def respond(request, timeout):
        requests.append(request.full_url)
        return DownloadResponse(vad)

    monkeypatch.setattr(downloader.urllib.request, "urlopen", respond)
    mirror = "https://model-mirror.example/silero.onnx"
    assert (
        downloader.main(
            ["--output-dir", str(target), "--with-vad", "--vad-url", mirror]
        )
        == 0
    )
    assert requests == [mirror]
    assert vad_path.read_bytes() == vad
    assert not (target / downloader.VAD_FILENAME).exists()
    assert not vad_path.with_suffix(".onnx.part").exists()


def test_vad_default_url_is_used_without_mirror(assets, monkeypatch):
    target, _, vad = assets
    requests = []

    def respond(request, timeout):
        requests.append(request.full_url)
        return DownloadResponse(vad)

    monkeypatch.setattr(downloader.urllib.request, "urlopen", respond)
    assert downloader.main(["--output-dir", str(target), "--with-vad"]) == 0
    assert requests == [downloader.DEFAULT_VAD_URL]


@pytest.mark.parametrize("bad_data", [b"short", b"x" * len(b"verified-vad")])
def test_corrupt_vad_download_does_not_replace_existing_file(
    assets, monkeypatch, bad_data
):
    target, vad_path, _ = assets
    vad_path.write_bytes(b"previous-file")
    monkeypatch.setattr(
        downloader.urllib.request,
        "urlopen",
        lambda request, timeout: DownloadResponse(bad_data),
    )
    assert downloader.main(["--output-dir", str(target), "--with-vad"]) == 1
    assert vad_path.read_bytes() == b"previous-file"
    assert vad_path.with_suffix(".onnx.part").read_bytes() == bad_data


def test_vad_download_resumes_and_checks_complete_hash(assets, monkeypatch):
    _, vad_path, vad = assets
    part = vad_path.with_suffix(".onnx.part")
    part.write_bytes(vad[:4])

    def respond(request, timeout):
        assert request.get_header("Range") == "bytes=4-"
        return DownloadResponse(vad[4:], status=206)

    monkeypatch.setattr(downloader.urllib.request, "urlopen", respond)
    downloader._download(
        downloader.DEFAULT_VAD_URL, vad_path, len(vad), downloader.VAD_SHA256
    )
    assert vad_path.read_bytes() == vad
    assert not part.exists()


@pytest.mark.parametrize(
    "part_data",
    [b"verified-vad", b"x" * len(b"verified-vad"), b"too-large-verified-vad"],
)
def test_range_416_validates_part_before_atomic_rename(assets, monkeypatch, part_data):
    _, vad_path, vad = assets
    part = vad_path.with_suffix(".onnx.part")
    part.write_bytes(part_data)

    def range_not_satisfiable(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 416, "range not satisfiable", {}, None
        )

    monkeypatch.setattr(downloader.urllib.request, "urlopen", range_not_satisfiable)
    if part_data == vad:
        downloader._download(
            downloader.DEFAULT_VAD_URL, vad_path, len(vad), downloader.VAD_SHA256
        )
        assert vad_path.read_bytes() == vad
        assert not part.exists()
    else:
        with pytest.raises(RuntimeError, match="大小不符|SHA256"):
            downloader._download(
                downloader.DEFAULT_VAD_URL, vad_path, len(vad), downloader.VAD_SHA256
            )
        assert not vad_path.exists()
        assert part.read_bytes() == part_data
