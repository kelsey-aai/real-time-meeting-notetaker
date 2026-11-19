"""Turns the speaker-labeled live transcript into meeting notes with LLM Gateway."""

import json
from typing import Any, Dict

import assemblyai as aai

NOTES_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "decisions": {"type": "array", "items": {"type": "string"}},
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "task": {"type": "string"},
                    "due": {"type": "string"},
                    "timestamp": {"type": "string"},
                },
                "required": ["owner", "task", "due", "timestamp"],
                "additionalProperties": False,
            },
        },
        "open_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "decisions", "action_items", "open_questions"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You write meeting notes from a speaker-labeled transcript.
Each line is: [mm:ss] Speaker: text.

Rules:
- summary: 3 to 5 sentences on what the meeting covered and where it landed.
- decisions: only things the group agreed on, one line each.
- action_items: a task someone committed to. owner is the speaker who took it on,
  exactly as labeled in the transcript. If the person assigned is named in the text
  but is not a labeled speaker, use that name. Never use "Unattributed" as an owner;
  lines labeled Unattributed are short interjections with no reliable speaker.
- due: the deadline as stated ("Friday", "end of sprint"), or "" if none was given.
- timestamp: the [mm:ss] of the line where the commitment was made.
- open_questions: questions raised and left unresolved.
Do not invent owners, dates or decisions that are not in the transcript."""


def write_notes(transcript_text: str, api_key: str, model: str) -> Dict[str, Any]:
    gateway = aai.LLMGateway(api_key=api_key)
    completion = gateway.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript_text},
        ],
        max_tokens=2000,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "meeting_notes", "schema": NOTES_SCHEMA, "strict": True},
        },
        post_processing_steps=[{"type": "json-repair"}],
    )
    return json.loads(completion.choices[0].message.content)


def notes_to_markdown(notes: Dict[str, Any]) -> str:
    out = ["## Summary", notes["summary"], "", "## Decisions"]
    out += [f"- {d}" for d in notes["decisions"]] or ["- None recorded"]
    out += ["", "## Action items"]
    for item in notes["action_items"]:
        due = f" (due {item['due']})" if item["due"] else ""
        out.append(f"- [ ] **{item['owner']}**: {item['task']}{due} [{item['timestamp']}]")
    if not notes["action_items"]:
        out.append("- None recorded")
    out += ["", "## Open questions"]
    out += [f"- {q}" for q in notes["open_questions"]] or ["- None"]
    return "\n".join(out) + "\n"
