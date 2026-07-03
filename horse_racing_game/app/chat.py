from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from horse_racing_game.app.file_directories import FileDirectories
from horse_racing_game.app.savedata import atomic_write_json, load_json_object


DEFAULT_VOICE_MACROS = (
    "Good luck.",
    "Inside line.",
    "Outside line.",
    "Push now.",
    "Hold pace.",
    "Reset.",
)


@dataclass(frozen=True)
class ChatMessage:
    sender_id: str
    sender_label: str
    body: str
    kind: str = "text"
    timestamp_s: float = 0.0
    recipient_id: str | None = None

    def __post_init__(self) -> None:
        if not self.sender_id:
            raise ValueError("sender_id must be non-empty")
        if not self.sender_label:
            raise ValueError("sender_label must be non-empty")
        if not self.body.strip():
            raise ValueError("body must be non-empty")
        if self.kind not in {"text", "voice"}:
            raise ValueError("kind must be 'text' or 'voice'")
        if self.recipient_id == "":
            raise ValueError("recipient_id must be non-empty when provided")

    @property
    def is_private(self) -> bool:
        return self.recipient_id is not None

    def tts_text(self) -> str:
        prefix = "Private " if self.is_private else ""
        if self.kind == "voice":
            return f"{prefix}{self.sender_label} voice line: {self.body}"
        return f"{prefix}{self.sender_label}: {self.body}"


@dataclass(frozen=True)
class ChatModerationPolicy:
    blocked_terms: tuple[str, ...] = ()
    replacement: str = "[filtered]"

    def filter_text(self, text: str) -> str:
        filtered = text
        for term in self.blocked_terms:
            if term:
                filtered = _replace_case_insensitive(filtered, term, self.replacement)
        return filtered


class ChatComposer:
    def __init__(self, sender_ids: Iterable[str] = ("host", "guest"), voice_macros: tuple[str, ...] = DEFAULT_VOICE_MACROS) -> None:
        ordered_sender_ids = tuple(str(sender_id) for sender_id in sender_ids if str(sender_id))
        if not ordered_sender_ids:
            raise ValueError("at least one sender is required")
        self._sender_ids = ordered_sender_ids
        self._sender_index = 0
        self._draft = ""
        self._voice_macros = voice_macros
        self._voice_macro_index = 0

    @property
    def sender_id(self) -> str:
        return self._sender_ids[self._sender_index]

    @property
    def sender_label(self) -> str:
        return self.sender_id.replace("_", " ").title()

    @property
    def draft(self) -> str:
        return self._draft

    @property
    def voice_macro(self) -> str:
        return self._voice_macros[self._voice_macro_index]

    @property
    def sender_ids(self) -> tuple[str, ...]:
        return self._sender_ids

    @property
    def voice_macros(self) -> tuple[str, ...]:
        return self._voice_macros

    def select_sender(self, delta: int) -> str:
        self._sender_index = (self._sender_index + delta) % len(self._sender_ids)
        return self.sender_id

    def append_text(self, text: str) -> None:
        if text:
            self._draft += text

    def backspace(self) -> None:
        self._draft = self._draft[:-1]

    def clear(self) -> None:
        self._draft = ""

    def cycle_voice_macro(self, delta: int) -> str:
        self._voice_macro_index = (self._voice_macro_index + delta) % len(self._voice_macros)
        return self.voice_macro

    def submit_text(self, timestamp_s: float = 0.0, recipient_id: str | None = None) -> ChatMessage:
        message = ChatMessage(self.sender_id, self.sender_label, self._draft.strip(), "text", timestamp_s, recipient_id)
        self.clear()
        return message

    def submit_voice(self, timestamp_s: float = 0.0, recipient_id: str | None = None) -> ChatMessage:
        return ChatMessage(self.sender_id, self.sender_label, self.voice_macro, "voice", timestamp_s, recipient_id)


