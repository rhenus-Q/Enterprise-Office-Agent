"""Stable OpenAPI wire-contract regression for the two public API routes.

The checked-in fixture intentionally is not the complete FastAPI document.
Descriptions, titles, summaries, operation IDs, tags, and other generated prose
do not affect JSON compatibility and would make the fixture noisy.  The
projection retains the selected request/response schemas and every transitively
referenced component, limited to JSON Schema keywords with wire semantics.
"""

import difflib
import json
from pathlib import Path

import pytest

from api.app import create_app

CONTRACT_PATH = Path(__file__).parent.parent / "contracts" / "api-openapi-wire-contract.json"
SELECTED_ENDPOINTS = {
    "/api/agent/run": "post",
    "/api/health": "get",
}

# OpenAPI 3.1 embeds JSON Schema. Keep compatibility-affecting keywords while
# dropping presentation-only metadata such as title, description, and examples.
_SCHEMA_KEYS = frozenset(
    {
        "$defs",
        "$ref",
        "additionalProperties",
        "allOf",
        "anyOf",
        "const",
        "contains",
        "contentEncoding",
        "contentMediaType",
        "default",
        "dependentRequired",
        "dependentSchemas",
        "deprecated",
        "discriminator",
        "else",
        "enum",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "format",
        "if",
        "items",
        "maxContains",
        "maxItems",
        "maxLength",
        "maxProperties",
        "maximum",
        "minContains",
        "minItems",
        "minLength",
        "minProperties",
        "minimum",
        "multipleOf",
        "not",
        "nullable",
        "oneOf",
        "pattern",
        "patternProperties",
        "prefixItems",
        "properties",
        "propertyNames",
        "readOnly",
        "required",
        "then",
        "type",
        "unevaluatedProperties",
        "uniqueItems",
        "writeOnly",
    }
)
_SCHEMA_MAP_KEYS = frozenset({"$defs", "dependentSchemas", "patternProperties", "properties"})
_SCHEMA_LIST_KEYS = frozenset({"allOf", "anyOf", "oneOf", "prefixItems"})
_SCHEMA_VALUE_KEYS = frozenset(
    {
        "additionalProperties",
        "contains",
        "else",
        "if",
        "items",
        "not",
        "propertyNames",
        "then",
        "unevaluatedProperties",
    }
)
_COMPONENT_REF_PREFIX = "#/components/schemas/"


def _project_schema(schema):
    """Return only JSON-compatibility semantics from one OpenAPI schema."""

    if not isinstance(schema, dict):
        return schema

    projected = {}
    for key, value in schema.items():
        if key not in _SCHEMA_KEYS:
            continue
        if key in _SCHEMA_MAP_KEYS:
            projected[key] = {
                name: _project_schema(child_schema) for name, child_schema in value.items()
            }
        elif key in _SCHEMA_LIST_KEYS:
            # Composition order can affect validation, so these arrays are
            # deliberately preserved rather than sorted for cosmetic stability.
            projected[key] = [_project_schema(child_schema) for child_schema in value]
        elif key in _SCHEMA_VALUE_KEYS:
            projected[key] = _project_schema(value)
        else:
            projected[key] = value
    return projected


def _project_content(content):
    """Keep each declared media type and its wire schema, but no framework prose."""

    return {
        media_type: {"schema": _project_schema(media["schema"])}
        for media_type, media in content.items()
        if "schema" in media
    }


def _project_operation(operation):
    projected = {}

    if "requestBody" in operation:
        request_body = operation["requestBody"]
        projected_request = {}
        if "$ref" in request_body:
            projected_request["$ref"] = request_body["$ref"]
        if "required" in request_body:
            projected_request["required"] = request_body["required"]
        if "content" in request_body:
            projected_request["content"] = _project_content(request_body["content"])
        projected["requestBody"] = projected_request

    projected["responses"] = {}
    for status_code, response in operation["responses"].items():
        projected_response = {}
        if "$ref" in response:
            projected_response["$ref"] = response["$ref"]
        if "content" in response:
            projected_response["content"] = _project_content(response["content"])
        projected["responses"][status_code] = projected_response

    return projected


