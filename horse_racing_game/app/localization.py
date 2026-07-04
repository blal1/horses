from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from string import Formatter
from typing import Any

from horse_racing_game.security.crypto import decrypt_bytes, encrypt_bytes


SUPPORTED_LOCALES = {"en-US", "fr-FR", "es-ES"}
SPEECH_PACES = {"slow", "normal", "fast"}
LANG_CONTEXT = "lang"


@dataclass(frozen=True)
class LocalizedString:
    key: str
    translations: dict[str, str]

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("key must be non-empty")
        if not self.translations:
            raise ValueError("translations must be non-empty")
        if any(locale not in SUPPORTED_LOCALES for locale in self.translations):
            raise ValueError("unsupported locale in translations")
        if any(not text for text in self.translations.values()):
            raise ValueError("translation text must be non-empty")

    def render(self, locale: str, fallback_locale: str = "en-US", **values: Any) -> str:
        template = self.translations.get(locale) or self.translations.get(fallback_locale)
        if template is None:
            template = next(iter(self.translations.values()))
        _validate_format_values(template, values)
        return template.format(**values)


@dataclass(frozen=True)
class LocalizationCatalog:
    strings: tuple[LocalizedString, ...]
    fallback_locale: str = "en-US"

    def __post_init__(self) -> None:
        if self.fallback_locale not in SUPPORTED_LOCALES:
            raise ValueError("unsupported fallback locale")
        keys = [item.key for item in self.strings]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate localization key")

    def text(self, key: str, locale: str, **values: Any) -> str:
        if locale not in SUPPORTED_LOCALES:
            locale = self.fallback_locale
        for item in self.strings:
            if item.key == key:
                return item.render(locale, self.fallback_locale, **values)
        raise ValueError(f"unknown localization key: {key}")

    def missing_keys_for_locale(self, locale: str) -> tuple[str, ...]:
        if locale not in SUPPORTED_LOCALES:
            raise ValueError("unsupported locale")
        return tuple(item.key for item in self.strings if locale not in item.translations)


@dataclass(frozen=True)
class LocaleFormat:
    locale: str
    decimal_separator: str = "."
    thousands_separator: str = ","
    seconds_unit: str = "s"
    meters_unit: str = "m"

    def __post_init__(self) -> None:
        if self.locale not in SUPPORTED_LOCALES:
            raise ValueError("unsupported locale")
        if not self.decimal_separator or not self.thousands_separator:
            raise ValueError("separators must be non-empty")

    def number(self, value: float, decimals: int = 0) -> str:
        if decimals < 0:
            raise ValueError("decimals must be non-negative")
        rendered = f"{value:,.{decimals}f}"
        return rendered.replace(",", "_").replace(".", self.decimal_separator).replace("_", self.thousands_separator)

    def distance(self, meters: float) -> str:
        return f"{self.number(meters, 0)} {self.meters_unit}"

    def duration(self, seconds: float) -> str:
        return f"{self.number(seconds, 1)} {self.seconds_unit}"


@dataclass(frozen=True)
class AccessibilityLanguagePack:
    locale: str
    speech_rate: str = "normal"
    phonetic_overrides: dict[str, str] = field(default_factory=dict)
    screen_reader_hint: str = ""

    def __post_init__(self) -> None:
        if self.locale not in SUPPORTED_LOCALES:
            raise ValueError("unsupported locale")
        if self.speech_rate not in SPEECH_PACES:
            raise ValueError("invalid speech rate")
        if any(not key or not value for key, value in self.phonetic_overrides.items()):
            raise ValueError("phonetic override keys and values must be non-empty")

    def pronounce(self, text: str) -> str:
        spoken = text
        for source, replacement in self.phonetic_overrides.items():
            spoken = spoken.replace(source, replacement)
        return spoken


