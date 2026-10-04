"""SAV label semantics verified against the authors' public label metadata."""
from __future__ import annotations

import hashlib
import re
from importlib.resources import files
from pathlib import Path


# The authors' README, step 5.4, links this exact education_first_label.pbtxt.
# Retrieved 2026-10-04; the packaged file preserves its original UTF-8 bytes.
LABEL_SOURCE = "https://drive.google.com/file/d/1bRS5ia_9UUlBTRNuGvc8jBFv3lHLSseg/view"
LABEL_INDEX = "https://github.com/Ritatanz/SAV#step-5-download-the-annotations-files-and-put-them-in-the-annotations-folder"
LABEL_SHA256 = "02210b6cbebbd0ab5119af5c1adc29cd6fd132f24676107f15bb493e44d7ade2"


def _parse_labels(raw: bytes) -> dict[int, str]:
    """Parse the limited item/name/id schema in the official label map."""
    text = raw.decode("utf-8-sig")
    names = {}
    blocks = list(re.finditer(r"item\s*\{([^{}]*)\}", text))
    if not blocks or re.sub(r"item\s*\{[^{}]*\}", "", text).strip():
        raise ValueError("Invalid SAV label metadata")
    for block in blocks:
        fields = block.group(1)
        name = re.search(r'name\s*:\s*"([a-z_]+)"\s*;?', fields)
        label = re.search(r"id\s*:\s*(\d+)\s*;?", fields)
        if name is None or label is None:
            raise ValueError("Invalid SAV label metadata")
        remainder = fields[:name.start()] + fields[name.end():]
        if re.sub(r"id\s*:\s*\d+\s*;?", "", remainder, count=1).strip():
            raise ValueError("Invalid SAV label metadata")
        label_id = int(label.group(1))
        if label_id in names or name.group(1) in names.values():
            raise ValueError("Duplicate SAV label metadata")
        names[label_id] = name.group(1)
    return names


def verified_action_names(root: Path) -> tuple[dict[int, str], dict]:
    """Return the fingerprinted authors' map; reject a conflicting local map."""
    raw = files("behavior_recognition").joinpath("metadata/sav_action_labels.pbtxt").read_bytes()
    if hashlib.sha256(raw).hexdigest() != LABEL_SHA256:
        raise ValueError("Packaged SAV label metadata fingerprint mismatch")
    names = _parse_labels(raw)
    local_path = root / "annotations" / "education_first_label.pbtxt"
    audit = {"source_url": LABEL_SOURCE, "index_url": LABEL_INDEX,
             "source_sha256": LABEL_SHA256,
             "action_names": {str(key): value for key, value in names.items()},
             "target_mapping": {"read": "READ", "take_notes": "WRITE"}}
    if local_path.exists():
        local_raw = local_path.read_bytes()
        if _parse_labels(local_raw) != names:
            raise ValueError("Local SAV label metadata disagrees with verified official map")
        audit["local_metadata_sha256"] = hashlib.sha256(local_raw).hexdigest()
    return names, audit
