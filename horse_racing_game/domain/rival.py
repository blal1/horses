from dataclasses import dataclass


@dataclass(frozen=True)
class RivalProfile:
    horse_id: str
    display_name: str
    intro_line: str
    approach_line: str
    passing_line: str
