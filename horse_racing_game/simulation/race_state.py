from dataclasses import dataclass


@dataclass(frozen=True)
class RunnerState:
    runner_id: str
    horse_name: str
    distance_m: float
    lateral_position: float
    speed_mps: float
    stamina: float
    stability: float
    is_player: bool
    rank: int


@dataclass(frozen=True)
class RaceState:
    elapsed_s: float
    runners: tuple[RunnerState, ...]
    is_finished: bool

    def player(self) -> RunnerState:
        for runner in self.runners:
            if runner.is_player:
                return runner
        raise ValueError("RaceState has no player runner.")

