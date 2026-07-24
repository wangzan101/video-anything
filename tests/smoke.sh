#!/usr/bin/env bash
# Opt-in platform smoke runner. It never supplies URLs or cookies by default.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
platform=""
url=""
output_root="${VA_SMOKE_OUTPUT_ROOT:-$(mktemp -d "${TMPDIR:-/tmp}/video-anything-smoke.XXXXXX")}"

usage() { echo "usage: bash tests/smoke.sh --platform <youtube|bilibili|twitter|douyin|kuaishou> --url <public-url> [--output-root <dir>]" >&2; }

while [ "$#" -gt 0 ]; do
  case "$1" in
    --platform) platform="${2:-}"; shift 2 ;;
    --url) url="${2:-}"; shift 2 ;;
    --output-root) output_root="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

case "$platform" in youtube|bilibili|twitter|douyin|kuaishou) ;; *) echo "ERROR: unsupported smoke platform" >&2; exit 2 ;; esac
if [ -z "$url" ]; then echo "ERROR: --url is required; no fixture is embedded in the repository" >&2; exit 2; fi
case "$url" in http://*|https://*) ;; *) echo "ERROR: smoke URL must use http:// or https://" >&2; exit 2 ;; esac

mkdir -p "$output_root"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
set +e
stdout_file="$output_root/stdout.txt"
stderr_file="$output_root/stderr.txt"
bash "$REPO_ROOT/scripts/fetch.sh" "$url" "$output_root/artifacts" >"$stdout_file" 2>"$stderr_file"
code=$?
set -e

artifact="$(tail -n 1 "$stdout_file" 2>/dev/null || true)"
status="failed"
classification="project_regression"
if [ "$code" -eq 0 ] && [ -n "$artifact" ] && [ -f "$artifact/manifest.json" ]; then
  status="ready"; classification="ready"
elif grep -Eqi 'cookie|login|sign in|forbidden|403|429|captcha|bot' "$stderr_file"; then
  classification="auth_or_antibot"
elif grep -Eqi 'unsupported|extractor|no suitable|not available' "$stderr_file"; then
  classification="upstream_extractor"
elif grep -Eqi '404|410|removed|unavailable' "$stderr_file"; then
  classification="link_rot"
fi

python3 - "$output_root/smoke-report.json" "$platform" "$url" "$started_at" "$code" "$status" "$classification" "$artifact" <<'PY'
import hashlib, json, pathlib, sys
report_path, platform, url, started_at, code, status, classification, artifact = sys.argv[1:]
report = {"platform": platform, "fixture_url_sha256": hashlib.sha256(url.encode()).hexdigest(), "url_redacted": url.split('?', 1)[0], "started_at": started_at, "exit_code": int(code), "status": status, "classification": classification, "artifact": artifact or None}
pathlib.Path(report_path).write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(report, sort_keys=True))
PY

exit "$code"