class ChatSession:
    def __init__(
        self,
        sender_ids: Iterable[str] = ("host", "guest"),
        max_messages: int = 12,
        moderation: ChatModerationPolicy | None = None,
    ) -> None:
        self._composer = ChatComposer(sender_ids)
        self._messages: deque[ChatMessage] = deque(maxlen=max_messages)
        self._muted_pairs: set[tuple[str, str]] = set()
        self._blocked_pairs: set[tuple[str, str]] = set()
        self._moderation = moderation or ChatModerationPolicy()
        self._max_messages = max_messages

    @property
    def composer(self) -> ChatComposer:
        return self._composer

    @property
    def messages(self) -> tuple[ChatMessage, ...]:
        return tuple(self._messages)

    @property
    def max_messages(self) -> int:
        return self._max_messages

    @property
    def moderation(self) -> ChatModerationPolicy:
        return self._moderation

    def add_message(self, message: ChatMessage) -> ChatMessage:
        if self._is_blocked(message):
            raise ValueError("message is blocked")
        moderated = ChatMessage(
            message.sender_id,
            message.sender_label,
            self._moderation.filter_text(message.body),
            message.kind,
            message.timestamp_s,
            message.recipient_id,
        )
        self._messages.appendleft(moderated)
        return moderated

    def submit_text(self, timestamp_s: float = 0.0, recipient_id: str | None = None) -> ChatMessage:
        return self.add_message(self._composer.submit_text(timestamp_s, recipient_id))

    def submit_voice(self, timestamp_s: float = 0.0, recipient_id: str | None = None) -> ChatMessage:
        return self.add_message(self._composer.submit_voice(timestamp_s, recipient_id))

    def mute(self, listener_id: str, sender_id: str) -> None:
        self._muted_pairs.add((listener_id, sender_id))

    def block(self, blocker_id: str, sender_id: str) -> None:
        self._blocked_pairs.add((blocker_id, sender_id))

    def visible_messages(self, viewer_id: str) -> tuple[ChatMessage, ...]:
        return tuple(message for message in self._messages if self._is_visible_to(message, viewer_id))

    def tts_lines(self, viewer_id: str) -> tuple[str, ...]:
        return tuple(message.tts_text() for message in self.visible_messages(viewer_id))

    def cycle_sender(self, delta: int) -> str:
        return self._composer.select_sender(delta)

    def cycle_voice_macro(self, delta: int) -> str:
        return self._composer.cycle_voice_macro(delta)

    def append_text(self, text: str) -> None:
        self._composer.append_text(text)

    def backspace(self) -> None:
        self._composer.backspace()

    def clear(self) -> None:
        self._composer.clear()

    def muted_snapshot(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._muted_pairs))

    def blocked_snapshot(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._blocked_pairs))

    def _is_blocked(self, message: ChatMessage) -> bool:
        if message.recipient_id is None:
            return False
        return (message.recipient_id, message.sender_id) in self._blocked_pairs

    def _is_visible_to(self, message: ChatMessage, viewer_id: str) -> bool:
        if (viewer_id, message.sender_id) in self._muted_pairs:
            return False
        if message.recipient_id is None:
            return True
        return viewer_id in {message.sender_id, message.recipient_id}


def _replace_case_insensitive(text: str, term: str, replacement: str) -> str:
    lowered = text.lower()
    needle = term.lower()
    output = []
    index = 0
    while True:
        match_index = lowered.find(needle, index)
        if match_index < 0:
            output.append(text[index:])
            return "".join(output)
        output.append(text[index:match_index])
        output.append(replacement)
        index = match_index + len(term)


def chat_session_path(project_root: Path) -> Path:
    return FileDirectories(project_root).save_file("chat_session.json")


def save_chat_session(project_root: Path, chat: ChatSession) -> None:
    atomic_write_json(
        chat_session_path(project_root),
        {
            "sender_ids": list(chat.composer.sender_ids),
            "voice_macros": list(chat.composer.voice_macros),
            "max_messages": chat.max_messages,
            "moderation": asdict(chat.moderation),
            "messages": [asdict(message) for message in chat.messages],
            "muted_pairs": [list(pair) for pair in chat.muted_snapshot()],
            "blocked_pairs": [list(pair) for pair in chat.blocked_snapshot()],
        },
    )


def load_chat_session(project_root: Path) -> ChatSession:
    data = load_json_object(chat_session_path(project_root))
    if data is None:
        return ChatSession()
    try:
        sender_ids = _string_tuple(data.get("sender_ids")) or ("host", "guest")
        voice_macros = _string_tuple(data.get("voice_macros")) or DEFAULT_VOICE_MACROS
        max_messages = max(1, int(data.get("max_messages") or 12))
        moderation_data = data.get("moderation")
        moderation = ChatModerationPolicy()
        if isinstance(moderation_data, dict):
            moderation = ChatModerationPolicy(
                _string_tuple(moderation_data.get("blocked_terms")),
                str(moderation_data.get("replacement") or "[filtered]"),
            )
        chat = ChatSession(sender_ids, max_messages=max_messages, moderation=moderation)
        chat._composer = ChatComposer(sender_ids, voice_macros)
        messages = deque(maxlen=max_messages)
        for item in _list(data.get("messages")):
            messages.append(
                ChatMessage(
                    str(item.get("sender_id") or ""),
                    str(item.get("sender_label") or ""),
                    str(item.get("body") or ""),
                    str(item.get("kind") or "text"),
                    float(item.get("timestamp_s") or 0.0),
                    _optional_string(item.get("recipient_id")),
                )
            )
        chat._messages = messages
        chat._muted_pairs = set(_pair_list(data.get("muted_pairs")))
        chat._blocked_pairs = set(_pair_list(data.get("blocked_pairs")))
    except (TypeError, ValueError):
        return ChatSession()
    return chat


def _list(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _pair_list(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        return ()
    pairs: list[tuple[str, str]] = []
    for item in value:
        if isinstance(item, list) and len(item) == 2 and isinstance(item[0], str) and isinstance(item[1], str):
            pairs.append((item[0], item[1]))
    return tuple(pairs)


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
