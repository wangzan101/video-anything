from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.support import FakeToolHarness


REPO_ROOT = Path(__file__).resolve().parents[1]
FETCH_SCRIPT = REPO_ROOT / "scripts" / "fetch.sh"


PHASE0_TEST_MATRIX = [
    {"test_id": "test_contract_resolve_failure_returns_20_without_creating_final", "group": "phase2_core", "acceptance": "A1", "removal_phase": "Phase 2"},
    {"test_id": "test_contract_download_failure_returns_30_without_stdout_path", "group": "phase2_core", "acceptance": "A2", "removal_phase": "Phase 2"},
    {"test_id": "test_contract_webm_only_input_requires_real_normalization", "group": "phase2_core", "acceptance": "A3", "removal_phase": "Phase 2"},
    {"test_id": "test_contract_audio_extraction_failure_returns_50_without_publish", "group": "phase2_core", "acceptance": "A4", "removal_phase": "Phase 2"},
    {"test_id": "test_contract_missing_info_json_returns_50", "group": "phase2_core", "acceptance": "A5", "removal_phase": "Phase 2"},
    {"test_id": "test_contract_unparseable_video_returns_50", "group": "phase2_core", "acceptance": "A6", "removal_phase": "Phase 2"},
    {"test_id": "test_contract_audio_duration_tolerance_is_enforced", "group": "phase2_core", "acceptance": "A7", "removal_phase": "Phase 2"},
    {"test_id": "test_contract_video_without_audio_returns_50_no_audio", "group": "phase2_core", "acceptance": "A8", "removal_phase": "Phase 2"},
    {"test_id": "test_contract_valid_final_is_reused_without_redownloading", "group": "phase3_publish", "acceptance": "A9", "removal_phase": "Phase 3"},
    {"test_id": "test_contract_invalid_final_requires_force", "group": "phase3_publish", "acceptance": "A10", "removal_phase": "Phase 3"},
    {"test_id": "test_contract_force_failure_preserves_existing_final", "group": "phase3_publish", "acceptance": "A11", "removal_phase": "Phase 3"},
    {"test_id": "test_contract_force_success_recovers_without_mixed_final_state", "group": "phase3_publish", "acceptance": "A12", "removal_phase": "Phase 3"},
    {"test_id": "test_contract_second_writer_fails_fast_when_lock_is_held", "group": "phase3_publish", "acceptance": "A13", "removal_phase": "Phase 3"},
    {"test_id": "test_contract_download_argv_ignores_host_config", "group": "phase2_core", "acceptance": "A14", "removal_phase": "Phase 2"},
    {"test_id": "test_contract_download_disables_yt_dlp_plugins", "group": "phase2_core", "acceptance": "A15", "removal_phase": "Phase 2"},
    {"test_id": "test_contract_cookie_arguments_are_forwarded_without_leaking_to_outputs", "group": "phase2_core", "acceptance": "A16", "removal_phase": "Phase 2"},
    {"test_id": "test_contract_cookies_from_browser_is_forwarded_without_leaking_to_outputs", "group": "phase2_core", "acceptance": "A16", "removal_phase": "Phase 2"},
    {"test_id": "test_contract_invalid_url_scheme_returns_usage_error", "group": "phase2_core", "acceptance": "A17", "removal_phase": "Phase 2"},
    {"test_id": "test_contract_playlist_inputs_are_rejected_before_download", "group": "phase2_core", "acceptance": "A17", "removal_phase": "Phase 2"},
    {"test_id": "test_contract_live_inputs_are_rejected_before_download", "group": "phase2_core", "acceptance": "A17", "removal_phase": "Phase 2"},
    {"test_id": "test_contract_ambiguous_publish_recovery_state_fails_without_mutation", "group": "phase3_publish", "acceptance": "A23", "removal_phase": "Phase 3"},
    {"test_id": "test_contract_reuse_does_not_rewrite_manifest_or_fetch_log", "group": "phase3_publish", "acceptance": "A24", "removal_phase": "Phase 3"},
]

