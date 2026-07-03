import unittest

from horse_racing_game.app.progress import GameProgress
from horse_racing_game.app.stats import compute_player_stats, stats_summary_text


class StatsTests(unittest.TestCase):
    def test_compute_player_stats_uses_persisted_results(self) -> None:
        progress = GameProgress(
            quick_races_completed=2,
            career_races_completed=1,
            career_points=7,
            finished_races=3,
            wins=1,
            podiums=2,
            best_rank=1,
            last_audio_mix_id="descriptive",
            speech_verbosity="detailed",
            language_id="fr-FR",
            controller_profile_id="controller-accessible",
            mobile_gesture_profile_id="android-large-gestures",
            haptics_enabled=True,
            controller_only_navigation=True,
            horse_training_levels={"ember_stride": 2, "midnight_vector": 0},
            rival_encounters={"copper_gate": 4},
            last_online_race_summary={"rank": 2, "ticks": 240, "distance_m": 810.5},
            last_career_result_summary={"base_reward": 10, "contract_reward": 40, "staff_upkeep": 8, "net_reward": 42},
            last_time_trial_summary={"elapsed_s": 112.5, "best_s": 112.5, "personal_best": True},
            last_ghost_race_summary={"elapsed_s": 111.0, "ghost_elapsed_s": 112.5, "beat_ghost": True},
        )

        stats = compute_player_stats(progress)

        self.assertEqual(stats.total_races, 5)
        self.assertEqual(stats.quick_races, 2)
        self.assertEqual(stats.career_races, 1)
        self.assertEqual(stats.training_sessions, 2)
        self.assertEqual(stats.wins, 1)
        self.assertEqual(stats.podiums, 2)
        self.assertEqual(stats.best_rank, 1)
        self.assertEqual(stats.win_rate_percent, 20.0)
        self.assertEqual(stats.trained_horses, 1)
        self.assertEqual(stats.rivals_encountered, 1)
        self.assertEqual(stats.stable_id, "oak_lane")
        self.assertEqual(stats.difficulty_id, "pro")
        self.assertEqual(stats.audio_mix_id, "descriptive")
        self.assertEqual(stats.speech_verbosity, "detailed")
        self.assertEqual(stats.language_id, "fr-FR")
        self.assertTrue(stats.haptics_enabled)
        self.assertEqual(stats.career_energy, 2)
        self.assertEqual(stats.last_online_race_summary, {"rank": 2, "ticks": 240, "distance_m": 810.5})
        self.assertEqual(stats.last_career_result_summary["staff_upkeep"], 8)
        self.assertTrue(stats.last_time_trial_summary["personal_best"])
        self.assertTrue(stats.last_ghost_race_summary["beat_ghost"])

    def test_stats_summary_includes_result_counts(self) -> None:
        stats = compute_player_stats(
            GameProgress(
                finished_races=1,
                last_audio_mix_id="descriptive",
                speech_verbosity="minimal",
                language_id="es-ES",
                controller_profile_id="controller-accessible",
                mobile_gesture_profile_id="android-large-gestures",
                haptics_enabled=True,
                controller_only_navigation=True,
                wins=1,
                podiums=1,
                best_rank=1,
                last_online_race_summary={"rank": 1, "ticks": 120, "distance_m": 402.0},
                last_career_result_summary={"base_reward": 10, "contract_reward": 40, "staff_upkeep": 8, "net_reward": 42},
                last_time_trial_summary={"elapsed_s": 112.5, "best_s": 112.5, "personal_best": True},
                last_ghost_race_summary={"elapsed_s": 111.0, "ghost_elapsed_s": 112.5, "beat_ghost": True},
            )
        )

        text = stats_summary_text(stats)

        self.assertIn("Total races: 1.", text)
        self.assertIn("Best rank: 1.", text)
        self.assertIn("Wins: 1. Podiums: 1. Win rate: 100.0 percent.", text)
        self.assertIn("Stable: oak_lane. Difficulty: pro.", text)
        self.assertIn("Settings: audio descriptive. Speech minimal. Language es-ES.", text)
        self.assertIn("Controls: controller-accessible. Mobile gestures android-large-gestures. Haptics on. Controller-only navigation on.", text)
        self.assertIn("Career energy: 2. Rewards: 0.", text)
        self.assertIn("Last career result: Career result: rank ?.", text)
        self.assertIn("Rewards: base 10 | contract 40 | staff upkeep 8 | net 42.", text)
        self.assertIn("Last time trial: 112.5 seconds | best 112.5 | personal best.", text)
        self.assertIn("Last ghost race: 111.0 seconds | ghost 112.5 | beat ghost.", text)
        self.assertIn("Last online race: rank 1 | ticks 120 | distance 402.0 m.", text)


if __name__ == "__main__":
    unittest.main()
