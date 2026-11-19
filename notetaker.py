"""Live meeting notetaker: speaker-labeled transcript during the call, notes when it ends.

Usage:
  python notetaker.py --file meeting.wav
  python notetaker.py --mic --max-speakers 6 --speakers "A=Priya,B=Marcus"
"""

import argparse
import json
import os
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv

from assemblyai.streaming.v3 import (
    BeginEvent,
    RealTimeError,
    RealTimeEvents,
    RealTimeParameters,
    RealTimeTranscriber,
    RealTimeTranscriberOptions,
    TerminationEvent,
    TurnEvent,
)

from audio_sources import open_microphone, open_wav
from meeting_notes import notes_to_markdown, write_notes
from transcript import MeetingTranscript, Turn, parse_speaker_names

# Published pay-as-you-go rates (assemblyai.com/pricing). Streaming bills on session time.
STT_RATE_PER_HOUR = 0.30          # AssemblyAI-STT-3.7-Realtime
DIARIZATION_RATE_PER_HOUR = 0.12  # streaming speaker diarization add-on


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="mono 16-bit PCM WAV, streamed at live speed")
    src.add_argument("--mic", action="store_true", help="stream from the default microphone (Ctrl+C to end)")
    p.add_argument("--max-speakers", type=int, help="hard cap on speaker labels, 1-10")
    p.add_argument("--speakers", help='map labels to names, e.g. "A=Priya,B=Marcus"')
    p.add_argument("--keyterms", help='comma-separated names/terms, e.g. "Priya,Kubernetes,Q3 roadmap"')
    p.add_argument("--model", default=os.getenv("LLM_MODEL", "claude-sonnet-5-5"), help="LLM Gateway model")
    p.add_argument("--out", default="output", help="folder for transcript.md and notes.md")
    return p.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        print("Set ASSEMBLYAI_API_KEY in your environment or .env file.", file=sys.stderr)
        return 1

    if args.file:
        sample_rate, audio = open_wav(args.file)
    else:
        sample_rate = 16000
        audio = open_microphone(sample_rate)

    meeting = MeetingTranscript(speaker_names=parse_speaker_names(args.speakers))
    session = {"seconds": 0.0}
    errors = []
    done = threading.Event()

    def on_begin(client: RealTimeTranscriber, event: BeginEvent) -> None:
        print(f"Session {event.id} started. Listening...\n")

    def on_turn(client: RealTimeTranscriber, event: TurnEvent) -> None:
        if not event.end_of_turn:
            return  # partials arrive about once a second; a UI would render them in place
        start = event.words[0].start if event.words else None
        turn = Turn(
            turn_order=event.turn_order,
            speaker=event.speaker_label or "PENDING",
            text=event.transcript,
            start_ms=start,
        )
        meeting.add(turn)  # final at turn end: no revision pass to wait for
        print(meeting.line(turn), flush=True)

    def on_terminated(client: RealTimeTranscriber, event: TerminationEvent) -> None:
        session["seconds"] = event.session_duration_seconds or 0.0
        done.set()

    def on_error(client: RealTimeTranscriber, error: RealTimeError) -> None:
        errors.append(error)
        print(f"Streaming error: {error}", file=sys.stderr)

    client = RealTimeTranscriber(
        RealTimeTranscriberOptions(terminate_timeout=30.0),
        api_key=api_key,
    )
    client.on(RealTimeEvents.Begin, on_begin)
    client.on(RealTimeEvents.Turn, on_turn)
    client.on(RealTimeEvents.Termination, on_terminated)
    client.on(RealTimeEvents.Error, on_error)

    params = RealTimeParameters(
        sample_rate=sample_rate,
        speech_model="assemblyai-stt-3-7-realtime",
        speaker_labels=True,
    )
    if args.max_speakers:
        params.max_speakers = args.max_speakers
    if args.keyterms:
        params.keyterms_prompt = [t.strip() for t in args.keyterms.split(",") if t.strip()]

    client.connect(params)
    try:
        client.stream(audio)
    except KeyboardInterrupt:
        print("\nEnding the session...")
    finally:
        client.disconnect(terminate=True)  # stops billing; waits for Termination
    done.wait(timeout=5)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    transcript_text = meeting.as_text()
    (out / "transcript.md").write_text(transcript_text + "\n")

    hours = session["seconds"] / 3600
    cost = hours * (STT_RATE_PER_HOUR + DIARIZATION_RATE_PER_HOUR)
    print(
        f"\n{len(meeting.turns)} turns, {meeting.word_count()} words, "
        f"speakers: {', '.join(meeting.speakers()) or 'none'}"
    )
    print(f"Session time {session['seconds'] / 60:.1f} min, streaming cost about ${cost:.3f}")

    if not meeting.turns:
        print("No speech captured, so no notes to write.")
        return 1 if errors else 0

    print(f"\nWriting notes with {args.model} via LLM Gateway...")
    notes = write_notes(transcript_text, api_key=api_key, model=args.model)
    (out / "notes.json").write_text(json.dumps(notes, indent=2))
    (out / "notes.md").write_text(notes_to_markdown(notes))
    print(notes_to_markdown(notes))
    print(f"Saved {out / 'transcript.md'}, {out / 'notes.md'} and {out / 'notes.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
