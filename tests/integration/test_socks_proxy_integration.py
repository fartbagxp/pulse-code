"""Integration test for the LLM_HTTP_PROXY code path.

Self-contained: spins up a local SOCKS5 relay and a local mock LLM HTTP
server, so this genuinely exercises AzureOpenAIQueryBuilder's proxy wiring
end-to-end — real sockets, real SOCKS handshake, real HTTP request/response
— without needing a real Azure resource, real credentials, or a real
external proxy. Complements test_llm_provider_live.py, which does need
those and is skipped when they aren't configured.
"""

from __future__ import annotations

import pytest

from pulse.llm_builder import AzureOpenAIQueryBuilder, WonderRequest, get_query_builder

pytestmark = pytest.mark.integration


def test_azure_openai_request_routes_through_socks_proxy(
    monkeypatch, socks_proxy, mock_llm_server
):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", mock_llm_server.url)
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4-mini")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    monkeypatch.setenv("LLM_HTTP_PROXY", socks_proxy.url)

    builder = get_query_builder("azure_openai")
    assert isinstance(builder, AzureOpenAIQueryBuilder)

    request = builder.build("TB cases by year")

    # The request actually went through our SOCKS relay, not direct —
    # proves LLM_HTTP_PROXY is wired all the way into the HTTP client.
    assert ("127.0.0.1", mock_llm_server.port) in socks_proxy.connections
    assert mock_llm_server.request_count == 1

    # And the mocked tool call was correctly parsed and merged onto D202's
    # bundled-query fallback template (same regression covered in
    # test_llm_builder.py, exercised here via the full provider + proxy path).
    assert isinstance(request, WonderRequest)
    assert request.dataset_id == "D202"
    names = {p.name for p in request.parameters}
    assert "O_age" in names  # came from the merge, not the mocked response
    assert "dataset_code" in names


def test_azure_openai_request_without_proxy_does_not_touch_socks_server(
    monkeypatch, socks_proxy, mock_llm_server
):
    """Sanity check for the test infra itself: without LLM_HTTP_PROXY set,
    the SOCKS relay should see zero connections — confirms the proxy
    assertion above is actually meaningful, not a tautology."""
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", mock_llm_server.url)
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4-mini")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    monkeypatch.delenv("LLM_HTTP_PROXY", raising=False)

    builder = get_query_builder("azure_openai")
    builder.build("TB cases by year")

    assert socks_proxy.connections == []
    assert mock_llm_server.request_count == 1
