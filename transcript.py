"""Collects final turns from the live stream and formats them for display and for the LLM.

On AssemblyAI-STT-3.7-Realtime, a turn's speaker label is final when the turn ends,
so each turn is stored once and never rewritten.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

PENDING = "PENDING"  # label the API sends for turns with under ~1 second of audio


@dataclass
class Turn:
    turn_order: int
    speaker: str  # "A", "B", ... or "PENDING"
    text: str
    start_ms: Optional[int] = None


def format_clock(ms: Optional[int]) -> str:
    if ms is None:
        return "--:--"
    seconds = ms // 1000
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def parse_speaker_names(spec: Optional[str]) -> Dict[str, str]:
    """Turn "A=Priya,B=Marcus" into {"A": "Priya", "B": "Marcus"}."""
    names: Dict[str, str] = {}
    if not spec:
        return names
    for pair in spec.split(","):
        if "=" not in pair:
            continue
        label, name = pair.split("=", 1)
        if label.strip() and name.strip():
            names[label.strip().upper()] = name.strip()
    return names


@dataclass
class MeetingTranscript:
    speaker_names: Dict[str, str] = field(default_factory=dict)
    turns: List[Turn] = field(default_factory=list)

    def add(self, turn: Turn) -> None:
        if turn.text.strip():
            self.turns.append(turn)

    def display_name(self, label: str) -> str:
        if label == PENDING:
            return "Unattributed"
        return self.speaker_names.get(label, f"Speaker {label}")

    def line(self, turn: Turn) -> str:
        return f"[{format_clock(turn.start_ms)}] {self.display_name(turn.speaker)}: {turn.text}"

    def as_text(self) -> str:
        return "\n".join(self.line(t) for t in self.turns)

    def speakers(self) -> List[str]:
        seen: List[str] = []
        for t in self.turns:
            if t.speaker != PENDING and t.speaker not in seen:
                seen.append(t.speaker)
        return [self.display_name(s) for s in seen]

    def word_count(self) -> int:
        return sum(len(t.text.split()) for t in self.turns)
