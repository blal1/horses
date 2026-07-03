from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from horse_racing_game.app.file_directories import FileDirectories
from horse_racing_game.app.savedata import atomic_write_json, load_json_object


ROLLOUT_CHANNELS = {"stable", "beta", "dev"}
ANALYTICS_EVENT_TYPES = {"race_start", "race_finish", "menu_action", "error", "economy", "accessibility"}


@dataclass(frozen=True)
class RemoteConfig:
    config_id: str
    channel: str = "stable"
    values: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.config_id:
            raise ValueError("config_id must be non-empty")
        if self.channel not in ROLLOUT_CHANNELS:
            raise ValueError("invalid rollout channel")

    def get_float(self, key: str, default: float) -> float:
        value = self.values.get(key, default)
        if isinstance(value, bool):
            return default
        if isinstance(value, (int, float)):
            return float(value)
        return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.values.get(key, default)
        return value if isinstance(value, bool) else default

    def merged(self, override: RemoteConfig) -> RemoteConfig:
        if self.channel != override.channel:
            raise ValueError("cannot merge configs from different channels")
        values = dict(self.values)
        values.update(override.values)
        return RemoteConfig(override.config_id, self.channel, values)


@dataclass(frozen=True)
class AnalyticsEvent:
    event_type: str
    player_id: str
    timestamp_s: float
    properties: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.event_type not in ANALYTICS_EVENT_TYPES:
            raise ValueError("invalid analytics event type")
        if not self.player_id:
            raise ValueError("player_id must be non-empty")
        if self.timestamp_s < 0:
            raise ValueError("timestamp_s must be non-negative")


class AnalyticsBuffer:
    def __init__(self, max_events: int = 128) -> None:
        if max_events < 1:
            raise ValueError("max_events must be positive")
        self._max_events = max_events
        self._events: list[AnalyticsEvent] = []

    @property
    def events(self) -> tuple[AnalyticsEvent, ...]:
        return tuple(self._events)

    def record(self, event: AnalyticsEvent) -> AnalyticsEvent:
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events :]
        return event

    def flush_payload(self) -> tuple[dict[str, Any], ...]:
        payload = tuple(
            {
                "event_type": event.event_type,
                "player_id": event.player_id,
                "timestamp_s": event.timestamp_s,
                "properties": dict(event.properties),
            }
            for event in self._events
        )
        self._events.clear()
        return payload

    def privacy_safe_payload(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "event_type": event.event_type,
                "player_hash": _stable_hash(event.player_id),
                "timestamp_s": event.timestamp_s,
                "properties": dict(event.properties),
            }
            for event in self._events
        )


@dataclass(frozen=True)
class CrashReport:
    report_id: str
    timestamp_s: float
    exception_type: str
    message: str
    stack_hash: str
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.report_id:
            raise ValueError("report_id must be non-empty")
        if self.timestamp_s < 0:
            raise ValueError("timestamp_s must be non-negative")
        if not self.exception_type:
            raise ValueError("exception_type must be non-empty")
        if not self.message:
            raise ValueError("message must be non-empty")
        if not self.stack_hash:
            raise ValueError("stack_hash must be non-empty")


@dataclass(frozen=True)
class TelemetrySnapshot:
    telemetry_consent_enabled: bool = False
    remote_config: RemoteConfig | None = None
    analytics_events: tuple[AnalyticsEvent, ...] = ()
    crash_reports: tuple[CrashReport, ...] = ()


def crash_report_from_exception(
    report_id: str,
    timestamp_s: float,
    error: BaseException,
    stack_text: str,
    context: dict[str, Any] | None = None,
) -> CrashReport:
    return CrashReport(
        report_id=report_id,
        timestamp_s=timestamp_s,
        exception_type=type(error).__name__,
        message=str(error),
        stack_hash=_stable_hash(stack_text),
        context=dict(context or {}),
    )


