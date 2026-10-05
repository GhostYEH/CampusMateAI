"""Catch runtime contract drift in the existing pytest/CI entry point."""
import importlib.util
import json
import re
from pathlib import Path

import pytest
from starlette.routing import WebSocketRoute

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


def test_documented_counts_websockets_and_learning_space_handlers_match_sources():
    api_docs = docs.SNAPSHOT.parent
    saved = json.loads(docs.SNAPSHOT.read_text(encoding="utf-8"))
    methods = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
    operation_count = sum(method in methods for operations in saved["paths"].values() for method in operations)
    websocket_paths = {route.path for route in create_app().routes if isinstance(route, WebSocketRoute)}
    response_contracts = (api_docs / "response-contracts.md").read_text(encoding="utf-8")
    documented_websockets = set(re.findall(r"WS (/[^`?\s]+)", response_contracts))
    assert documented_websockets == websocket_paths
    readme = (api_docs / "README.md").read_text(encoding="utf-8")
    counts = re.search(r"(\d+) 个 HTTP 操作、(\d+) 个路径、(\d+) 个 WebSocket", readme)
    assert counts is not None
    assert tuple(map(int, counts.groups())) == (operation_count, len(saved["paths"]), len(websocket_paths))
    web_map = (api_docs / "web-map.md").read_text(encoding="utf-8")
    count = re.search(r"覆盖方式：(\d+) 个后端操作", web_map)
    assert count is not None and int(count[1]) == operation_count

    route_root = docs.ROOT / "magicclass-app" / "app" / "api"
    expected = set()
    for route in route_root.rglob("route.ts"):
        path = "/api/" + route.parent.relative_to(route_root).as_posix()
        path = re.sub(r"\[([^]]+)\]", r"{\1}", path)
        source = route.read_text(encoding="utf-8")
        handlers = re.findall(
            r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|TRACE)\b"
            r"|export\s+const\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|TRACE)\b", source,
        )
        expected.update((function or constant, path) for function, constant in handlers)
    assert expected, "No independent learning-space handlers found"
    source = (api_docs / "learning-space.md").read_text(encoding="utf-8")
    rows = set(re.findall(r"^\| (GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|TRACE) \| `([^`]+)` \|", source, re.MULTILINE))
    sections = set(re.findall(r"^### `(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|TRACE) (/api/[^`]+)`", source, re.MULTILINE))
    assert rows == sections == expected, f"Missing/stale learning-space documentation: {(rows ^ expected) | (sections ^ expected)}"
    count = re.search(r"(\d+) 个显式 HTTP handler", readme)
    assert count is not None and int(count[1]) == len(expected)


def _assert_field_table_matches_schema(source, schema, context):
    rows = {name: (required, constraints) for name, required, constraints in re.findall(
        r"^\| `([^`]+)` \| .*? \| (是|否) \| (.*?) \|", source, re.MULTILINE,
    )}
    if not rows:  # Some contracts describe fields in prose instead of tables.
        return
    properties = schema.get("properties", {})
    assert rows.keys() == properties.keys(), f"{context}: missing/stale fields: {rows.keys() ^ properties.keys()}"
    for name, property_schema in properties.items():
        required, constraints = rows[name]
        assert (required == "是") == (name in schema.get("required", [])), f"{context}.{name}: required mismatch"
        branches = [property_schema, *property_schema.get("anyOf", [])]
        for branch in branches:
            for key in ("minLength", "maxLength", "minimum", "maximum", "minItems", "maxItems"):
                if key in branch:
                    value = branch[key]
                    documented = re.search(rf"\b{key}=(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(?=;|\s|$)", constraints)
                    assert documented and float(documented[1]) == value, f"{context}.{name}: missing {key}={value}"


def test_markdown_schema_and_operation_field_tables_match_openapi():
    api_docs = docs.SNAPSHOT.parent
    saved = json.loads(docs.SNAPSHOT.read_text(encoding="utf-8"))
    schemas = saved["components"]["schemas"]
    fields = (api_docs / "schemas.md").read_text(encoding="utf-8")
    for name, section in re.findall(r"^## (\w+)\s*\n(.*?)(?=^## |\Z)", fields, re.MULTILINE | re.DOTALL):
        _assert_field_table_matches_schema(section, schemas[name], name)

    for module in sorted(api_docs.glob("[0-9][0-9]-*.md")):
        source = module.read_text(encoding="utf-8")
        sections = re.findall(
            r"^### `(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|TRACE) ([^`]+)`\s*\n(.*?)(?=^### `|\Z)",
            source, re.MULTILINE | re.DOTALL,
        )
        for method, path, section in sections:
            operation = saved["paths"][path][method.lower()]
            context = f"{module.name}: {method} {path}"
            if "请求体：" in section:
                request = section.split("请求体：", 1)[1].split("请求结构示例", 1)[0].split("响应：", 1)[0]
                for content in operation.get("requestBody", {}).get("content", {}).values():
                    reference = content.get("schema", {}).get("$ref")
                    if reference:
                        _assert_field_table_matches_schema(request, schemas[reference.rsplit("/", 1)[-1]], context)
            if "| HTTP | Content-Type | 结构 |" in section:
                statuses = set(re.findall(r"^\| (\d{3}) \|", section, re.MULTILINE))
                assert operation["responses"].keys() <= statuses, f"{context}: missing response statuses"
            for status, response in operation.get("responses", {}).items():
                marker = f"{status} 响应顶层字段："
                if not status.startswith("2") or marker not in section:
                    continue
                body = section.split(marker, 1)[1].split("异常：", 1)[0].split("路由及", 1)[0]
                for content in response.get("content", {}).values():
                    reference = content.get("schema", {}).get("$ref")
                    if reference:
                        _assert_field_table_matches_schema(body, schemas[reference.rsplit("/", 1)[-1]], context)


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
