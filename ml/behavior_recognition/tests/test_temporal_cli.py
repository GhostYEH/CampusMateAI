from behavior_recognition.cli import build_parser


def test_cli_accepts_temporal_manifest_and_training_commands():
    parser = build_parser()
    manifest = parser.parse_args(
        ["temporal-manifest", "--dataset-root", "data", "--output", "manifests"]
    )
    train = parser.parse_args(
        [
            "temporal-train", "--config", "config.yaml", "--manifests", "manifests",
            "--run-dir", "run", "--max-epochs", "1", "--source-onnx", "current.onnx",
        ]
    )

    assert manifest.command == "temporal-manifest"
    assert manifest.sequence_length == 16
    assert train.command == "temporal-train"
    assert train.max_epochs == 1
    assert str(train.source_onnx) == "current.onnx"