@dataclass(frozen=True)
class ExperimentVariant:
    variant_id: str
    weight: int
    config: RemoteConfig

    def __post_init__(self) -> None:
        if not self.variant_id:
            raise ValueError("variant_id must be non-empty")
        if self.weight < 1:
            raise ValueError("variant weight must be positive")


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    variants: tuple[ExperimentVariant, ...]

    def __post_init__(self) -> None:
        if not self.experiment_id:
            raise ValueError("experiment_id must be non-empty")
        if not self.variants:
            raise ValueError("experiment requires variants")
        variant_ids = [variant.variant_id for variant in self.variants]
        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError("duplicate experiment variant")

    def assign(self, player_id: str) -> ExperimentVariant:
        if not player_id:
            raise ValueError("player_id must be non-empty")
        total_weight = sum(variant.weight for variant in self.variants)
        bucket = _hash_bucket(f"{self.experiment_id}:{player_id}", total_weight)
        cursor = 0
        for variant in self.variants:
            cursor += variant.weight
            if bucket < cursor:
                return variant
        return self.variants[-1]


@dataclass(frozen=True)
class BalanceTuning:
    opponent_strength_multiplier: float = 1.0
    reward_multiplier: float = 1.0
    stamina_cost_multiplier: float = 1.0

    def __post_init__(self) -> None:
        if self.opponent_strength_multiplier <= 0:
            raise ValueError("opponent_strength_multiplier must be positive")
        if self.reward_multiplier <= 0:
            raise ValueError("reward_multiplier must be positive")
        if self.stamina_cost_multiplier <= 0:
            raise ValueError("stamina_cost_multiplier must be positive")

    def apply_remote_config(self, config: RemoteConfig) -> BalanceTuning:
        return BalanceTuning(
            opponent_strength_multiplier=config.get_float("opponent_strength_multiplier", self.opponent_strength_multiplier),
            reward_multiplier=config.get_float("reward_multiplier", self.reward_multiplier),
            stamina_cost_multiplier=config.get_float("stamina_cost_multiplier", self.stamina_cost_multiplier),
        )


@dataclass(frozen=True)
class SeasonalEvent:
    event_id: str
    title: str
    starts_at_s: float
    ends_at_s: float
    reward_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id must be non-empty")
        if not self.title:
            raise ValueError("title must be non-empty")
        if self.ends_at_s <= self.starts_at_s:
            raise ValueError("seasonal event end must be after start")

    def is_active(self, timestamp_s: float) -> bool:
        return self.starts_at_s <= timestamp_s < self.ends_at_s


@dataclass(frozen=True)
class RolloutRule:
    rollout_id: str
    channel: str
    percentage: int
    enabled_content_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.rollout_id:
            raise ValueError("rollout_id must be non-empty")
        if self.channel not in ROLLOUT_CHANNELS:
            raise ValueError("invalid rollout channel")
        if not 0 <= self.percentage <= 100:
            raise ValueError("percentage must be in [0, 100]")
        if any(not content_id for content_id in self.enabled_content_ids):
            raise ValueError("content ids must be non-empty")

    def includes_player(self, player_id: str) -> bool:
        if not player_id:
            raise ValueError("player_id must be non-empty")
        if self.percentage == 0:
            return False
        if self.percentage == 100:
            return True
        return _hash_bucket(f"{self.rollout_id}:{player_id}", 100) < self.percentage


class TelemetryStore:
    def __init__(
        self,
        *,
        telemetry_consent_enabled: bool = False,
        remote_config: RemoteConfig | None = None,
        analytics_buffer: AnalyticsBuffer | None = None,
        crash_reports: tuple[CrashReport, ...] = (),
    ) -> None:
        self._telemetry_consent_enabled = telemetry_consent_enabled
        self._remote_config = remote_config
        self._analytics = analytics_buffer or AnalyticsBuffer()
        self._crash_reports = list(crash_reports)

    @property
    def telemetry_consent_enabled(self) -> bool:
        return self._telemetry_consent_enabled

    @property
    def remote_config(self) -> RemoteConfig | None:
        return self._remote_config

    @property
    def analytics_events(self) -> tuple[AnalyticsEvent, ...]:
        return self._analytics.events

    @property
    def crash_reports(self) -> tuple[CrashReport, ...]:
        return tuple(self._crash_reports)

    def set_remote_config(self, config: RemoteConfig) -> RemoteConfig:
        self._remote_config = config
        return config

    def record_analytics(self, event: AnalyticsEvent) -> AnalyticsEvent | None:
        if not self._telemetry_consent_enabled:
            return None
        return self._analytics.record(event)

    def record_crash(self, report: CrashReport) -> CrashReport | None:
        if not self._telemetry_consent_enabled:
            return None
        self._crash_reports.append(report)
        return report

    def privacy_safe_analytics_payload(self) -> tuple[dict[str, Any], ...]:
        return self._analytics.privacy_safe_payload()

    def snapshot(self) -> TelemetrySnapshot:
        return TelemetrySnapshot(
            telemetry_consent_enabled=self._telemetry_consent_enabled,
            remote_config=self._remote_config,
            analytics_events=self._analytics.events,
            crash_reports=tuple(self._crash_reports),
        )


