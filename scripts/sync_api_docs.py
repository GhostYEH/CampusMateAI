"""Synchronize the runtime OpenAPI snapshot while preserving documented supplements.

Run with the backend Python environment, from any working directory:
    python scripts/sync_api_docs.py --check
    python scripts/sync_api_docs.py
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from importlib import import_module
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "docs" / "api" / "openapi.json"
SUPPLEMENTAL_SCHEMAS = frozenset({
    "ChatFinalMeta", "ChatSource", "ClassMemberOut", "ErrandExtra",
    "InteractiveClassroomInput", "LearningGoalInput", "NoticeOut", "RecruitExtra", "SuggestedAction",
})
DOCUMENT_INFO_FIELDS = ("title", "version", "description")
APP_EXCEPTION_OPERATIONS = {
    "app.repositories.chaoxing_repository.ChaoxingCredentialsUnavailable": (
        ("/api/v1/chaoxing/status", "get"),
        ("/api/v1/chaoxing/sync", "post"),
        ("/api/v1/courses/{course_id}/sync", "post"),
        ("/api/v1/courses/{course_id}/resources/{item_id}/download", "get"),
    ),
}


def exception_response_differences(runtime: dict) -> list[str]:
    """Check known indirect AppException paths independently of the snapshot.

    A global exception handler does not add responses to OpenAPI. Keep the
    known credential consumers here so deleting a runtime declaration and
    regenerating the snapshot cannot silently bless that omission.
    """
    changes = []
    for reference, operations in APP_EXCEPTION_OPERATIONS.items():
        module, name = reference.rsplit(".", 1)
        exception = getattr(import_module(module), name)
        for path, method in operations:
            response = runtime.get("paths", {}).get(path, {}).get(method, {}).get("responses", {}).get(str(exception.http_status))
            if response is None or exception.code not in response.get("description", ""):
                changes.append(f"$/paths/{path}/{method}/responses/{exception.http_status} ({exception.code})")
    return changes


def documented_schema(runtime: dict, saved: dict) -> dict:
    """The nine supplementary schemas and document metadata are intentional."""
    schema = deepcopy(runtime)
    current = schema["components"]["schemas"]
    saved_models = saved["components"]["schemas"]
    missing = SUPPLEMENTAL_SCHEMAS - saved_models.keys() - current.keys()
    if missing:
        raise ValueError(f"Missing documented supplemental schemas: {', '.join(sorted(missing))}")
    for name in sorted(SUPPLEMENTAL_SCHEMAS - current.keys()):
        current[name] = deepcopy(saved_models[name])
    for name in DOCUMENT_INFO_FIELDS:
        if name in saved.get("info", {}):
            schema["info"][name] = saved["info"][name]
    return schema


def differences(saved, expected, path="$") -> list[str]:
    """Report structure changes without dumping response bodies or credentials."""
    if isinstance(saved, dict) and isinstance(expected, dict):
        changes = [f"{path}/{key}" for key in sorted(saved.keys() ^ expected.keys())]
        for key in sorted(saved.keys() & expected.keys()):
            changes.extend(differences(saved[key], expected[key], f"{path}/{key}"))
        return changes
    return [] if saved == expected else [path]


def preserve_order(expected, saved):
    """Keep unchanged source ordering so regenerating produces a reviewable diff."""
    if isinstance(expected, dict):
        old = saved if isinstance(saved, dict) else {}
        keys = [key for key in old if key in expected] + [key for key in expected if key not in old]
        return {key: preserve_order(expected[key], old.get(key)) for key in keys}
    if isinstance(expected, list):
        old = saved if isinstance(saved, list) else []
        return [preserve_order(value, old[index] if index < len(old) else None) for index, value in enumerate(expected)]
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail on drift without writing files")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "backend"))
    from app.main import create_app

    saved = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    runtime = create_app().openapi()
    missing_exceptions = exception_response_differences(runtime)
    if missing_exceptions:
        print("Missing runtime AppException response declarations:")
        print("\n".join(missing_exceptions))
        return 1
    expected = documented_schema(runtime, saved)
    changed = differences(saved, expected)
    if args.check:
        if changed:
            print("OpenAPI documentation drift:")
            print("\n".join(changed[:20]))
            return 1
        print("OpenAPI snapshot matches runtime declarations and preserves supplemental schemas.")
    else:
        SNAPSHOT.write_text(json.dumps(preserve_order(expected, saved), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Updated docs/api/openapi.json ({len(changed)} differences).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
