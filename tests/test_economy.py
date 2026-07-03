import unittest

from horse_racing_game.app.economy import (
    Achievement,
    EconomyState,
    RewardGrant,
    Unlockable,
    Wallet,
    race_participation_reward,
    season_level_for_xp,
)


class EconomyTests(unittest.TestCase):
    def test_wallet_credits_and_spends_currency(self) -> None:
        wallet = Wallet(soft_currency=100, premium_currency=5)

        updated = wallet.credit(soft_currency=25).spend(soft_currency=80, premium_currency=2)

        self.assertEqual(updated.soft_currency, 45)
        self.assertEqual(updated.premium_currency, 3)
        with self.assertRaises(ValueError):
            updated.spend(soft_currency=999)

    def test_rewards_grant_currency_xp_items_and_levels(self) -> None:
        state = EconomyState()
        reward = RewardGrant("race_win", soft_currency=120, xp=230, item_ids=("winner_badge",))

        updated = state.grant(reward)

        self.assertEqual(updated.wallet.soft_currency, 120)
        self.assertEqual(updated.xp, 230)
        self.assertEqual(updated.season_level, 3)
        self.assertEqual(updated.owned_item_ids, ("winner_badge",))

    def test_purchase_unlockable_checks_level_currency_and_duplicates(self) -> None:
        state = EconomyState(wallet=Wallet(soft_currency=200), xp=250, season_level=3)
        unlockable = Unlockable("red_silks", "cosmetic", soft_cost=150, required_level=2)

        updated = state.purchase(unlockable)

        self.assertEqual(updated.wallet.soft_currency, 50)
        self.assertIn("red_silks", updated.owned_item_ids)
        with self.assertRaises(ValueError):
            updated.purchase(unlockable)
        with self.assertRaises(ValueError):
            EconomyState(wallet=Wallet(soft_currency=200), season_level=1).purchase(unlockable)

    def test_achievement_completion_grants_once(self) -> None:
        achievement = Achievement("first_win", "Win one race", 1, RewardGrant("achievement", xp=100, item_ids=("first_win_badge",)))
        state = EconomyState()

        completed = state.complete_achievement(achievement, value=1)
        completed_again = completed.complete_achievement(achievement, value=1)

        self.assertEqual(completed.xp, 100)
        self.assertEqual(completed.completed_achievement_ids, ("first_win",))
        self.assertEqual(completed_again, completed)
        with self.assertRaises(ValueError):
            state.complete_achievement(achievement, value=0)

    def test_race_participation_reward_scales_by_rank_and_finish(self) -> None:
        winner = race_participation_reward(1, finished=True)
        fifth = race_participation_reward(5, finished=True)
        dnf = race_participation_reward(4, finished=False)

        self.assertGreater(winner.soft_currency, fifth.soft_currency)
        self.assertEqual(dnf.reason, "race_participation")
        self.assertEqual(season_level_for_xp(0), 1)
        self.assertEqual(season_level_for_xp(250), 3)

    def test_invalid_economy_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Wallet(-1)
        with self.assertRaises(ValueError):
            Unlockable("", "cosmetic")
        with self.assertRaises(ValueError):
            Unlockable("item", "invalid")
        with self.assertRaises(ValueError):
            RewardGrant("", xp=1)
        with self.assertRaises(ValueError):
            Achievement("", "Description", 1, RewardGrant("reward"))
        with self.assertRaises(ValueError):
            EconomyState(xp=-1)
        with self.assertRaises(ValueError):
            race_participation_reward(0, True)
        with self.assertRaises(ValueError):
            season_level_for_xp(-1)


if __name__ == "__main__":
    unittest.main()