def live_ops_path(project_root: Path) -> Path:
    return FileDirectories(project_root).save_file("live_ops.json")


def save_telemetry_store(project_root: Path, store: TelemetryStore) -> None:
    snapshot = store.snapshot()
    atomic_write_json(
        live_ops_path(project_root),
        {
            "telemetry_consent_enabled": snapshot.telemetry_consent_enabled,
            "remote_config": None if snapshot.remote_config is None else _remote_config_to_dict(snapshot.remote_config),
            "analytics_events": [asdict(event) for event in snapshot.analytics_events],
            "crash_reports": [asdict(report) for report in snapshot.crash_reports],
        },
    )


def load_telemetry_store(project_root: Path) -> TelemetryStore:
    data = load_json_object(live_ops_path(project_root))
    if data is None:
        return TelemetryStore()
    try:
        remote_config = _remote_config_from_dict(data.get("remote_config"))
        buffer = AnalyticsBuffer()
        for item in _list(data.get("analytics_events")):
            buffer.record(_analytics_event_from_dict(item))
        reports = tuple(_crash_report_from_dict(item) for item in _list(data.get("crash_reports")))
        return TelemetryStore(
            telemetry_consent_enabled=bool(data.get("telemetry_consent_enabled")),
            remote_config=remote_config,
            analytics_buffer=buffer,
            crash_reports=reports,
        )
    except (TypeError, ValueError):
        return TelemetryStore()


def active_seasonal_events(events: tuple[SeasonalEvent, ...], timestamp_s: float) -> tuple[SeasonalEvent, ...]:
    return tuple(sorted((event for event in events if event.is_active(timestamp_s)), key=lambda event: event.starts_at_s))


def content_enabled_for_player(rules: tuple[RolloutRule, ...], player_id: str, channel: str) -> tuple[str, ...]:
    enabled: set[str] = set()
    for rule in rules:
        if rule.channel == channel and rule.includes_player(player_id):
            enabled.update(rule.enabled_content_ids)
    return tuple(sorted(enabled))


def _hash_bucket(value: str, modulo: int) -> int:
    if modulo < 1:
        raise ValueError("modulo must be positive")
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % modulo


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _remote_config_to_dict(config: RemoteConfig) -> dict[str, Any]:
    return {"config_id": config.config_id, "channel": config.channel, "values": dict(config.values)}


def _remote_config_from_dict(value: object) -> RemoteConfig | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("remote config must be an object")
    values = value.get("values")
    return RemoteConfig(
        str(value.get("config_id") or ""),
        str(value.get("channel") or "stable"),
        dict(values) if isinstance(values, dict) else {},
    )


def _analytics_event_from_dict(data: dict[str, object]) -> AnalyticsEvent:
    properties = data.get("properties")
    return AnalyticsEvent(
        str(data.get("event_type") or ""),
        str(data.get("player_id") or ""),
        float(data.get("timestamp_s") or 0.0),
        dict(properties) if isinstance(properties, dict) else {},
    )


def _crash_report_from_dict(data: dict[str, object]) -> CrashReport:
    context = data.get("context")
    return CrashReport(
        str(data.get("report_id") or ""),
        float(data.get("timestamp_s") or 0.0),
        str(data.get("exception_type") or ""),
        str(data.get("message") or ""),
        str(data.get("stack_hash") or ""),
        dict(context) if isinstance(context, dict) else {},
    )


def _list(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))
