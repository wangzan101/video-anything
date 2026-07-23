from scripts.lib.asr_utils import fmt_ts, parse_vtt

def test_fmt_ts_under_hour():
    assert fmt_ts(0) == "00:00"
    assert fmt_ts(65) == "01:05"
    assert fmt_ts(599.9) == "09:59"

def test_fmt_ts_over_hour():
    assert fmt_ts(3661) == "1:01:01"

def test_parse_vtt_basic():
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello\n\n00:01:05.000 --> 00:01:07.000\nworld\nagain\n"
    assert parse_vtt(vtt) == [(1, "Hello"), (65, "world again")]