PHASE0_ACCEPTANCE_NOTES = [
    {"acceptance": "A18", "group": "phase1_capability", "note": "bootstrap/check asset matrix is planned for the capability suite, not the fetch shell contract suite."},
    {"acceptance": "A19", "group": "phase1_capability", "note": "runtime auto|deno|node|none coverage is planned for the capability suite, not the fetch shell contract suite."},
    {"acceptance": "A20", "group": "phase4_ci", "note": "pytest/bash syntax/diff gates are verified by the repo test command, not strict xfail cases."},
    {"acceptance": "A21", "group": "phase5_smoke", "note": "public fixture smoke tests are intentionally excluded from offline pytest."},
    {"acceptance": "A22", "group": "phase6_docs", "note": "documentation support-level checks are intentionally excluded from offline pytest."},
]


def owned_xfail(group: str, acceptance: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(strict=True, reason=f"owned by {group} ({acceptance})")


def run_fetch(
    tmp_path: Path,
    scenario: dict[str, object] | None = None,
    *,
    url: str = "https://example.com/watch?v=abc123",
    output_root_name: str = "video-out",
    extra_env: dict[str, str] | None = None,
    extra_args: list[str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], FakeToolHarness, Path, Path]:
    harness = FakeToolHarness(tmp_path, scenario or {})
    harness.install()
    output_root = tmp_path / output_root_name
    env = harness.build_env(**(extra_env or {}))
    command = ["bash", str(FETCH_SCRIPT), url, str(output_root), *(extra_args or [])]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    artifact_dir = output_root / "fake-abc123"
    return completed, harness, output_root, artifact_dir


def stdout_lines(stdout: str) -> list[str]:
    return [line for line in stdout.splitlines() if line.strip()]


def test_phase0_matrix_has_unique_owned_entries() -> None:
    test_ids = [entry["test_id"] for entry in PHASE0_TEST_MATRIX]
    assert len(test_ids) == len(set(test_ids))


@pytest.mark.phase2_core
def test_contract_resolve_failure_returns_20_without_creating_final(tmp_path: Path) -> None:
    completed, _, _, artifact = run_fetch(tmp_path, {"resolve_exit": 42, "resolve_stdout": ""})
    assert completed.returncode == 20
    assert completed.stdout == ""
    assert not artifact.exists()


@pytest.mark.phase2_core
def test_contract_download_failure_returns_30_without_stdout_path(tmp_path: Path) -> None:
    completed, _, _, artifact = run_fetch(tmp_path, {"download_exit": 42})
    assert completed.returncode == 30
    assert completed.stdout == ""
    assert "done" not in completed.stderr.lower()
    assert not artifact.exists()


@pytest.mark.phase2_core
def test_contract_webm_only_input_requires_real_normalization(tmp_path: Path) -> None:
    completed, _, _, artifact = run_fetch(tmp_path, {"video_ext": "webm"})
    assert completed.returncode == 40
    assert not (artifact / "video.mp4").exists()


@pytest.mark.phase2_core
def test_contract_audio_extraction_failure_returns_50_without_publish(tmp_path: Path) -> None:
    completed, _, _, artifact = run_fetch(tmp_path, {"ffmpeg_exit": 9})
    assert completed.returncode == 50
    assert not artifact.exists()


@pytest.mark.phase2_core
def test_contract_missing_info_json_returns_50(tmp_path: Path) -> None:
    completed, _, _, artifact = run_fetch(tmp_path, {"write_info": False})
    assert completed.returncode == 50
    assert not artifact.exists()


@pytest.mark.phase2_core
def test_contract_invalid_info_json_returns_50(tmp_path: Path) -> None:
    completed, _, _, artifact = run_fetch(tmp_path, {"info_body": "not-json\n"})
    assert completed.returncode == 50
    assert not artifact.exists()


@pytest.mark.phase2_core
def test_contract_unparseable_video_returns_50(tmp_path: Path) -> None:
    completed, _, _, artifact = run_fetch(tmp_path, {"ffprobe_responses": {".mp4": {"exit": 1, "stdout": ""}}})
    assert completed.returncode == 50
    assert not artifact.exists()


@pytest.mark.phase2_core
def test_contract_video_without_video_stream_returns_50(tmp_path: Path) -> None:
    no_video = {"format": {"format_name": "mp4", "duration": "10"}, "streams": []}
    completed, _, _, artifact = run_fetch(
        tmp_path,
        {"ffprobe_responses": {".mp4": {"exit": 0, "stdout": json.dumps(no_video)}}},
    )
    assert completed.returncode == 50
    assert not artifact.exists()


@pytest.mark.phase2_core
def test_contract_audio_duration_tolerance_is_enforced(tmp_path: Path) -> None:
    video = {"format": {"format_name": "mp4", "duration": "100"}, "streams": [{"codec_type": "video", "codec_name": "h264", "duration": "100"}, {"codec_type": "audio", "codec_name": "aac", "duration": "100"}]}
    wav_exact = {"format": {"format_name": "wav", "duration": "101"}, "streams": [{"codec_type": "audio", "codec_name": "pcm_s16le", "sample_rate": "16000", "channels": 1, "duration": "101"}]}
    completed, _, _, artifact = run_fetch(tmp_path / "exact", {"ffprobe_responses": {".mp4": {"stdout": json.dumps(video)}, ".wav": {"stdout": json.dumps(wav_exact)}}})
    assert completed.returncode == 0
    assert (artifact / "manifest.json").exists()
    wav_over = dict(wav_exact)
    wav_over["format"] = {"format_name": "wav", "duration": "101.01"}
    wav_over["streams"] = [dict(wav_exact["streams"][0], duration="101.01")]
    completed, _, _, artifact = run_fetch(tmp_path / "over", {"ffprobe_responses": {".mp4": {"stdout": json.dumps(video)}, ".wav": {"stdout": json.dumps(wav_over)}}})
    assert completed.returncode == 50
    assert not artifact.exists()


@pytest.mark.phase2_core
def test_contract_video_without_audio_returns_50_no_audio(tmp_path: Path) -> None:
    video_only = {"format": {"format_name": "mp4", "duration": "10"}, "streams": [{"codec_type": "video", "codec_name": "h264", "duration": "10"}]}
    completed, _, _, artifact = run_fetch(
        tmp_path,
        {"ffprobe_responses": {".mp4": {"exit": 0, "stdout": json.dumps(video_only)}}},
    )
    assert completed.returncode == 50
    assert "no_audio" in completed.stderr
    assert not artifact.exists()


@owned_xfail("phase3_publish", "A9")
@pytest.mark.phase3_publish
def test_contract_valid_final_is_reused_without_redownloading() -> None:
    pytest.fail("Phase 3 must reuse a validated final without invoking the downloader")


@owned_xfail("phase3_publish", "A10")
@pytest.mark.phase3_publish
def test_contract_invalid_final_requires_force() -> None:
    pytest.fail("Phase 3 must reject an invalid final unless --force is explicit")


@owned_xfail("phase3_publish", "A11")
@pytest.mark.phase3_publish
def test_contract_force_failure_preserves_existing_final() -> None:
    pytest.fail("Phase 3 must preserve the old final when a forced build fails")


@owned_xfail("phase3_publish", "A12")
@pytest.mark.phase3_publish
def test_contract_force_success_recovers_without_mixed_final_state() -> None:
    pytest.fail("Phase 3 must publish a complete new final and clean only owned backups")


@owned_xfail("phase3_publish", "A13")
@pytest.mark.phase3_publish
def test_contract_second_writer_fails_fast_when_lock_is_held() -> None:
    pytest.fail("Phase 3 must fail immediately with artifact_locked when the per-artifact lock exists")


@pytest.mark.phase2_core
def test_contract_download_argv_ignores_host_config(tmp_path: Path) -> None:
    completed, harness, _, _ = run_fetch(tmp_path)
    assert completed.returncode == 0
    assert all("--ignore-config" in call["argv"] for call in harness.calls("yt-dlp"))


@pytest.mark.phase2_core
def test_contract_download_disables_yt_dlp_plugins(tmp_path: Path) -> None:
    completed, harness, _, _ = run_fetch(tmp_path)
    assert completed.returncode == 0
    assert all(call.get("env", {}).get("YTDLP_NO_PLUGINS") == "1" for call in harness.calls("yt-dlp"))


@pytest.mark.phase2_core
def test_contract_cookie_arguments_are_forwarded_without_leaking_to_outputs(tmp_path: Path) -> None:
    cookie = tmp_path / "cookies.txt"
    secret = "session=phase0-secret"
    cookie.write_text(secret, encoding="utf-8")
    completed, harness, _, artifact = run_fetch(tmp_path, extra_env={"VA_COOKIES": str(cookie)})
    assert completed.returncode == 0
    assert any("--cookies" in call["argv"] and str(cookie) in call["argv"] for call in harness.calls("yt-dlp"))
    assert (artifact / "manifest.json").exists()
    assert (artifact / "fetch.log").exists()
    public = b"".join(path.read_bytes() for path in artifact.iterdir() if path.is_file())
    assert secret.encode() not in public


@pytest.mark.phase2_core
def test_contract_cookies_from_browser_is_forwarded_without_leaking_to_outputs(tmp_path: Path) -> None:
    completed, harness, _, artifact = run_fetch(tmp_path, extra_env={"VA_COOKIES_FROM_BROWSER": "chrome:profile-secret"})
    assert completed.returncode == 0
    assert any("--cookies-from-browser" in call["argv"] and "chrome:profile-secret" in call["argv"] for call in harness.calls("yt-dlp"))
    public = b"".join(path.read_bytes() for path in artifact.iterdir() if path.is_file())
    assert b"profile-secret" not in public


@pytest.mark.phase2_core
def test_contract_invalid_url_scheme_returns_usage_error(tmp_path: Path) -> None:
    completed, harness, _, artifact = run_fetch(tmp_path, url="file:///tmp/video")
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert not harness.calls("yt-dlp")
    assert not artifact.exists()


@pytest.mark.phase2_core
def test_contract_playlist_inputs_are_rejected_before_download(tmp_path: Path) -> None:
    metadata = {"_type": "playlist", "extractor": "fake", "id": "playlist", "entries": [{"id": "abc123"}]}
    completed, harness, _, artifact = run_fetch(tmp_path, {"resolve_metadata": metadata})
    assert completed.returncode == 20
    assert not harness.calls("yt-dlp", mode="download")
    assert not artifact.exists()


@pytest.mark.phase2_core
def test_contract_live_inputs_are_rejected_before_download(tmp_path: Path) -> None:
    metadata = {"_type": "video", "extractor": "fake", "id": "abc123", "is_live": True}
    completed, harness, _, artifact = run_fetch(tmp_path, {"resolve_metadata": metadata})
    assert completed.returncode == 20
    assert not harness.calls("yt-dlp", mode="download")
    assert not artifact.exists()


@owned_xfail("phase3_publish", "A23")
@pytest.mark.phase3_publish
def test_contract_ambiguous_publish_recovery_state_fails_without_mutation(tmp_path: Path) -> None:
    pytest.fail("Phase 3 must reject multiple active journals without moving or deleting conflict paths")


@owned_xfail("phase3_publish", "A24")
@pytest.mark.phase3_publish
def test_contract_reuse_does_not_rewrite_manifest_or_fetch_log() -> None:
    pytest.fail("Phase 3 must keep final manifest, fetch.log, inode and mtime immutable on reuse")
