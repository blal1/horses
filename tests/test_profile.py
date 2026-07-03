import tempfile
import unittest
from pathlib import Path

from horse_racing_game.app.savedata import read_secure_object
from horse_racing_game.app.profile import (
    claim_profile_starter_reward,
    equip_profile_badge,
    equip_profile_cosmetic,
    equip_profile_title,
    load_player_profile,
    profile_path,
    profile_summary_lines,
)


class ProfileTests(unittest.TestCase):
    def test_default_profile_has_identity_signature_and_empty_economy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = load_player_profile(Path(directory))

        self.assertEqual(profile.identity.display_name, "Rider")
        self.assertEqual(profile.economy.wallet.soft_currency, 0)
        self.assertIn("Rider", profile.signature())

    def test_starter_reward_unlocks_equipable_identity_items_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = claim_profile_starter_reward(root, load_player_profile(root))
            profile = claim_profile_starter_reward(root, profile)
            profile = equip_profile_title(root, profile, "storm_rider")
            profile = equip_profile_badge(root, profile, "founder")
            profile = equip_profile_cosmetic(root, profile, "red_silks")

            loaded = load_player_profile(root)
            raw = profile_path(root).read_bytes()
            secure_payload = read_secure_object(profile_path(root))

        self.assertEqual(profile.economy.wallet.soft_currency, 120)
        self.assertEqual(profile.economy.xp, 140)
        self.assertEqual(profile.economy.completed_achievement_ids, ("profile_starter",))
        self.assertEqual(loaded.identity.title_id, "storm_rider")
        self.assertEqual(loaded.identity.badge_ids, ("founder",))
        self.assertEqual(loaded.identity.cosmetic_ids, ("red_silks",))
        self.assertNotIn(b"soft_currency", raw)
        self.assertIsNotNone(secure_payload)
        self.assertTrue(any("Wallet: 120 soft" in line for line in profile_summary_lines(loaded)))

    def test_locked_items_and_unknown_options_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = load_player_profile(root)

            with self.assertRaises(ValueError):
                equip_profile_title(root, profile, "storm_rider")
            with self.assertRaises(ValueError):
                equip_profile_badge(root, profile, "missing")
            with self.assertRaises(ValueError):
                equip_profile_cosmetic(root, profile, "gold_saddle")

    def test_corrupt_profile_falls_back_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = profile_path(root)
            path.parent.mkdir(parents=True)
            path.write_text("{not json", encoding="utf-8")

            profile = load_player_profile(root)

        self.assertEqual(profile.identity.player_id, "local_player")


if __name__ == "__main__":
    unittest.main()
