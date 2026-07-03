from dataclasses import dataclass


@dataclass(frozen=True)
class HorseStats:
    max_speed_mps: float
    acceleration: float
    stamina_capacity: float
    stamina_recovery: float
    handling: float
    nervousness: float


@dataclass(frozen=True)
class Horse:
    horse_id: str
    name: str
    role: str
    preferred_surface: str
    signature_sound: str
    stats: HorseStats
    traits: tuple[str, ...]

