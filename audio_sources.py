"""Audio sources that yield 16-bit mono PCM chunks for the Realtime Speech-to-Text API."""

import time
import wave
from typing import Iterator, Tuple

CHUNK_MS = 100  # the docs recommend 50-100 ms chunks; 20-1000 ms is allowed


def open_wav(path: str) -> Tuple[int, Iterator[bytes]]:
    """Return (sample_rate, chunk iterator) for a mono 16-bit PCM WAV file.

    Chunks are sent at live speed so the session behaves like a real meeting.
    """
    wf = wave.open(path, "rb")
    if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
        wf.close()
        raise ValueError(
            "Expected a mono, 16-bit PCM WAV. Convert with:\n"
            "  ffmpeg -i input.mp4 -ac 1 -ar 16000 -sample_fmt s16 meeting.wav"
        )
    sample_rate = wf.getframerate()
    frames_per_chunk = sample_rate * CHUNK_MS // 1000

    def chunks() -> Iterator[bytes]:
        try:
            while True:
                data = wf.readframes(frames_per_chunk)
                if not data:
                    break
                yield data
                time.sleep(CHUNK_MS / 1000)
        finally:
            wf.close()

    return sample_rate, chunks()


def open_microphone(sample_rate: int = 16000) -> Iterator[bytes]:
    """Yield chunks from the default microphone. Needs `pip install pyaudio`."""
    import pyaudio  # imported here so file mode works without PortAudio installed

    frames_per_chunk = sample_rate * CHUNK_MS // 1000
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=sample_rate,
        input=True,
        frames_per_buffer=frames_per_chunk,
    )
    try:
        while True:
            yield stream.read(frames_per_chunk, exception_on_overflow=False)
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
