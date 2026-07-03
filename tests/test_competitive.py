import unittest

from horse_racing_game.app.competitive import (
    CompetitiveLadder,
    CompetitiveProfile,
    RankedRaceResult,
    division_for_mmr,
    mmr_delta_for_rank,
)


class CompetitiveTests(unittest.TestCase):
    def test_division_thresholds_and_mmr_delta_are_stable(self) -> None:
        self.assertEqual(division_for_mmr(1000), "Bronze")
        self.assertEqual(division_for_mmr(1100), "Silver")
        self.assertEqual(division_for_mmr(1300), "Gold")
        self.assertEqual(division_for_mmr(1550), "Platinum")
        self.assertEqual(division_for_mmr(1800), "Diamond")
        self.assertGreater(mmr_delta_for_rank(1, 4), 0)
        self.assertLess(mmr_delta_for_rank(4, 4), 0)

    def test_ladder_records_ranked_result_and_placements(self) -> None:
        ladder = CompetitiveLadder("season-1")
        ladder.upsert_profile(CompetitiveProfile("alice", "Alice", mmr=1000, placements_remaining=1))

        updated = ladder.record_result(RankedRaceResult("alice", 1, 2))

        self.assertEqual(updated.ranked_races, 1)
        self.assertEqual(updated.wins, 1)
        self.assertEqual(updated.placements_remaining, 0)
        self.assertTrue(updated.is_placed)
        self.assertGreater(updated.mmr, 1000)

    def test_ladder_records_complete_field_and_orders_leaderboard(self) -> None:
        ladder = CompetitiveLadder("season-1")
        ladder.upsert_profile(CompetitiveProfile("alice", "Alice", mmr=1200))
        ladder.upsert_profile(CompetitiveProfile("bob", "Bob", mmr=1200))
        ladder.upsert_profile(CompetitiveProfile("carol", "Carol", mmr=1200))

        ladder.record_results(
            (
                RankedRaceResult("bob", 1, 3),
                RankedRaceResult("carol", 2, 3),
                RankedRaceResult("alice", 3, 3),
            )
        )
        rows = ladder.leaderboard()

        self.assertEqual([row.player_id for row in rows], ["bob", "carol", "alice"])
        self.assertEqual(rows[0].position, 1)
        self.assertEqual(rows[0].wins, 1)

    def test_ladder_rejects_incomplete_or_duplicate_rank_fields(self) -> None:
        ladder = CompetitiveLadder("season-1")
        ladder.upsert_profile(CompetitiveProfile("alice", "Alice"))
        ladder.upsert_profile(CompetitiveProfile("bob", "Bob"))

        with self.assertRaises(ValueError):
            ladder.record_results((RankedRaceResult("alice", 1, 3), RankedRaceResult("bob", 2, 3)))
        with self.assertRaises(ValueError):
            ladder.record_results((RankedRaceResult("alice", 1, 2), RankedRaceResult("bob", 1, 2)))

    def test_matchmaking_band_is_bounded_and_validated(self) -> None:
        ladder = CompetitiveLadder("season-1")
        ladder.upsert_profile(CompetitiveProfile("alice", "Alice", mmr=80))

        self.assertEqual(ladder.matchmaking_band("alice", width=150), (0, 230))
        with self.assertRaises(ValueError):
            ladder.matchmaking_band("alice", width=-1)

    def test_invalid_competitive_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CompetitiveProfile("", "Player")
        with self.assertRaises(ValueError):
            CompetitiveProfile("alice", "Alice", mmr=-1)
        with self.assertRaises(ValueError):
            RankedRaceResult("alice", 3, 2)
        with self.assertRaises(ValueError):
            division_for_mmr(-1)


if __name__ == "__main__":
    unittest.main()
