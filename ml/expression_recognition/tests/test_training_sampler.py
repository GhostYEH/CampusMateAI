from types import SimpleNamespace

import torch

from expression_recognition import train
from expression_recognition.data import BalancedBatchSampler


def test_training_sets_resumed_epoch_on_sampler_after_oom_rebuild(monkeypatch) -> None:
    first = SimpleNamespace(batch_sampler=BalancedBatchSampler(list(range(7)) * 4, 14))
    rebuilt = SimpleNamespace(batch_sampler=BalancedBatchSampler(list(range(7)) * 4, 7))
    seen = []

    def run_epoch(model, loader, *args):
        seen.append(loader.batch_sampler.epoch)
        if loader is first:
            raise torch.cuda.OutOfMemoryError("synthetic retry")
        return {"loss": 0.0}

    monkeypatch.setattr(train, "run_epoch", run_epoch)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    metrics = train.run_epoch_with_oom_recovery(
        None, lambda size: (None, rebuilt, None), None, torch.device("cuda"),
        None, None, 1.0, None,
        {"batch_size": 14, "train_loader": first, "epoch": 7},
    )
    assert seen == [7, 7]
    assert metrics["batch_size"] == 7
