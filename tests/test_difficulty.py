import tempfile
import unittest
from pathlib import Path

from horse_racing_game.app.difficulty import (
    DEFAULT_DIFFICULTY,
    DIFFICULTY_TIERS,
    career_difficulty,
    difficulty_by_id,
)
from horse_racing_game.app.progress import GameProgress, record_race_result
from horse_racing_game.domain.horse import Horse, HorseStats
from horse_racing_game.domain.track import Track, TrackSegment
from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.simulation.race_engine import RaceEngine


def _stats() -> HorseStats:
    return HorseStats(17.0, 8.0, 80.0, 4.0, 8.0, 3.0)


def _track() -> Track:
    return Track(
        track_id="t", name="T", length_m=2000.0, surface="turf", lanes=4,
        handedness="left", final_stretch_start_m=1600.0, audio_profile={},
        segments=(TrackSegment(0.0, 2000.0, "none", 0.0, 0.0, "a"),),
    )


def _opponent_distance(strength: float, ticks: int = 60) -> float:
    horses = (
        Horse("player", "Player", "player", "turf", "s", _stats(), ()),
        Horse("rival", "Rival", "opponent", "turf", "s", _stats(), ()),
    )
    engine = RaceEngine(_track(), horses, "player", seed=3, weather=None, opponent_strength=strength)
    # Player coasts so opponent pace (driven by strength) is what varies.
    command = RaceCommand(throttle_delta=0.2)
    result = engine.tick(command, 0.25)
    for _ in range(ticks - 1):
        result = engine.tick(command, 0.25)
    rival = next(r for r in result.state.runners if not r.is_player)
    return rival.distance_m


class DifficultyTierTests(unittest.TestCase):
    def test_difficulty_by_id(self) -> None:
        self.assertEqual(difficulty_by_id("elite").tier_id, "elite")
        self.assertEqual(difficulty_by_id("nope"), DEFAULT_DIFFICULTY)

    def test_career_difficulty_escalates_across_season(self) -> None:
        self.assertEqual(career_difficulty(0, 3), DIFFICULTY_TIERS[0])  # rookie
        self.assertEqual(career_difficulty(1, 3), DIFFICULTY_TIERS[1])  # pro
        self.assertEqual(career_difficulty(2, 3), DIFFICULTY_TIERS[2])  # elite

    def test_career_difficulty_handles_edges(self) -> None:
        self.assertEqual(career_difficulty(0, 1), DEFAULT_DIFFICULTY)
        self.assertEqual(career_difficulty(99, 3), DIFFICULTY_TIERS[2])  # clamped


class OpponentStrengthTests(unittest.TestCase):
    def test_stronger_setting_makes_opponents_faster(self) -> None:
        weak = _opponent_distance(0.97)
        strong = _opponent_distance(1.06)
        self.assertGreater(strong, weak)

    def test_default_strength_is_deterministic(self) -> None:
        self.assertEqual(_opponent_distance(1.0), _opponent_distance(1.0))


class DataDrivenCareerLengthTests(unittest.TestCase):
    def test_career_length_can_exceed_default_three(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            progress = GameProgress(career_races_completed=3, career_points=30)
            updated = record_race_result(
                root, progress, "ember_stride", "ashford_oval",
                is_tutorial=False, finished=True, is_career=True, rank=1, career_length=5,
            )
            self.assertEqual(updated.career_races_completed, 4)

    def test_default_length_uses_six_race_season(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            progress = GameProgress(career_races_completed=6, career_points=30)
            updated = record_race_result(
                root, progress, "ember_stride", "ashford_oval",
                is_tutorial=False, finished=True, is_career=True, rank=1,
            )
            self.assertEqual(updated.career_races_completed, 6)


if __name__ == "__main__":
    unittest.main()
