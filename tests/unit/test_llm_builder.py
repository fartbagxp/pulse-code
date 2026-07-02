"""Unit tests for llm_builder.py — template merging, constraints, provider
selection, and SOCKS proxy wiring. No network calls; where a provider's
constructor would normally reach out, we stop short of the actual request."""

from __future__ import annotations

import httpcore
import pytest

from pulse.llm_builder import (
    AzureOpenAIQueryBuilder,
    LLMQueryBuilder,
    WonderParam,
    WonderRequest,
    WonderRequestSet,
    _apply_constraints,
    _build_http_client,
    _finalize_request,
    _merge_overrides,
    _parse_xml_params,
    get_query_builder,
)


# ── WonderRequest / XML round-trip ──────────────────────────────────────


def test_wonder_request_to_xml_basic_structure():
    req = WonderRequest(
        dataset_id="D202",
        parameters=[WonderParam(name="B_1", values=["D202.V20"])],
    )
    xml = req.to_xml()
    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?><request-parameters>')
    assert "<name>B_1</name>" in xml
    assert "<value>D202.V20</value>" in xml


def test_wonder_request_to_xml_empty_value_becomes_self_closing_tag():
    req = WonderRequest(
        dataset_id="D202", parameters=[WonderParam(name="I_D202.V22", values=[""])]
    )
    assert "<value/>" in req.to_xml()


def test_parse_xml_params_round_trips_through_to_xml():
    req = WonderRequest(
        dataset_id="D202",
        parameters=[
            WonderParam(name="B_1", values=["D202.V20"]),
            WonderParam(name="V_D202.V13", values=["T40.1", "T40.2"]),
        ],
    )
    parsed = _parse_xml_params(req.to_xml())
    assert parsed[0].name == "B_1"
    assert parsed[0].values == ["D202.V20"]
    assert parsed[1].values == ["T40.1", "T40.2"]


# ── template merging (_merge_overrides / _finalize_request) ────────────


def test_merge_overrides_replaces_matching_param_and_appends_new():
    template_xml = (
        '<?xml version="1.0" encoding="UTF-8"?><request-parameters>'
        "<parameter><name>B_1</name><value>*None*</value></parameter>"
        "<parameter><name>dataset_code</name><value>D202</value></parameter>"
        "</request-parameters>"
    )
    merged_xml = _merge_overrides(
        template_xml, [WonderParam(name="B_1", values=["D202.V20"])]
    )
    params = {p.name: p.values for p in _parse_xml_params(merged_xml)}
    assert params["B_1"] == ["D202.V20"]
    assert params["dataset_code"] == ["D202"]


def test_finalize_request_merges_onto_real_base_template():
    """D176 has a real D176-base.xml — merging should pull in the full
    boilerplate (100+ params) from just one override."""
    raw = WonderRequest(
        dataset_id="D176",
        parameters=[WonderParam(name="B_1", values=["D176.V1-level1"])],
    )
    merged = _finalize_request(raw)
    names = {p.name for p in merged.parameters}
    assert "dataset_code" in names
    assert "action-Send" in names
    assert len(merged.parameters) > 50


def test_finalize_request_falls_back_to_bundled_query_for_d202():
    """Regression test for the CDC WONDER radio-button-trap HTTP 500: D202
    has no D202-base.xml, so _finalize_request must fall back to merging
    onto its bundled query (which carries the required O_age/O_race radio
    buttons) instead of silently returning unmerged overrides."""
    raw = WonderRequest(
        dataset_id="D202",
        parameters=[WonderParam(name="B_1", values=["D202.V20"])],
    )
    merged = _finalize_request(raw)
    names = {p.name for p in merged.parameters}
    assert "O_age" in names
    assert "O_race" in names
    assert "dataset_code" in names
    assert len(merged.parameters) > 1