def _component_refs(value) -> set[str]:
    refs = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "$ref":
                assert child.startswith(_COMPONENT_REF_PREFIX), f"unsupported local ref: {child}"
                refs.add(child.removeprefix(_COMPONENT_REF_PREFIX))
            else:
                refs.update(_component_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.update(_component_refs(child))
    return refs


def _reachable_components(paths, available_components):
    """Compute the complete component closure rooted at the selected operations."""

    reachable = {}
    pending = _component_refs(paths)
    while pending:
        name = min(pending)
        pending.remove(name)
        if name in reachable:
            continue
        assert name in available_components, f"unresolved component ref: {name}"
        component = _project_schema(available_components[name])
        reachable[name] = component
        pending.update(_component_refs(component) - reachable.keys())
    return reachable


def _project_wire_contract(openapi):
    paths = {
        path: {method: _project_operation(openapi["paths"][path][method])}
        for path, method in SELECTED_ENDPOINTS.items()
    }
    components = _reachable_components(paths, openapi["components"]["schemas"])
    return {"components": {"schemas": components}, "paths": paths}


def _render_contract(contract) -> str:
    """Canonical text form used by both determinism and fixture comparisons."""

    return json.dumps(contract, indent=2, sort_keys=True) + "\n"


@pytest.fixture
def openapi_schema(monkeypatch):
    # Keep app construction independent of inherited runtime modes. Root
    # conftest already makes load_dotenv() a no-op for this ordinary test run.
    monkeypatch.setenv("PRIVACY_MODE", "false")
    monkeypatch.setenv("OFFLINE_MODE", "false")
    return create_app().openapi()


@pytest.fixture
def contract_fixture():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_selected_endpoint_methods_are_present(openapi_schema):
    for path, method in SELECTED_ENDPOINTS.items():
        assert path in openapi_schema["paths"]
        assert method in openapi_schema["paths"][path]


def test_current_wire_schema_exactly_matches_checked_in_contract(openapi_schema):
    expected = CONTRACT_PATH.read_text(encoding="utf-8")
    actual = _render_contract(_project_wire_contract(openapi_schema))

    if actual != expected:
        diff = "".join(
            difflib.unified_diff(
                expected.splitlines(keepends=True),
                actual.splitlines(keepends=True),
                fromfile=str(CONTRACT_PATH),
                tofile="current create_app().openapi() projection",
            )
        )
        pytest.fail(f"OpenAPI wire contract changed; review and update the fixture:\n{diff}")


def test_contract_fixture_contains_only_selected_paths(contract_fixture):
    assert contract_fixture["paths"].keys() == SELECTED_ENDPOINTS.keys()
    assert {path: set(path_item) for path, path_item in contract_fixture["paths"].items()} == {
        path: {method} for path, method in SELECTED_ENDPOINTS.items()
    }


def test_fixture_components_are_exactly_the_reachable_ref_closure(contract_fixture):
    components = contract_fixture["components"]["schemas"]
    reachable = _reachable_components(contract_fixture["paths"], components)

    assert set(reachable) == set(components)


def test_projection_is_byte_deterministic(monkeypatch):
    monkeypatch.setenv("PRIVACY_MODE", "false")
    monkeypatch.setenv("OFFLINE_MODE", "false")

    first = _render_contract(_project_wire_contract(create_app().openapi()))
    second = _render_contract(_project_wire_contract(create_app().openapi()))

    assert first.encode() == second.encode()


def test_high_value_wire_semantics_remain_explicit(contract_fixture):
    schemas = contract_fixture["components"]["schemas"]

    request = schemas["AgentRunRequest"]
    assert request["properties"]["text"] == {
        "type": "string",
        "minLength": 1,
        "maxLength": 4000,
    }

    options = schemas["RunOptionsRequest"]
    assert options["additionalProperties"] is False
    assert options["properties"]["privacy_mode"]["enum"] == ["standard", "strict"]

    assert schemas["HealthResponse"]["required"] == [
        "privacy_mode",
        "offline_mode",
        "office_llm_enabled",
        "web_search_effective",
    ]
    assert schemas["AgentRunResponse"]["required"] == [
        "intent",
        "content",
        "duration_ms",
        "execution_mode",
    ]

    assert schemas["AgentRunResponse"]["properties"]["observability"]["anyOf"] == [
        {"$ref": "#/components/schemas/KnowledgeObservabilityModel"},
        {"type": "null"},
    ]
    assert schemas["KnowledgeObservabilityModel"]["properties"]["run_id"]["anyOf"] == [
        {"type": "string"},
        {"type": "null"},
    ]

    settings = schemas["RunSettingsModel"]
    for field in ("requested", "effective"):
        values_name = settings["properties"][field]["$ref"].removeprefix(_COMPONENT_REF_PREFIX)
        assert schemas[values_name]["properties"]["web_search"] == {"type": "boolean"}