@dataclass(frozen=True)
class TutorialStep:
    step_id: str
    message_key: str
    trigger_s: float
    required_action: str | None = None

    def __post_init__(self) -> None:
        if not self.step_id:
            raise ValueError("step_id must be non-empty")
        if not self.message_key:
            raise ValueError("message_key must be non-empty")
        if self.trigger_s < 0:
            raise ValueError("trigger_s must be non-negative")


@dataclass(frozen=True)
class TutorialScript:
    script_id: str
    steps: tuple[TutorialStep, ...]

    def __post_init__(self) -> None:
        if not self.script_id:
            raise ValueError("script_id must be non-empty")
        if not self.steps:
            raise ValueError("tutorial script requires steps")
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("duplicate tutorial step")

    def due_steps(self, elapsed_s: float, announced_step_ids: set[str]) -> tuple[TutorialStep, ...]:
        return tuple(
            sorted(
                (step for step in self.steps if step.trigger_s <= elapsed_s and step.step_id not in announced_step_ids),
                key=lambda step: step.trigger_s,
            )
        )


@dataclass(frozen=True)
class OnboardingChecklist:
    checklist_id: str
    task_keys: tuple[str, ...]
    completed_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.checklist_id:
            raise ValueError("checklist_id must be non-empty")
        if not self.task_keys:
            raise ValueError("onboarding checklist requires tasks")
        if any(not key for key in self.task_keys):
            raise ValueError("task keys must be non-empty")
        unknown_completed = set(self.completed_keys) - set(self.task_keys)
        if unknown_completed:
            raise ValueError("completed task is not in checklist")

    @property
    def completion_fraction(self) -> float:
        return len(set(self.completed_keys)) / len(set(self.task_keys))

    def mark_complete(self, task_key: str) -> OnboardingChecklist:
        if task_key not in self.task_keys:
            raise ValueError("task is not in checklist")
        if task_key in self.completed_keys:
            return self
        return OnboardingChecklist(self.checklist_id, self.task_keys, (*self.completed_keys, task_key))


@dataclass(frozen=True)
class CopyPolishRule:
    banned_phrases: tuple[str, ...] = ("click here", "simply", "obviously")
    max_words: int = 18

    def __post_init__(self) -> None:
        if self.max_words < 1:
            raise ValueError("max_words must be positive")

    def issues(self, text: str) -> tuple[str, ...]:
        stripped = text.strip()
        lowered = stripped.lower()
        issues: list[str] = []
        for phrase in self.banned_phrases:
            if phrase and phrase.lower() in lowered:
                issues.append(f"banned phrase: {phrase}")
        if len(stripped.split()) > self.max_words:
            issues.append("too many words")
        if stripped.endswith("!!"):
            issues.append("overexcited punctuation")
        return tuple(issues)

    def polished(self, text: str) -> str:
        polished = " ".join(text.strip().split())
        for phrase in self.banned_phrases:
            polished = _replace_case_insensitive(polished, phrase, "")
        polished = polished.replace("!!", ".")
        return " ".join(polished.split())


def default_localization_catalog() -> LocalizationCatalog:
    return LocalizationCatalog(
        (
            LocalizedString(
                "race.start",
                {
                    "en-US": "Start.",
                    "fr-FR": "Depart.",
                    "es-ES": "Salida.",
                },
            ),
            LocalizedString(
                "race.finish_rank",
                {
                    "en-US": "Finished rank {rank}.",
                    "fr-FR": "Arrive en position {rank}.",
                    "es-ES": "Termino en posicion {rank}.",
                },
            ),
            LocalizedString(
                "help.controls",
                {
                    "en-US": "Arrows or ZQSD control pace and line. J pushes.",
                    "fr-FR": "Les fleches ou ZQSD controlent le rythme et la ligne. Espace pousse.",
                },
            ),
            LocalizedString(
                "tutorial.status",
                {
                    "en-US": "Press Tab to hear rank, distance, stamina, and weather.",
                    "fr-FR": "Appuie sur Tab pour entendre le rang, la distance, l'endurance et la meteo.",
                },
            ),
            LocalizedString(
                "onboarding.first_race",
                {
                    "en-US": "Finish your first race.",
                    "fr-FR": "Termine ta premiere course.",
                    "es-ES": "Termina tu primera carrera.",
                },
            ),
        )
    )


