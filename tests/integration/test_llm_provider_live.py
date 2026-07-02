"""Integration tests against your *actually configured* LLM provider —
whatever ANTHROPIC_API_KEY / LLM_PROVIDER=azure_openai + AZURE_OPENAI_* /
LLM_HTTP_PROXY are set to in your environment or .env file.

Unlike test_socks_proxy_integration.py (which is self-contained and always
runs), these hit real external services and cost real API calls. They:

  - skip if the required credentials for the configured provider aren't set
  - skip (not fail) if the provider is reachable but a network-layer
    restriction blocks it (e.g. an Azure OpenAI resource with public
    access disabled and no working LLM_HTTP_PROXY) — that's an environment
    gap to fix, not a code defect
  - actually fail if the provider responds but produces something wrong
"""

from __future__ import annotations

import os

import pytest

from pulse.llm_builder import WonderRequest, get_query_builder

pytestmark = pytest.mark.integration


def _configured_provider() -> str:
    return os.getenv("LLM_PROVIDER", "anthropic").lower()


def _missing_credentials() -> str | None:
    """Returns a human-readable reason if the configured provider's
    required credentials aren't set, else None."""
    provider = _configured_provider()
    if provider == "anthropic":
        if not os.getenv("ANTHROPIC_API_KEY"):
            return "ANTHROPIC_API_KEY is not set"
        return None
    if provider in ("azure_openai", "azure-openai", "azure"):
        required = (
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT",
            "AZURE_OPENAI_API_VERSION",
        )
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            return f"missing {', '.join(missing)} for LLM_PROVIDER=azure_openai"
        return None
    return f"unknown LLM_PROVIDER {provider!r}"


_SKIP_REASON = _missing_credentials()


@pytest.mark.skipif(bool(_SKIP_REASON), reason=_SKIP_REASON or "")
def test_live_provider_builds_a_real_query():
    provider = _configured_provider()
    builder = get_query_builder()

    try:
        request = builder.build("TB cases by year")
    except Exception as exc:  # noqa: BLE001 — deliberately broad: network/
        # permission failures here are an environment gap (e.g. missing
        # LLM_HTTP_PROXY for a private-endpoint-only Azure resource), not a
        # code defect worth failing CI over. Anything else re-raises as a
        # real test failure below via the isinstance/content assertions.
        message = str(exc)
        network_signals = (
            "connection",
            "public access is disabled",
            "403",
            "timed out",
            "getaddrinfo",
        )
        if any(sig in message.lower() for sig in network_signals):
            pytest.skip(
                f"{provider} provider unreachable from this environment: {message[:200]}"
            )
        raise

    assert isinstance(request, WonderRequest)
    assert request.dataset_id  # LLM picked *some* dataset
    xml = request.to_xml()
    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?><request-parameters>')
    names = {p.name for p in request.parameters}
    assert "action-Send" in names
    assert "dataset_code" in names
