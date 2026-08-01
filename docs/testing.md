# Testing

```bash
uv run pytest                  # unit tests only, fast, no network (default)
uv run pytest -m integration   # + integration tests (see below)
```

Unit tests cover catalog/matcher lookups, XML template merging (including
the CDC WONDER radio-button-trap regression), AAR constraints, provider
selection, and the offline-network-free CLI commands.

Integration tests (`tests/integration/`) are excluded by default and split
into two kinds:

- **`test_socks_proxy_integration.py`**: always runs. Spins up a local
  SOCKS5 relay and a local mock LLM HTTP server, so it actually exercises
  `LLM_HTTP_PROXY` end-to-end (real SOCKS handshake, real HTTP
  request/response) without needing real Azure/Anthropic credentials.
- **`test_llm_provider_live.py`**: hits whatever `ANTHROPIC_API_KEY` /
  `LLM_PROVIDER=azure_openai` + `AZURE_OPENAI_*` / `LLM_HTTP_PROXY` you
  actually have configured. Skips if credentials aren't set; also skips
  (rather than fails) if the provider is reachable but blocked at the
  network layer (e.g. an Azure OpenAI resource with public access disabled
  and no working proxy). That's an environment gap, not a code defect.
