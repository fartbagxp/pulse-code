# Testing

```bash
uv run pytest                  # unit tests only, fast, no network (default)
uv run pytest -m integration   # + integration tests (see below)
```

Unit tests cover catalog and matcher lookups, XML template merging (including
a regression test for the CDC WONDER radio-button trap), AAR constraints,
provider selection, and every CLI command that works offline.

Integration tests live in `tests/integration/` and are excluded by default.
There are two of them, and they behave differently.

`test_socks_proxy_integration.py` always runs. It spins up a local SOCKS5
relay and a local mock LLM HTTP server, so it exercises `LLM_HTTP_PROXY` for
real (an actual SOCKS handshake and an actual HTTP request and response)
without needing Azure or Anthropic credentials.

`test_llm_provider_live.py` hits whatever you have configured:
`ANTHROPIC_API_KEY`, or `LLM_PROVIDER=azure_openai` plus the `AZURE_OPENAI_*`
variables, plus `LLM_HTTP_PROXY` if you use one. It skips when credentials
aren't set. It also skips, rather than fails, when the provider is reachable
but blocked at the network layer, for example an Azure OpenAI resource with
public access disabled and no working proxy. That's a gap in the environment,
not a defect in the code.
