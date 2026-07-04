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
from horse_racing_game.app.config import AppConfig
from horse_racing_game.app.pygame_main import _config_for_selection
from horse_racing_game.domain.horse import Horse, HorseStats
from horse_racing_game.domain.track import Track, TrackSegment
from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.simulation.race_engine import RaceEngine
from horse_racing_game.ui.menu_models import MenuSelection


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

    def test_menu_difficulty_sets_non_career_config_strength(self) -> None:
        base = AppConfig(content_root=Path("content"))

        rookie = _config_for_selection(base, MenuSelection("ember_stride", "ashford_oval", difficulty_id="rookie"))
        elite = _config_for_selection(base, MenuSelection("ember_stride", "ashford_oval", difficulty_id="elite"))

        self.assertEqual(rookie.opponent_strength, difficulty_by_id("rookie").opponent_strength)
        self.assertEqual(elite.opponent_strength, difficulty_by_id("elite").opponent_strength)
        self.assertGreater(elite.opponent_strength, rookie.opponent_strength)

    def test_explicit_strength_override_is_preserved_for_career_scaling(self) -> None:
        base = AppConfig(content_root=Path("content"))

        config = _config_for_selection(
            base,
            MenuSelection("ember_stride", "ashford_oval", difficulty_id="elite"),
            opponent_strength=0.75,
        )

        self.assertEqual(config.opponent_strength, 0.75)


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


class TierRewardScalingTests(unittest.TestCase):
    def test_reward_multipliers_escalate_with_tier(self) -> None:
        self.assertLess(difficulty_by_id("rookie").reward_multiplier, 1.0)
        self.assertEqual(difficulty_by_id("pro").reward_multiplier, 1.0)
        self.assertGreater(difficulty_by_id("elite").reward_multiplier, 1.0)

    def test_elite_career_win_pays_more_than_rookie(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rookie = record_race_result(
                root, GameProgress(), "ember_stride", "ashford_oval",
                is_tutorial=False, finished=True, is_career=True, rank=1,
                career_difficulty_id="rookie", career_length=6,
            )
            elite = record_race_result(
                root, GameProgress(), "ember_stride", "ashford_oval",
                is_tutorial=False, finished=True, is_career=True, rank=1,
                career_difficulty_id="elite", career_length=6,
            )
            rookie_reward = rookie.last_career_result_summary["base_reward"]
            elite_reward = elite.last_career_result_summary["base_reward"]
            self.assertGreater(elite_reward, rookie_reward)
            self.assertEqual(elite.last_career_result_summary["difficulty_tier"], "Elite")
            self.assertEqual(elite.last_career_result_summary["reward_multiplier"], 1.25)

    def test_result_feedback_reports_difficulty_bonus(self) -> None:
        from horse_racing_game.app.career_result_feedback import career_result_summary_lines

        scaled = {
            "finished": True, "rank": 1, "base_reward": 13, "contract_reward": 0,
            "staff_upkeep": 0, "fatigue_before": 0, "fatigue_after": 10, "injury_days": 0,
            "net_reward": 13, "rewards_balance": 13, "difficulty_tier": "Elite", "reward_multiplier": 1.25,
        }
        lines = career_result_summary_lines(scaled)
        self.assertTrue(any("Elite tier scaled base reward by 1.25x" in line for line in lines))

        unscaled = {**scaled, "difficulty_tier": None, "reward_multiplier": 1.0}
        self.assertFalse(any("scaled base reward" in line for line in career_result_summary_lines(unscaled)))

    def test_missing_career_difficulty_leaves_reward_unscaled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            updated = record_race_result(
                root, GameProgress(), "ember_stride", "ashford_oval",
                is_tutorial=False, finished=True, is_career=True, rank=1, career_length=6,
            )
            summary = updated.last_career_result_summary
            self.assertEqual(summary["base_reward"], 10)  # career_reward_for_rank(1), unscaled
            self.assertIsNone(summary["difficulty_tier"])
            self.assertEqual(summary["reward_multiplier"], 1.0)


if __name__ == "__main__":
    unittest.main()
