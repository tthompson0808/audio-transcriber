"""VTT + Teams-paste parser smoke tests (no API calls)."""
from audio_transcriber.ingest.vtt_parser import parse_vtt, extract_participants
from audio_transcriber.ingest.teams_paste_parser import parse_teams_paste


VTT_SAMPLE = """WEBVTT

00:00:01.000 --> 00:00:05.000
<v Ian Redd>Hey, can you walk me through the proposal?

00:00:05.500 --> 00:00:09.000
<v Tyler Thompson>Sure — the retainer is sixteen thousand setup plus three a month.
"""


def test_vtt_parses_speakers_and_text():
    utterances = parse_vtt(VTT_SAMPLE)
    assert len(utterances) == 2
    assert utterances[0]["speaker"] == "Ian Redd"
    assert "walk me through" in utterances[0]["text"]
    assert utterances[1]["speaker"] == "Tyler Thompson"
    participants = extract_participants(utterances)
    assert set(participants) == {"Ian Redd", "Tyler Thompson"}


TEAMS_PASTE_SAMPLE = """TT
Tyler Thompson
Tyler Thompson 0 minutes 5 seconds
Hey Ian, thanks for jumping on.

IR
Ian Redd
Ian Redd 0 minutes 8 seconds
Of course. Let's dive in.

Tyler Thompson 1 hour 3 minutes 20 seconds
So that's the deal — sixteen K plus three.
"""


def test_teams_paste_parses_initials_and_timestamps():
    utterances = parse_teams_paste(TEAMS_PASTE_SAMPLE)
    assert len(utterances) >= 2
    speakers = {u["speaker"] for u in utterances}
    assert "Tyler Thompson" in speakers
    assert "Ian Redd" in speakers
    # The hours-timestamp should parse correctly
    assert any(u["start"] == "01:03:20" for u in utterances)
