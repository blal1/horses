from __future__ import annotations

from dataclasses import dataclass


ACCESSIBILITY_EVENT_GROUPS = {
    "status",
    "pace",
    "turns",
    "obstacles",
    "chat",
    "results",
}


@dataclass(frozen=True)
class SpeechFilter:
    enabled_event_groups: tuple[str, ...] = tuple(sorted(ACCESSIBILITY_EVENT_GROUPS))
    minimum_priority: int = 0

    def __post_init__(self) -> None:
        if self.minimum_priority < 0:
            raise ValueError("minimum_priority must be non-negative")
        if any(group not in ACCESSIBILITY_EVENT_GROUPS for group in self.enabled_event_groups):
            raise ValueError("unknown speech event group")

    def allows(self, event_group: str, priority: int) -> bool:
        if event_group not in ACCESSIBILITY_EVENT_GROUPS:
            raise ValueError("unknown speech event group")
        return event_group in self.enabled_event_groups and priority >= self.minimum_priority


@dataclass(frozen=True)
class AnnouncerProfile:
    profile_id: str
    label: str
    verbosity: str = "standard"
    pace_detail: bool = True
    opponent_detail: bool = True

    def __post_init__(self) -> None:
        if not self.profile_id:
            raise ValueError("profile_id must be non-empty")
        if not self.label:
            raise ValueError("label must be non-empty")
        if self.verbosity not in {"minimal", "standard", "detailed"}:
            raise ValueError("invalid verbosity")


@dataclass(frozen=True)
class VoiceMacro:
    macro_id: str
    phrase: str
    category: str = "race"

    def __post_init__(self) -> None:
        if not self.macro_id:
            raise ValueError("macro_id must be non-empty")
        if not self.phrase.strip():
            raise ValueError("phrase must be non-empty")
        if self.category not in {"race", "chat", "accessibility"}:
            raise ValueError("invalid macro category")


@dataclass(frozen=True)
class AccessibilitySettings:
    speech_filter: SpeechFilter = SpeechFilter()
    announcer: AnnouncerProfile = AnnouncerProfile("standard", "Standard")
    voice_macros: tuple[VoiceMacro, ...] = ()
    hold_to_speak_ms: int = 350
    haptics_enabled: bool = False
    controller_only_navigation: bool = False

    def __post_init__(self) -> None:
        if self.hold_to_speak_ms < 0:
            raise ValueError("hold_to_speak_ms must be non-negative")
        macro_ids = [macro.macro_id for macro in self.voice_macros]
        if len(macro_ids) != len(set(macro_ids)):
            raise ValueError("voice macro ids must be unique")

    def with_verbosity(self, verbosity: str) -> "AccessibilitySettings":
        return AccessibilitySettings(
            speech_filter=self.speech_filter,
            announcer=AnnouncerProfile(
                self.announcer.profile_id,
                self.announcer.label,
                verbosity,
                self.announcer.pace_detail,
                self.announcer.opponent_detail,
            ),
            voice_macros=self.voice_macros,
            hold_to_speak_ms=self.hold_to_speak_ms,
            haptics_enabled=self.haptics_enabled,
            controller_only_navigation=self.controller_only_navigation,
        )

    def add_voice_macro(self, macro: VoiceMacro, limit: int = 12) -> "AccessibilitySettings":
        if limit < 1:
            raise ValueError("limit must be positive")
        macros = tuple(item for item in self.voice_macros if item.macro_id != macro.macro_id)
        macros = (macro,) + macros
        return AccessibilitySettings(
            speech_filter=self.speech_filter,
            announcer=self.announcer,
            voice_macros=macros[:limit],
            hold_to_speak_ms=self.hold_to_speak_ms,
            haptics_enabled=self.haptics_enabled,
            controller_only_navigation=self.controller_only_navigation,
        )

    def should_speak(self, event_group: str, priority: int) -> bool:
        return self.speech_filter.allows(event_group, priority)

    def controller_prompt(self) -> str:
        if self.controller_only_navigation:
            return "Controller navigation enabled. Use directional controls and confirm or back."
        return "Keyboard and controller navigation enabled."


def default_accessibility_settings(profile_id: str = "standard") -> AccessibilitySettings:
    if profile_id == "minimal":
        return AccessibilitySettings(
            speech_filter=SpeechFilter(("status", "obstacles", "results"), minimum_priority=50),
            announcer=AnnouncerProfile("minimal", "Minimal", "minimal", pace_detail=False, opponent_detail=False),
            hold_to_speak_ms=500,
        )
    if profile_id == "detailed":
        return AccessibilitySettings(
            speech_filter=SpeechFilter(),
            announcer=AnnouncerProfile("detailed", "Detailed", "detailed", pace_detail=True, opponent_detail=True),
            haptics_enabled=True,
        )
    return AccessibilitySettings()