def localization_catalog_to_dict(catalog: LocalizationCatalog) -> dict[str, object]:
    return {
        "fallback_locale": catalog.fallback_locale,
        "strings": [
            {
                "key": item.key,
                "translations": dict(item.translations),
            }
            for item in catalog.strings
        ],
    }


def localization_catalog_from_dict(data: dict[str, object]) -> LocalizationCatalog:
    fallback_locale = data.get("fallback_locale", "en-US")
    if not isinstance(fallback_locale, str):
        raise ValueError("fallback_locale must be a string")
    raw_strings = data.get("strings")
    if not isinstance(raw_strings, list):
        raise ValueError("strings must be a list")
    strings: list[LocalizedString] = []
    for item in raw_strings:
        if not isinstance(item, dict):
            raise ValueError("localization string entries must be objects")
        key = item.get("key")
        translations = item.get("translations")
        if not isinstance(key, str) or not isinstance(translations, dict):
            raise ValueError("localization string requires key and translations")
        parsed_translations: dict[str, str] = {}
        for locale, text in translations.items():
            if not isinstance(locale, str) or not isinstance(text, str):
                raise ValueError("translation locales and text must be strings")
            parsed_translations[locale] = text
        strings.append(LocalizedString(key, parsed_translations))
    return LocalizationCatalog(tuple(strings), fallback_locale)


def write_encrypted_localization_catalog(path: Path, catalog: LocalizationCatalog) -> None:
    payload = json.dumps(localization_catalog_to_dict(catalog), sort_keys=True).encode("utf-8")
    encrypted = encrypt_bytes(payload, LANG_CONTEXT)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(encrypted)
    tmp.replace(path)


def load_encrypted_localization_catalog(path: Path) -> LocalizationCatalog:
    payload = decrypt_bytes(Path(path).read_bytes(), LANG_CONTEXT)
    parsed = json.loads(payload.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("encrypted localization catalog must contain a JSON object")
    return localization_catalog_from_dict(parsed)


def locale_format(locale: str) -> LocaleFormat:
    if locale == "fr-FR":
        return LocaleFormat(locale, decimal_separator=",", thousands_separator=" ", seconds_unit="s", meters_unit="m")
    if locale == "es-ES":
        return LocaleFormat(locale, decimal_separator=",", thousands_separator=".", seconds_unit="s", meters_unit="m")
    return LocaleFormat("en-US")


def default_accessibility_language_pack(locale: str) -> AccessibilityLanguagePack:
    if locale == "fr-FR":
        return AccessibilityLanguagePack(
            "fr-FR",
            "normal",
            {"Ember Stride": "Ember Straide", "Ashford": "Acheford"},
            "Lecteur d'ecran actif.",
        )
    if locale == "es-ES":
        return AccessibilityLanguagePack("es-ES", "normal", {"Ember Stride": "Ember Estraid"}, "Lector de pantalla activo.")
    return AccessibilityLanguagePack("en-US", "normal", {}, "Screen reader active.")


def default_tutorial_script() -> TutorialScript:
    return TutorialScript(
        "race-basics",
        (
            TutorialStep("pace", "help.controls", 0.0, "throttle_up"),
            TutorialStep("status", "tutorial.status", 24.0, "status"),
        ),
    )


def _validate_format_values(template: str, values: dict[str, Any]) -> None:
    required = {
        field_name
        for _, field_name, _, _ in Formatter().parse(template)
        if field_name is not None and field_name
    }
    missing = required - set(values)
    if missing:
        raise ValueError(f"missing localization values: {', '.join(sorted(missing))}")


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
