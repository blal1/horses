from dataclasses import dataclass


RaceEventValue = str | int | float | bool


@dataclass(frozen=True)
class RaceEvent:
    event_type: str
    priority: int
    timestamp_s: float
    subject_id: str | None
    data: dict[str, RaceEventValue]


