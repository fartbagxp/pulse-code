from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.integration._servers import MockLLMServer, SocksProxyServer


@pytest.fixture()
def socks_proxy() -> Iterator[SocksProxyServer]:
    server = SocksProxyServer()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture()
def mock_llm_server() -> Iterator[MockLLMServer]:
    server = MockLLMServer()
    try:
        yield server
    finally:
        server.stop()
