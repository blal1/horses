import unittest

from horse_racing_game.app.training import MAX_TRAINING_LEVEL, apply_training_boost, clamp_training_level, next_training_level
from horse_racing_game.domain.horse import Horse, HorseStats


class TrainingTests(unittest.TestCase):
    def test_training_level_is_bounded(self) -> None:
        self.assertEqual(clamp_training_level(-1), 0)
        self.assertEqual(clamp_training_level(99), MAX_TRAINING_LEVEL)

    def test_next_level_only_increases_when_finished(self) -> None:
        self.assertEqual(next_training_level(1, finished=False), 1)
        self.assertEqual(next_training_level(1, finished=True), 2)
        self.assertEqual(next_training_level(MAX_TRAINING_LEVEL, finished=True), MAX_TRAINING_LEVEL)

    def test_training_boost_improves_control_stats(self) -> None:
        horse = Horse(
            horse_id="test",
            name="Test",
            role="player",
            preferred_surface="turf",
            signature_sound="none",
            stats=HorseStats(10.0, 5.0, 80.0, 3.0, 6.0, 2.0),
            traits=(),
        )

        boosted = apply_training_boost(horse, 3)

        self.assertGreater(boosted.stats.max_speed_mps, horse.stats.max_speed_mps)
        self.assertGreater(boosted.stats.acceleration, horse.stats.acceleration)
        self.assertGreater(boosted.stats.stamina_capacity, horse.stats.stamina_capacity)
        self.assertGreater(boosted.stats.handling, horse.stats.handling)
        self.assertLess(boosted.stats.nervousness, horse.stats.nervousness)


if __name__ == "__main__":
    unittest.main()
