import unittest

from horse_racing_game.app.career_depth import (
    CareerContract,
    CareerProfile,
    ChampionshipBranch,
    HorseCondition,
    career_condition_after_event,
    career_condition_after_rest,
    career_condition_risk,
    career_condition_status,
    unlocked_branches,
)


class CareerDepthTests(unittest.TestCase):
    def test_contract_availability_and_prize_scaling(self) -> None:
        contract = CareerContract("c1", "sponsor", required_reputation=5, base_prize=100, win_bonus=50)

        self.assertFalse(contract.is_available(4))
        self.assertTrue(contract.is_available(5))
        self.assertEqual(contract.prize_for_rank(1), 150)
        self.assertEqual(contract.prize_for_rank(3), 50)
        self.assertEqual(contract.prize_for_rank(9), 0)

    def test_horse_condition_tracks_fatigue_injury_and_rest(self) -> None:
        condition = HorseCondition("ember_stride", fatigue=30)

        after_race = condition.after_race(80, injured=True)
        rested = after_race.rest(2)

        self.assertEqual(after_race.fatigue, 100)
        self.assertFalse(after_race.can_race)
        self.assertEqual(rested.fatigue, 60)
        self.assertTrue(rested.can_race)

    def test_condition_helpers_apply_staff_energy_and_rest_tradeoffs(self) -> None:
        tired = HorseCondition("ember_stride", fatigue=60)

        without_vet = career_condition_after_event(
            tired,
            energy=0,
            rank=5,
            is_training=False,
            staff_ids=(),
        )
        with_vet = career_condition_after_event(
            tired,
            energy=0,
            rank=5,
            is_training=False,
            staff_ids=("stable_vet",),
        )
        rested = career_condition_after_rest(without_vet, 2)

        self.assertGreater(career_condition_risk(80, 0), career_condition_risk(80, 0, ("stable_vet",)))
        self.assertGreater(without_vet.fatigue, with_vet.fatigue)
        self.assertGreaterEqual(without_vet.injury_days_remaining, 1)
        self.assertEqual(rested.fatigue, max(0, without_vet.fatigue - 40))
        self.assertEqual(career_condition_status(75, 0), "high fatigue")

    def test_profile_signs_contract_and_records_rewards(self) -> None:
        contract = CareerContract("c1", "sponsor", required_reputation=3, base_prize=120, win_bonus=80)
        profile = CareerProfile(reputation=3)

        signed = profile.sign_contract(contract)
        updated = signed.record_result(contract, rank=1)

        self.assertEqual(signed.active_contract_id, "c1")
        self.assertEqual(updated.prize_money, 200)
        self.assertEqual(updated.reputation, 8)

    def test_branch_unlocks_by_reputation_and_story(self) -> None:
        branches = (
            ChampionshipBranch("rookie", 0),
            ChampionshipBranch("rival_finale", 8, "beat_copper_gate"),
            ChampionshipBranch("elite", 12),
        )
        profile = CareerProfile(reputation=8).complete_story("beat_copper_gate")

        self.assertEqual([branch.branch_id for branch in unlocked_branches(profile, branches)], ["rookie", "rival_finale"])

    def test_invalid_career_depth_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CareerContract("", "sponsor", 0, 100)
        with self.assertRaises(ValueError):
            HorseCondition("", 0)
        with self.assertRaises(ValueError):
            HorseCondition("horse", -1)
        with self.assertRaises(ValueError):
            CareerProfile(reputation=-1)
        with self.assertRaises(ValueError):
            ChampionshipBranch("", 0)
        with self.assertRaises(ValueError):
            CareerProfile(reputation=0).sign_contract(CareerContract("c1", "sponsor", 10, 100))


if __name__ == "__main__":
    unittest.main()
