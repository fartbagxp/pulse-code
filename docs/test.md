# Testing

```bash
uv run pytest                  # unit tests only, fast, no network (default)
uv run pytest -m integration   # integration tests only
```

## Unit Tests

The unit suite is 126 tests and finishes in about 4 seconds without touching the network. It covers catalog and matcher lookups, XML template merging (including a regression test for the CDC WONDER radio-button trap), AAR constraints, provider selection, and every CLI command that works offline, with one file per source under `tests/unit/`.

## Integration Tests

The integration tests live in `tests/integration/`. A bare `uv run pytest` skips all 3 of them, because `addopts` in `pyproject.toml` carries `-m "not integration"`. The two files behave differently.

`test_socks_proxy_integration.py` always runs. It spins up a local SOCKS5 relay and a local mock LLM HTTP server, so it exercises `LLM_HTTP_PROXY` for real (an actual SOCKS handshake and an actual HTTP request and response) without needing Azure or Anthropic credentials.

`test_llm_provider_live.py` hits whatever you have configured: `ANTHROPIC_API_KEY`, or `LLM_PROVIDER=azure_openai` plus the `AZURE_OPENAI_*` variables, plus `LLM_HTTP_PROXY` if you use one. It skips when credentials aren't set. It also skips, rather than fails, when the provider is reachable but blocked at the network layer, for example an Azure OpenAI resource with public access disabled and no working proxy. That's a gap in the environment, not a defect in the code.

## Previewing the Site Locally

`site/dist/` is generated and gitignored, so build it before serving:

```bash
uv run python site/generate.py
uv run python -m http.server 8080 --bind 0.0.0.0 --directory site/dist
```

That binds to every interface, so the site is reachable at `http://<this-machine-ip>:8080/` from anywhere on the network, and at `http://localhost:8080/` on the machine itself. Any free port works. `http.server` reads from disk on each request, so after re-running the generator a browser refresh picks up the new output without restarting the server.

Which URL you use changes what you are testing. The copy buttons prefer `navigator.clipboard`, which browsers only expose in a secure context. `localhost` counts as secure even over plain HTTP, but a LAN IP does not, so visiting by IP exercises the `textarea` and `execCommand` fallback instead. Either way the command should land on the clipboard and the button's icon should turn into a green checkmark for a moment. Check both paths if you have touched that code.

The generator writes `index.html`, `usage.html`, `wonder.html`, and one page per bundled query under `examples/`. It is pure stdlib and imports nothing from `pulse`, which is what lets the Pages workflow run it on a bare Python with no dependencies installed.
