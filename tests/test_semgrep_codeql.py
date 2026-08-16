"""Real tests for the Semgrep and CodeQL tool support added to close the gap
where SecuraIQ described SonarQube/Semgrep/CodeQL-class coverage but had zero
registry entries or dispatch code for Semgrep or CodeQL.

Semgrep is pip-installable, so `_tool_semgrep` genuinely shells out to the
real `semgrep` binary via subprocess when present on PATH and parses its
JSON output through the existing `parse_semgrep` adapter. These tests mock
only the subprocess boundary (PATH resolution + process I/O) so the suite
stays fast/deterministic without requiring semgrep actually installed, while
still exercising the real JSON-parsing and result-shaping logic.

CodeQL requires a per-language database build before it can analyze
anything, so there is no single safe generic invocation for an arbitrary
target — `_tool_codeql` honestly reports CLI presence and next steps instead
of faking a scan. Real CodeQL coverage of SecuraIQ's own repo runs via the
`codeql` GitHub Actions job (github/codeql-action) added to
.github/workflows/security-scan.yml.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.scanner_adapters import parse_semgrep
from app.tools.registry import TOOL_CATALOG
import app.tools.runner as runner_mod
from app.tools.runner import _tool_codeql, _tool_semgrep


# --- catalog wiring ----------------------------------------------------------


def test_semgrep_and_codeql_are_registered():
    assert "semgrep" in TOOL_CATALOG
    assert "codeql" in TOOL_CATALOG
    assert TOOL_CATALOG["semgrep"].kind == "external"
    assert TOOL_CATALOG["semgrep"].binaries == ("semgrep",)
    assert TOOL_CATALOG["codeql"].kind == "external"
    assert TOOL_CATALOG["codeql"].binaries == ("codeql",)
    # Both are path/CLI-based, not network-target based.
    assert TOOL_CATALOG["semgrep"].needs_target is False
    assert TOOL_CATALOG["codeql"].needs_target is False


def test_semgrep_and_codeql_are_path_tools_not_dns_resolved():
    # Mirrors code_scan/securaiq_code — these must never be resolved as
    # hostnames when Target is actually a local folder path.
    import inspect

    src = inspect.getsource(runner_mod.iter_security_tools)
    assert '"semgrep"' in src
    assert '"codeql"' in src


# --- _tool_semgrep: input validation ----------------------------------------


def test_semgrep_requires_a_path():
    result = asyncio.run(_tool_semgrep("", authorized=True))
    assert result["ok"] is False
    assert "path" in (result.get("error") or "").lower()


def test_semgrep_requires_authorization(tmp_path):
    result = asyncio.run(_tool_semgrep(str(tmp_path), authorized=False))
    assert result["ok"] is False
    assert "auth" in (result.get("error") or "").lower() or "Auth" in result["output"]


def test_semgrep_rejects_nonexistent_path():
    result = asyncio.run(_tool_semgrep("/definitely/does/not/exist/anywhere", authorized=True))
    assert result["ok"] is False
    assert "not found" in (result.get("error") or "").lower()


# --- _tool_semgrep: honest "not installed" path -----------------------------


def test_semgrep_not_installed_gives_honest_guidance_not_a_fake_result(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod.shutil, "which", lambda name: None)
    result = asyncio.run(_tool_semgrep(str(tmp_path), authorized=True))
    assert result["ok"] is False
    assert "not installed" in result["error"].lower()
    assert "pip install semgrep" in result["output"]
    assert "code_scan" in result["output"]  # points to the zero-install fallback
    # Must not claim any scan actually ran.
    assert "semgrep_results" not in result


# --- _tool_semgrep: real binary invocation (subprocess boundary mocked) ----


def test_semgrep_invocation_parses_real_json_shape(tmp_path, monkeypatch):
    """Mocks only shutil.which + create_subprocess_exec — everything else
    (JSON parsing, finding-line formatting, result shape) is the real code
    path that also feeds vulnerability persistence."""
    monkeypatch.setattr(runner_mod.shutil, "which", lambda name: "/usr/local/bin/semgrep")

    fake_semgrep_json = {
        "results": [
            {
                "check_id": "python.lang.security.audit.eval-detected",
                "path": "app.py",
                "start": {"line": 3},
                "extra": {
                    "message": "Detected eval() usage",
                    "severity": "ERROR",
                    "metadata": {"cwe": "CWE-95"},
                },
            }
        ],
        "errors": [],
        "paths": {"scanned": ["app.py", "utils.py"]},
    }
    stdout_bytes = json.dumps(fake_semgrep_json).encode("utf-8")

    class _FakeProc:
        returncode = 0

        async def communicate(self):
            return stdout_bytes, b""

    async def _fake_create_subprocess_exec(*args, **kwargs):
        return _FakeProc()

    monkeypatch.setattr(runner_mod.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    result = asyncio.run(_tool_semgrep(str(tmp_path), authorized=True))
    assert result["ok"] is True
    assert result["files_scanned"] == 2
    assert len(result["semgrep_results"]) == 1
    assert "eval-detected" in result["output"]

    # The persistence branch in runner.py (`elif tid == "semgrep":`) feeds
    # semgrep_results straight into the existing scanner_adapters parser —
    # confirm that shape is exactly what create_vulnerability expects.
    items = parse_semgrep(result["semgrep_results"], engagement_id=None, filename=str(tmp_path))
    assert len(items) == 1
    assert items[0]["severity"] in {"critical", "high", "medium", "low", "info"}
    assert "eval" in items[0]["title"].lower()
    assert items[0]["source"].startswith("semgrep:")


def test_semgrep_handles_unparseable_output_without_crashing(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod.shutil, "which", lambda name: "/usr/local/bin/semgrep")

    class _FakeProc:
        returncode = 2

        async def communicate(self):
            return b"not json at all", b"some stderr noise"

    async def _fake_create_subprocess_exec(*args, **kwargs):
        return _FakeProc()

    monkeypatch.setattr(runner_mod.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    result = asyncio.run(_tool_semgrep(str(tmp_path), authorized=True))
    assert result["ok"] is False
    assert "parse" in result["error"].lower()


def test_semgrep_treats_empty_stdout_as_a_real_failure_not_a_clean_scan(tmp_path, monkeypatch):
    """Real bug found via live testing: semgrep can exit non-zero with EMPTY
    stdout (e.g. its rule-registry fetch is blocked by a proxy/firewall)
    while writing the real error to stderr. The old code did
    `json.loads(raw_text) if raw_text.strip() else {}`, which silently turned
    that crash into `{}` -> 0 results -> a *reported* clean scan. That is
    exactly the "fake success" this product is supposed to never produce."""
    monkeypatch.setattr(runner_mod.shutil, "which", lambda name: "/usr/local/bin/semgrep")

    class _FakeProc:
        returncode = 2

        async def communicate(self):
            return b"", b"requests.exceptions.ProxyError: ... 403 Forbidden"

    async def _fake_create_subprocess_exec(*args, **kwargs):
        return _FakeProc()

    monkeypatch.setattr(runner_mod.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    result = asyncio.run(_tool_semgrep(str(tmp_path), authorized=True))
    assert result["ok"] is False
    assert "no output" in result["error"].lower()
    assert "2" in result["error"]  # surfaces the real exit code
    assert "403" in result["output"] or "ProxyError" in result["output"]
    # Must never be reported as a 0-finding clean scan.
    assert "semgrep_results" not in result


# --- _tool_codeql: honest, no fake scan -------------------------------------


def test_codeql_reports_cli_not_found_without_faking_a_scan(monkeypatch):
    monkeypatch.setattr(runner_mod.shutil, "which", lambda name: None)
    result = asyncio.run(_tool_codeql())
    assert result["ok"] is False
    assert "not installed" in result["error"].lower()
    assert "codeql-action" in result["output"] or "github.com/github/codeql-action" in result["output"]
    # Must point to the real CI coverage rather than pretending to scan.
    assert "security-scan.yml" in result["output"]


def test_codeql_reports_cli_found_with_real_next_steps(monkeypatch):
    monkeypatch.setattr(runner_mod.shutil, "which", lambda name: "/usr/local/bin/codeql")
    result = asyncio.run(_tool_codeql())
    assert result["ok"] is True
    assert "database create" in result["output"]
    assert "database analyze" in result["output"]
    # No fabricated finding counts — this call never ran an actual analysis.
    assert "results" not in result
