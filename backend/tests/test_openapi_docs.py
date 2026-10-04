"""Catch runtime contract drift in the existing pytest/CI entry point."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

from app.main import create_app

spec = importlib.util.spec_from_file_location("sync_api_docs", Path(__file__).resolve().parents[2] / "scripts/sync_api_docs.py")
docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docs)


def test_documented_openapi_matches_runtime_and_preserves_supplements():
    saved = json.loads(docs.SNAPSHOT.read_text(encoding="utf-8"))
    runtime = create_app().openapi()
    assert not docs.exception_response_differences(runtime)
    expected = docs.documented_schema(runtime, saved)
    assert not docs.differences(saved, expected)
    assert docs.SUPPLEMENTAL_SCHEMAS <= saved["components"]["schemas"].keys()


def test_markdown_covers_all_http_operations_models_and_schema_links():
    api_docs = docs.SNAPSHOT.parent
    saved = json.loads(docs.SNAPSHOT.read_text(encoding="utf-8"))
    methods = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
    expected = {(method.upper(), path) for path, operations in saved["paths"].items()
                for method in operations if method in methods}
    covered = set()
    for module in sorted(api_docs.glob("[0-9][0-9]-*.md")):
        source = module.read_text(encoding="utf-8")
        rows = set(re.findall(r"^\| (GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|TRACE) \| `([^`]+)` \|", source, re.MULTILINE))
        sections = set(re.findall(r"^### `(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|TRACE) ([^`]+)`", source, re.MULTILINE))
        assert rows == sections, f"{module.name}: index and full contract sections differ: {rows ^ sections}"
        assert not covered & rows, f"{module.name}: duplicated operations: {covered & rows}"
        covered.update(rows)
    assert covered == expected, f"Missing/stale HTTP documentation: {covered ^ expected}"

    fields = (api_docs / "schemas.md").read_text(encoding="utf-8")
    headings = set(re.findall(r"^## (\w+)\s*$", fields, re.MULTILINE))
    assert headings == saved["components"]["schemas"].keys()
    anchors = set(re.findall(r'<a id="([^"]+)"', fields))
    for document in api_docs.glob("*.md"):
        referenced = set(re.findall(r"\]\(schemas\.md#([^)]*)\)", document.read_text(encoding="utf-8")))
        assert referenced <= anchors, f"{document.name}: missing schema anchors: {referenced - anchors}"


def test_missing_supplement_is_not_silently_erased():
    saved = json.loads(docs.SNAPSHOT.read_text(encoding="utf-8"))
    del saved["components"]["schemas"]["ChatFinalMeta"]
    with pytest.raises(ValueError, match="ChatFinalMeta"):
        docs.documented_schema(create_app().openapi(), saved)


def test_checker_detects_changed_http_and_model_contracts():
    saved = json.loads(docs.SNAPSHOT.read_text(encoding="utf-8"))
    expected = docs.documented_schema(create_app().openapi(), saved)
    del saved["paths"]["/api/v1/chaoxing/status"]["get"]["responses"]["503"]
    saved["components"]["schemas"]["ChaoxingSyncStatus"]["properties"]["status"]["type"] = "integer"
    changes = docs.differences(saved, expected)
    assert any("responses/503" in path for path in changes)
    assert any("properties/status/type" in path for path in changes)


@pytest.mark.parametrize("path,method", next(iter(docs.APP_EXCEPTION_OPERATIONS.values())))
def test_checker_rejects_undocumented_indirect_exceptions_even_after_regeneration(path, method):
    runtime = create_app().openapi()
    del runtime["paths"][path][method]["responses"]["503"]
    # Matching snapshots alone cannot detect the global-handler omission.
    assert not docs.differences(runtime, runtime)
    assert any(path in change and "CHAOXING_CREDENTIALS_UNAVAILABLE" in change
               for change in docs.exception_response_differences(runtime))
