from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    content_root: Path
    track_id: str = "ashford_oval"
    player_horse_id: str = "ember_stride"
    weather_id: str = "clear"
    audio_mix_id: str = "normal"
    stable_id: str = "oak_lane"
    rival_stable_ids: dict[str, str] = field(default_factory=dict)
    horse_training_level: int = 0
    opponent_strength: float = 1.0
    seed: int = 42
    tick_hz: int = 4
    max_race_seconds: float = 240.0

    @property
    def tick_seconds(self) -> float:
        return 1.0 / self.tick_hz


def default_config(project_root: Path) -> AppConfig:
    return AppConfig(content_root=project_root / "content")
