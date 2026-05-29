from audio_transcriber.capture.exclusion import should_record, title_excluded, attendee_excluded


def test_title_pattern_blocks_board_meeting(tmp_cfg):
    excluded, reason = title_excluded("Q3 Board Sync", tmp_cfg)
    assert excluded
    assert "board" in reason.lower()


def test_title_pattern_allows_normal(tmp_cfg):
    excluded, _ = title_excluded("Buildertrend Demo", tmp_cfg)
    assert not excluded


def test_attendee_blocklist_matches_domain(tmp_cfg):
    excluded, reason = attendee_excluded(["partner@legalcounsel.com"], tmp_cfg)
    assert excluded
    assert "legalcounsel" in reason.lower()


def test_attendee_blocklist_allows_other_domains(tmp_cfg):
    excluded, _ = attendee_excluded(["client@buildertrend.com"], tmp_cfg)
    assert not excluded


def test_should_record_combined(tmp_cfg):
    allowed, msg = should_record("Buildertrend Demo", ["client@buildertrend.com"], tmp_cfg)
    assert allowed and msg == "ok"

    allowed, msg = should_record("Board Strategy", [], tmp_cfg)
    assert not allowed and "exclusion" in msg

    allowed, msg = should_record("Normal Sync", ["x@legalcounsel.com"], tmp_cfg)
    assert not allowed and "blocklist" in msg
