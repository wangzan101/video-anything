from scripts.lib.asr_utils import fmt_ts

def test_fmt_ts_under_hour():
    assert fmt_ts(0) == "00:00"
    assert fmt_ts(65) == "01:05"
    assert fmt_ts(599.9) == "09:59"

def test_fmt_ts_over_hour():
    assert fmt_ts(3661) == "1:01:01"
