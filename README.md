# Real-time meeting notetaker

A live meeting notetaker in a few hundred lines of Python. While the meeting runs, it prints a speaker-labeled transcript from [AssemblyAI-STT-3.7-Realtime](https://www.assemblyai.com/docs/streaming/label-speakers-and-separate-channels). When the meeting ends, it sends that transcript to [LLM Gateway](https://www.assemblyai.com/docs/llm-gateway/quickstart) and writes a summary, decisions, action items with owners, and open questions.

There's no second, post-call transcription job. Speaker labels on AssemblyAI-STT-3.7-Realtime are final when each turn ends, so the live transcript is the one the notes are built from.

Companion code for the AssemblyAI blog post *Live speaker labels for AI notetakers: why you can stop batching meeting audio*.

## What it does

```
Session 4f1c... started. Listening...

[00:02] Priya: Okay, let's get started. The main thing today is the March launch.
[00:09] Speaker B: Engineering is on track, but the billing migration is still open.
[00:15] Unattributed: Right.
[00:16] Priya: Marcus, can you own the migration plan and send it by Friday?
...
41 turns, 1288 words, speakers: Priya, Speaker B, Speaker C
Session time 11.4 min, streaming cost about $0.080

Writing notes with claude-sonnet-5-5 via LLM Gateway...
## Summary
...
## Action items
- [ ] **Speaker B**: Send the billing migration plan (due Friday) [00:16]
```

Output lands in `output/`: `transcript.md`, `notes.md` and `notes.json`.

## Quick start

```bash
git clone https://github.com/kelsey-aai/real-time-meeting-notetaker.git
cd real-time-meeting-notetaker
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your ASSEMBLYAI_API_KEY
```

Run it on a recording, streamed at live speed:

```bash
# convert any recording to mono 16 kHz 16-bit WAV first
ffmpeg -i meeting.mp4 -ac 1 -ar 16000 -sample_fmt s16 meeting.wav
python notetaker.py --file meeting.wav
```

Or on your microphone (Ctrl+C ends the session and writes the notes):

```bash
pip install pyaudio        # macOS: brew install portaudio first
python notetaker.py --mic
```

## Options

| Flag | What it does |
|---|---|
| `--file PATH` / `--mic` | Audio source. Files must be mono 16-bit PCM WAV. |
| `--max-speakers N` | Hard cap on speaker labels (1–10). Extra voices merge into the closest label, so leave headroom. |
| `--speakers "A=Priya,B=Marcus"` | Map labels to names before display and before the LLM pass. |
| `--keyterms "Priya,Kubernetes"` | Names and terms to boost, e.g. from the calendar invite. Start without it and add terms the model misses. |
| `--model ID` | LLM Gateway model for the notes (default `claude-sonnet-5-5`, or `LLM_MODEL` in `.env`). |
| `--out DIR` | Output folder (default `output`). |

## How it works

- `notetaker.py` opens a Realtime session with `speech_model="assemblyai-stt-3-7-realtime"` and `speaker_labels=True`, streams 100 ms chunks, and appends each turn once, when `end_of_turn` is true.
- Turns shorter than about one second come back with the speaker label `PENDING`. They're shown as "Unattributed", and the notes prompt never assigns an action item to them.
- `meeting_notes.py` calls LLM Gateway's chat completions endpoint with a JSON schema (`response_format`) and the `json-repair` post-processing step, so the notes parse every time.
- `client.disconnect(terminate=True)` closes the session. Streaming bills on session time, so the script always terminates, even on Ctrl+C.

## Costs

At published pay-as-you-go rates, AssemblyAI-STT-3.7-Realtime is $0.30/hr of session time and streaming speaker diarization adds $0.12/hr. The script prints an estimate when the session ends. LLM Gateway is billed per token at the provider's rate and isn't covered by the free signup credits. Check [assemblyai.com/pricing](https://www.assemblyai.com/pricing) for current rates.

## Tests

The offline tests need no API key:

```bash
pip install pytest
python -m pytest -q
```

## Notes

- A streaming session auto-closes after 3 hours, so meetings longer than that need a new session.
- If any of your customers process protected health information, AssemblyAI offers a Business Associate Addendum (BAA).
- Code was checked against the AssemblyAI docs and Python SDK 1.10.11.
