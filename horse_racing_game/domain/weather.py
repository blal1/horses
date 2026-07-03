from dataclasses import dataclass


@dataclass(frozen=True)
class Weather:
    weather_id: str
    name: str
    speed_modifier: float
    stamina_cost_multiplier: float
    stability_modifier: float
    ambient_sound_id: str | None
