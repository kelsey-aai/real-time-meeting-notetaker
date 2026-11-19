"""Offline checks: no API key or network needed. Run with `python -m pytest`."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from assemblyai.streaming.v3 import RealTimeParameters, TurnEvent  # noqa: E402

from meeting_notes import NOTES_SCHEMA, notes_to_markdown  # noqa: E402
from transcript import MeetingTranscript, Turn, parse_speaker_names  # noqa: E402


def test_parse_speaker_names():
    assert parse_speaker_names("A=Priya, b=Marcus,bad") == {"A": "Priya", "B": "Marcus"}
    assert parse_speaker_names(None) == {}


def test_transcript_lines_and_pending():
    m = MeetingTranscript(speaker_names={"A": "Priya"})
    m.add(Turn(0, "A", "Let's lock the launch date.", 1200))
    m.add(Turn(1, "PENDING", "Yeah.", 65000))
    m.add(Turn(2, "B", "I'll send the draft by Friday.", 66500))
    m.add(Turn(3, "B", "   ", None))  # empty turns are dropped
    assert m.as_text().splitlines() == [
        "[00:01] Priya: Let's lock the launch date.",
        "[01:05] Unattributed: Yeah.",
        "[01:06] Speaker B: I'll send the draft by Friday.",
    ]
    assert m.speakers() == ["Priya", "Speaker B"]
    assert m.word_count() == 12


def test_turn_event_parses_documented_payload():
    # Shape from /docs/streaming/label-speakers-and-separate-channels
    event = TurnEvent.model_validate(
        {
            "type": "Turn",
            "turn_order": 0,
            "turn_is_formatted": True,
            "end_of_turn": True,
            "transcript": "Good morning, thanks for joining the call.",
            "end_of_turn_confidence": 0.9,
            "speaker_label": "A",
            "words": [
                {"text": "Good", "speaker": "A", "word_is_final": True,
                 "start": 120, "end": 280, "confidence": 0.99},
            ],
        }
    )
    assert event.speaker_label == "A"
    assert event.words[0].start == 120


def test_connection_params():
    p = RealTimeParameters(
        sample_rate=16000,
        speech_model="assemblyai-stt-3-7-realtime",
        speaker_labels=True,
        max_speakers=6,
        keyterms_prompt=["Priya", "Kubernetes"],
    )
    assert p.speech_model.value == "assemblyai-stt-3-7-realtime"
    assert p.speaker_labels is True


def test_notes_markdown():
    notes = {
        "summary": "The team agreed on a launch date.",
        "decisions": ["Launch on March 3"],
        "action_items": [
            {"owner": "Speaker B", "task": "Send the draft", "due": "Friday", "timestamp": "01:06"}
        ],
        "open_questions": [],
    }
    md = notes_to_markdown(notes)
    assert "- [ ] **Speaker B**: Send the draft (due Friday) [01:06]" in md
    assert "- None" in md
    assert set(NOTES_SCHEMA["required"]) == set(notes)
