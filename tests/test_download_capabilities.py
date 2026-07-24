from __future__ import annotations

import pytest

from scripts.lib.capabilities import CapabilityError, choose_js_runtime, host_capabilities


@pytest.mark.phase1_capability
@pytest.mark.parametrize(
    ("os_name", "arch", "libc", "yt_asset", "deno_asset"),
    [
        ("Darwin", "x86_64", None, "yt-dlp_macos", "deno-x86_64-apple-darwin.zip"),
        ("Darwin", "arm64", None, "yt-dlp_macos", "deno-aarch64-apple-darwin.zip"),
        ("Linux", "x86_64", "glibc", "yt-dlp_linux", "deno-x86_64-unknown-linux-gnu.zip"),
        ("Linux", "aarch64", "glibc", "yt-dlp_linux_aarch64", "deno-aarch64-unknown-linux-gnu.zip"),
    ],
)
def test_supported_host_asset_matrix(os_name: str, arch: str, libc: str | None, yt_asset: str, deno_asset: str) -> None:
    capabilities = host_capabilities(os_name, arch, libc)
    assert capabilities.yt_dlp_asset == yt_asset
    assert capabilities.deno_asset == deno_asset


@pytest.mark.phase1_capability
@pytest.mark.parametrize(
    ("os_name", "arch", "libc"),
    [("Linux", "x86_64", "musl"), ("Linux", "armv7l", "glibc"), ("Windows", "x86_64", None), ("Linux", "riscv64", "glibc")],
)
def test_unsupported_hosts_fail_before_asset_selection(os_name: str, arch: str, libc: str | None) -> None:
    with pytest.raises(CapabilityError, match="unsupported_host"):
        host_capabilities(os_name, arch, libc)


@pytest.mark.phase1_capability
@pytest.mark.parametrize(
    ("choice", "deno_version", "node_version", "expected"),
    [("auto", "2.3.0", None, "deno"), ("deno", "2.8.1", None, "deno"), ("node", None, "22.0.0", "node"), ("none", None, None, "none")],
)
def test_js_runtime_policy_requires_explicit_valid_runtime(choice: str, deno_version: str | None, node_version: str | None, expected: str) -> None:
    result = choose_js_runtime(
        choice,
        deno_path="/controlled/deno" if deno_version else None,
        deno_version=deno_version,
        node_path="/system/node" if node_version else None,
        node_version=node_version,
    )
    assert result["runtime"] == expected


@pytest.mark.phase1_capability
@pytest.mark.parametrize(
    ("choice", "deno_version", "node_version", "error"),
    [("invalid", None, None, "invalid_js_runtime"), ("deno", "2.2.9", None, "deno_unavailable"), ("node", None, "21.9.0", "node_unavailable")],
)
def test_js_runtime_policy_rejects_invalid_or_old_runtime(choice: str, deno_version: str | None, node_version: str | None, error: str) -> None:
    with pytest.raises(CapabilityError, match=error):
        choose_js_runtime(
            choice,
            deno_path="/controlled/deno" if deno_version else None,
            deno_version=deno_version,
            node_path="/system/node" if node_version else None,
            node_version=node_version,
        )
