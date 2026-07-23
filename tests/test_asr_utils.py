from scripts.lib.asr_utils import fmt_ts, parse_vtt, derive_output_dir, is_manual_subtitle, segments_to_markdown, segments_to_text

def test_fmt_ts_under_hour():
    assert fmt_ts(0) == "00:00"
    assert fmt_ts(65) == "01:05"
    assert fmt_ts(599.9) == "09:59"

def test_fmt_ts_over_hour():
    assert fmt_ts(3661) == "1:01:01"

def test_parse_vtt_basic():
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello\n\n00:01:05.000 --> 00:01:07.000\nworld\nagain\n"
    assert parse_vtt(vtt) == [(1, "Hello"), (65, "world again")]

def test_derive_output_dir_sanitizes():
    assert derive_output_dir("douyin", "abc123", "video-out") == "video-out/douyin-abc123"
    assert derive_output_dir("You/Tube", "a b*c", "out") == "out/You_Tube-a_b_c"

def test_is_manual_subtitle():
    assert is_manual_subtitle("sub.zh-Hans.vtt") is True
    assert is_manual_subtitle("sub.en-auto.vtt") is False
    assert is_manual_subtitle("sub.en.auto.vtt") is False

def test_segments_render():
    segs = [(1, "Hello"), (65, "  "), (66, "world")]
    assert segments_to_markdown(segs) == "# Transcript\n\n`[00:01]` Hello\n\n`[01:06]` world\n"
    assert segments_to_text(segs) == "Hello\nworld\n"
