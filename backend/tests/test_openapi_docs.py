"""Catch runtime contract drift in the existing pytest/CI entry point."""
import importlib.util
import json
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
