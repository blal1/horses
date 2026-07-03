from dataclasses import dataclass


@dataclass(frozen=True)
class RaceCommand:
    throttle_delta: float = 0.0
    lateral_delta: float = 0.0
    push_requested: bool = False
    jump_requested: bool = False
    duck_requested: bool = False
    request_status: bool = False
