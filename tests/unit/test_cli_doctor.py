"""Unit tests for `pulse doctor` — monkeypatches the network check, no live calls here."""

from __future__ import annotations

from typer.testing import CliRunner

import pulse.cli as cli
from pulse.cli import app

runner = CliRunner()


def test_doctor_all_reachable_exits_zero(monkeypatch):
    monkeypatch.setattr(cli, "_check_url", lambda url, timeout=8.0: (True, "HTTP 200  10ms"))
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "All sources reachable" in result.stdout


def test_doctor_unreachable_source_exits_nonzero(monkeypatch):
    def fake_check(url, timeout=8.0):
        if "nis" in url.lower():
            return False, "HTTP 404  10ms"
        return True, "HTTP 200  10ms"

    monkeypatch.setattr(cli, "_check_url", fake_check)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "unreachable" in result.stdout.lower()


def test_doctor_reports_missing_anthropic_key(monkeypatch):
    monkeypatch.setattr(cli, "_check_url", lambda url, timeout=8.0: (True, "HTTP 200  10ms"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    result = runner.invoke(app, ["doctor"])
    assert "WARN" in result.stdout
    assert "not set" in result.stdout


def test_doctor_reports_set_anthropic_key(monkeypatch):
    monkeypatch.setattr(cli, "_check_url", lambda url, timeout=8.0: (True, "HTTP 200  10ms"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    result = runner.invoke(app, ["doctor"])
    assert "ANTHROPIC_API_KEY set" in result.stdout
