from expression_recognition.data import DomainBalancedBatchSampler
from expression_recognition.data import ManifestDataset, create_mixed_domain_loader
from PIL import Image
from torchvision import transforms
import csv


def test_target_domain_batch_ratio_is_respected() -> None:
    sampler = DomainBalancedBatchSampler(
        public_count=80,
        target_count=20,
        target_ratio=0.5,
        batch_size=10,
        seed=7,
    )

    batch = next(iter(sampler))

    assert len(batch) == 10
    assert sum(index >= 80 for index in batch) == 5


def test_domain_sampler_is_reproducible_and_keeps_index_ranges() -> None:
    first = list(DomainBalancedBatchSampler(8, 3, 0.4, 5, seed=11))
    second = list(DomainBalancedBatchSampler(8, 3, 0.4, 5, seed=11))

    assert first == second
    assert all(0 <= index < 11 for batch in first for index in batch)


def test_target_manifest_path_field_is_loadable(tmp_path) -> None:
    image = tmp_path / "face.jpg"
    Image.new("L", (16, 16), color=80).save(image)
    manifest = tmp_path / "included.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "label_index", "status", "split"])
        writer.writeheader()
        writer.writerow({"path": str(image), "label_index": "5", "status": "included", "split": "train"})

    dataset = ManifestDataset(manifest, "train", transforms.ToTensor())

    tensor, label = dataset[0]
    assert tensor.shape == (1, 16, 16)
    assert label == 5


def test_mixed_loader_enforces_target_ratio_per_batch(tmp_path) -> None:
    def create_manifest(name: str, field: str, count: int, label: int) -> object:
        manifest = tmp_path / f"{name}.csv"
        with manifest.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=[field, "label_index", "status", "split"])
            writer.writeheader()
            for index in range(count):
                image = tmp_path / f"{name}-{index}.jpg"
                Image.new("L", (16, 16), color=20 + index).save(image)
                writer.writerow({field: str(image), "label_index": label, "status": "included", "split": "train"})
        return manifest

    public = create_manifest("public", "source_path", 8, 0)
    target = create_manifest("target", "path", 4, 5)
    config = {
        "input_size": 16,
        "input_channels": 1,
        "batch_size": 4,
        "num_workers": 0,
        "seed": 9,
        "target_domain_ratio": 0.5,
        "normalization": {"mean": [0.5], "std": [0.5]},
        "augmentation": {},
    }

    _, loader = create_mixed_domain_loader(public, target, "train", config, training=True)
    _, labels = next(iter(loader))

    assert labels.tolist().count(5) == 2
    assert labels.tolist().count(0) == 2