@pytest.mark.parametrize("dataset_id", ["D204", "D178", "D117", "D128"])
def test_finalize_request_works_for_previously_unsupported_datasets(dataset_id):
    raw = WonderRequest(
        dataset_id=dataset_id, parameters=[WonderParam(name="B_1", values=["*None*"])]
    )
    merged = _finalize_request(raw)
    names = {p.name for p in merged.parameters}
    assert "dataset_code" in names
    assert "action-Send" in names


def test_finalize_request_with_unknown_dataset_returns_raw_unmerged():
    raw = WonderRequest(
        dataset_id="D999999", parameters=[WonderParam(name="B_1", values=["*None*"])]
    )
    merged = _finalize_request(raw)
    assert merged.parameters == raw.parameters


# ── AAR / age-grouping constraint ───────────────────────────────────────


def test_apply_constraints_disables_aar_when_grouping_by_age():
    overrides = [WonderParam(name="B_1", values=["D176.V5"])]  # ten-year age
    constrained = _apply_constraints(overrides)
    by_name = {p.name: p.values for p in constrained}
    assert by_name["O_aar_enable"] == ["false"]
    assert by_name["O_aar"] == ["aar_none"]


def test_apply_constraints_leaves_non_age_grouping_untouched():
    overrides = [WonderParam(name="B_1", values=["D176.V1-level1"])]  # year
    constrained = _apply_constraints(overrides)
    names = {p.name for p in constrained}
    assert "O_aar_enable" not in names


# ── WonderRequestSet (comparison queries) ───────────────────────────────


def test_wonder_request_set_holds_multiple_requests():
    rs = WonderRequestSet(
        requests=[
            WonderRequest(dataset_id="D176", parameters=[]),
            WonderRequest(dataset_id="D66", parameters=[]),
        ],
        labels=["Opioid deaths", "Births"],
    )
    assert len(rs.requests) == len(rs.labels) == 2


# ── provider selection (get_query_builder) ──────────────────────────────


def test_get_query_builder_defaults_to_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    builder = get_query_builder()
    assert isinstance(builder, LLMQueryBuilder)


def test_get_query_builder_unknown_provider_raises_value_error():
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        get_query_builder("not-a-real-provider")


def test_get_query_builder_azure_missing_config_raises_runtime_error(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_API_KEY"):
        get_query_builder("azure_openai")


def test_get_query_builder_azure_with_full_config_constructs(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4-mini")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    builder = get_query_builder("azure_openai")
    assert isinstance(builder, AzureOpenAIQueryBuilder)
    assert builder.deployment == "gpt-5.4-mini"


def test_azure_openai_tool_schema_conversion():
    tools = AzureOpenAIQueryBuilder._to_openai_tools(
        [
            {
                "name": "build_wonder_query",
                "description": "desc",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]
    )
    assert tools == [
        {
            "type": "function",
            "function": {
                "name": "build_wonder_query",
                "description": "desc",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]


# ── SOCKS proxy wiring (_build_http_client) ─────────────────────────────


def test_build_http_client_returns_none_without_proxy_env_var(monkeypatch):
    monkeypatch.delenv("LLM_HTTP_PROXY", raising=False)
    assert _build_http_client() is None


def test_build_http_client_wires_socks5h_proxy(monkeypatch):
    """Confirms the proxy URL actually results in an httpcore.SOCKSProxy
    transport — not a silent no-op — without needing a real reachable
    proxy (the client is constructed but never asked to connect)."""
    monkeypatch.setenv("LLM_HTTP_PROXY", "socks5h://127.0.0.1:1080")
    client = _build_http_client()
    assert client is not None
    mounts = client._mounts
    assert len(mounts) == 1
    transport = next(iter(mounts.values()))
    assert isinstance(transport._pool, httpcore.SOCKSProxy)
    client.close()


def test_build_http_client_wires_http_proxy(monkeypatch):
    monkeypatch.setenv("LLM_HTTP_PROXY", "http://127.0.0.1:8080")
    client = _build_http_client()
    transport = next(iter(client._mounts.values()))
    assert isinstance(transport._pool, httpcore.HTTPProxy)
    client.close()
