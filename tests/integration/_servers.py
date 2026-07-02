"""Minimal local SOCKS5 relay + mock Azure-OpenAI-compatible HTTP server,
used to exercise the LLM_HTTP_PROXY code path end-to-end without needing
real external credentials or a real proxy.

Not a general-purpose SOCKS implementation — just enough of RFC 1928 (no
auth, IPv4/hostname CONNECT) to prove requests actually traverse a proxy.
"""

from __future__ import annotations

import http.server
import json
import socket
import struct
import threading
from dataclasses import dataclass, field


@dataclass
class SocksProxyServer:
    """A local SOCKS5 proxy. `connections` records every (host, port) it
    was asked to CONNECT to, so tests can assert traffic actually routed
    through it rather than going direct."""

    connections: list[tuple[str, int]] = field(default_factory=list)
    _listener: socket.socket = field(init=False, repr=False)
    _thread: threading.Thread = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(8)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        return self._listener.getsockname()[1]

    @property
    def url(self) -> str:
        return f"socks5h://127.0.0.1:{self.port}"

    def _serve(self) -> None:
        while True:
            try:
                client, _ = self._listener.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(client,), daemon=True).start()

    def _handle(self, client: socket.socket) -> None:
        try:
            _ver, nmethods = client.recv(2)
            client.recv(nmethods)
            client.sendall(bytes([5, 0]))  # no-auth accepted

            header = client.recv(4)
            _ver, _cmd, _rsv, atyp = header
            if atyp == 1:  # IPv4
                addr = socket.inet_ntoa(client.recv(4))
            elif atyp == 3:  # domain name
                length = client.recv(1)[0]
                addr = client.recv(length).decode()
            else:
                client.close()
                return
            port = struct.unpack(">H", client.recv(2))[0]
            self.connections.append((addr, port))

            target = socket.create_connection((addr, port))
            client.sendall(bytes([5, 0, 0, 1, 0, 0, 0, 0, 0, 0]))
            t1 = threading.Thread(target=_pipe, args=(client, target), daemon=True)
            t2 = threading.Thread(target=_pipe, args=(target, client), daemon=True)
            t1.start()
            t2.start()
        except OSError:
            client.close()

    def stop(self) -> None:
        self._listener.close()


def _pipe(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass


@dataclass
class MockLLMServer:
    """A local HTTP server that speaks just enough of the OpenAI/Azure
    chat-completions response shape to drive AzureOpenAIQueryBuilder,
    always returning a canned `build_wonder_query` tool call."""

    tool_name: str = "build_wonder_query"
    tool_arguments: dict = field(
        default_factory=lambda: {
            "dataset_id": "D202",
            "parameters": [{"name": "B_1", "values": ["D202.V20"]}],
        }
    )
    request_count: int = field(default=0)
    _server: http.server.HTTPServer = field(init=False, repr=False)
    _thread: threading.Thread = field(init=False, repr=False)

    def __post_init__(self) -> None:
        mock = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                mock.request_count += 1
                length = int(self.headers.get("Content-Length", 0))
                self.rfile.read(length)
                body = json.dumps(
                    {
                        "id": "chatcmpl-test",
                        "object": "chat.completion",
                        "created": 0,
                        "model": "mock",
                        "choices": [
                            {
                                "index": 0,
                                "finish_reason": "tool_calls",
                                "message": {
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": [
                                        {
                                            "id": "call_1",
                                            "type": "function",
                                            "function": {
                                                "name": mock.tool_name,
                                                "arguments": json.dumps(
                                                    mock.tool_arguments
                                                ),
                                            },
                                        }
                                    ],
                                },
                            }
                        ],
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:  # silence default logging
                pass

        self._server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        return self._server.server_port

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
