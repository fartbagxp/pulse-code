# LLM Providers

The `build`, `query`, `refine`, `compare`, and `chat` commands call an LLM. `pulse` defaults to Anthropic Claude and can also run against an Azure OpenAI Foundry deployment (e.g. GPT-5.4). Select the provider with `LLM_PROVIDER` (defaults to `anthropic`). All of these variables can live in the environment or in a `.env` file.

## Anthropic (default)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# or put it in a .env file:
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

## Azure OpenAI

```bash
export LLM_PROVIDER=azure_openai
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com
export AZURE_OPENAI_DEPLOYMENT=<your-gpt-5.4-deployment-name>
export AZURE_OPENAI_API_VERSION=<api-version-your-resource-supports>
```

All four `AZURE_OPENAI_*` variables are required when `LLM_PROVIDER=azure_openai`; `pulse` tells you which ones are missing.

## Proxying

If the LLM endpoint isn't directly reachable (for example an Azure OpenAI resource with public network access disabled, requiring a private endpoint), bridge the connection through a proxy with `LLM_HTTP_PROXY`. It applies to both providers and supports `http://`, `https://`, `socks5://`, and `socks5h://` (DNS resolved through the proxy):

```bash
export LLM_HTTP_PROXY=socks5h://user:pass@host:port
```

The SOCKS proxy path has an end-to-end integration test that runs without real credentials; see [testing.md](testing.md).
