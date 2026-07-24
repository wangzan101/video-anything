"""Pure host and JavaScript-runtime capability decisions for download setup."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass


class CapabilityError(ValueError):
    """Raised when a requested host/runtime is outside the v1 contract."""


@dataclass(frozen=True)
class HostCapabilities:
    os_name: str
    arch: str
    libc: str | None
    yt_dlp_asset: str
    deno_asset: str
    supported: bool = True


def host_capabilities(os_name: str, arch: str, libc: str | None = None) -> HostCapabilities:
    """Return the v1 release assets, rejecting unsupported hosts before network use."""

    normalized_os = os_name.strip()
    normalized_arch = arch.strip().lower()
    normalized_libc = libc.lower() if libc else None
    if normalized_os == "Darwin":
        if normalized_arch not in {"x86_64", "amd64", "arm64", "aarch64"}:
            raise CapabilityError("unsupported_host")
        canonical_arch = "arm64" if normalized_arch in {"arm64", "aarch64"} else "x86_64"
        return HostCapabilities(
            normalized_os,
            canonical_arch,
            None,
            "yt-dlp_macos",
            f"deno-{('aarch64' if canonical_arch == 'arm64' else 'x86_64')}-apple-darwin.zip",
        )
    if normalized_os != "Linux":
        raise CapabilityError("unsupported_host")
    if normalized_libc != "glibc":
        raise CapabilityError("unsupported_host")
    if normalized_arch in {"x86_64", "amd64"}:
        return HostCapabilities(
            normalized_os,
            "x86_64",
            normalized_libc,
            "yt-dlp_linux",
            "deno-x86_64-unknown-linux-gnu.zip",
        )
    if normalized_arch in {"aarch64", "arm64"}:
        return HostCapabilities(
            normalized_os,
            "aarch64",
            normalized_libc,
            "yt-dlp_linux_aarch64",
            "deno-aarch64-unknown-linux-gnu.zip",
        )
    raise CapabilityError("unsupported_host")


def parse_version(value: str) -> tuple[int, ...]:
    match = re.search(r"\d+(?:\.\d+)+", value)
    if not match:
        raise CapabilityError("invalid_runtime_version")
    return tuple(int(part) for part in match.group(0).split("."))


def version_at_least(value: str, minimum: tuple[int, ...]) -> bool:
    parsed = parse_version(value)
    padded = parsed + (0,) * (len(minimum) - len(parsed))
    return padded[: len(minimum)] >= minimum


def choose_js_runtime(
    choice: str,
    *,
    deno_path: str | None = None,
    deno_version: str | None = None,
    node_path: str | None = None,
    node_version: str | None = None,
) -> dict[str, str | None]:
    """Validate the explicit runtime policy and return an argv-ready selection."""

    if choice not in {"auto", "deno", "node", "none"}:
        raise CapabilityError("invalid_js_runtime")
    if choice == "none":
        return {"runtime": "none", "path": None}
    if choice in {"auto", "deno"}:
        if deno_path and deno_version and version_at_least(deno_version, (2, 3, 0)):
            return {"runtime": "deno", "path": deno_path}
        if choice == "deno":
            raise CapabilityError("deno_unavailable")
        # auto is intentionally not allowed to silently fall back to Node.
        raise CapabilityError("deno_bootstrap_required")
    if not node_path or not node_version or not version_at_least(node_version, (22, 0, 0)):
        raise CapabilityError("node_unavailable")
    return {"runtime": "node", "path": node_path}


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--os", dest="os_name", required=True)
    parser.add_argument("--arch", required=True)
    parser.add_argument("--libc")
    args = parser.parse_args()
    try:
        print(json.dumps(asdict(host_capabilities(args.os_name, args.arch, args.libc))))
    except CapabilityError as exc:
        print(json.dumps({"error": str(exc)}))
        return 10
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
