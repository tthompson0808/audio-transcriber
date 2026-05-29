"""The summarize_meeting call should send a different system prompt depending
on has_speakers. We verify by intercepting the Anthropic client.
"""
from unittest.mock import MagicMock, patch


@patch("audio_transcriber.claude_api.get_client")
def test_has_speakers_true_uses_named_owners_prompt(mock_get_client):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text='{"title":"x","summary":"","action_items":[],"participants":[],"utterances":[]}')]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg
    mock_get_client.return_value = fake_client

    from audio_transcriber.claude_api import summarize_meeting
    summarize_meeting("Alice: hi\nBob: hi", {"anthropic_api_key": "x"}, has_speakers=True)

    args = fake_client.messages.create.call_args
    system = args.kwargs["system"]
    assert "include named speakers" in system
    assert "real participant name" in system


@patch("audio_transcriber.claude_api.get_client")
def test_has_speakers_false_uses_unattributed_prompt(mock_get_client):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text='{"title":"x","summary":"","action_items":[],"participants":[],"utterances":[]}')]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg
    mock_get_client.return_value = fake_client

    from audio_transcriber.claude_api import summarize_meeting
    summarize_meeting("just a blob of raw whisper text", {"anthropic_api_key": "x"}, has_speakers=False)

    system = fake_client.messages.create.call_args.kwargs["system"]
    assert "DO NOT have named speakers" in system
    assert "(unattributed)" in system
