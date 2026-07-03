import unittest

from horse_racing_game.app.identity import HorseCard, PlayerIdentity


class IdentityTests(unittest.TestCase):
    def test_identity_builds_public_name_and_signature(self) -> None:
        identity = PlayerIdentity(
            "alice",
            "Alice",
            title_id="storm_rider",
            badge_ids=("winner", "founder"),
            emblem_id="gold_horseshoe",
            club_tag="FAST",
            horse_card=HorseCard("ember_stride", "Ember Stride", "midnight"),
        )

        self.assertEqual(identity.public_name, "[FAST] Alice")
        self.assertIn("[FAST] Alice", identity.signature())
        self.assertIn("Storm Rider", identity.signature())
        self.assertIn("Horse: Ember Stride", identity.signature())
        self.assertIn("Badges: winner, founder", identity.signature())

    def test_equipping_badges_is_unique_and_limited(self) -> None:
        identity = PlayerIdentity("alice", "Alice", badge_ids=("veteran", "winner", "founder"))

        updated = identity.equip_badge("champion")
        updated = updated.equip_badge("winner")

        self.assertEqual(updated.badge_ids, ("winner", "champion", "veteran"))

    def test_equipping_cosmetics_and_title_returns_new_identity(self) -> None:
        identity = PlayerIdentity("alice", "Alice")

        updated = identity.equip_cosmetic("red_silks").equip_cosmetic("gold_saddle").with_title("elite_racer")

        self.assertEqual(identity.cosmetic_ids, ())
        self.assertEqual(updated.cosmetic_ids, ("gold_saddle", "red_silks"))
        self.assertEqual(updated.title_id, "elite_racer")

    def test_horse_card_can_be_attached(self) -> None:
        identity = PlayerIdentity("alice", "Alice")

        updated = identity.with_horse_card(HorseCard("night_rail", "Night Rail"))

        self.assertEqual(updated.horse_card.horse_id, "night_rail")
        self.assertIn("Night Rail", updated.signature())

    def test_invalid_identity_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            PlayerIdentity("", "Alice")
        with self.assertRaises(ValueError):
            PlayerIdentity("alice", "")
        with self.assertRaises(ValueError):
            PlayerIdentity("alice", "Alice", club_tag="fast")
        with self.assertRaises(ValueError):
            PlayerIdentity("alice", "Alice", badge_ids=("winner", "winner"))
        with self.assertRaises(ValueError):
            PlayerIdentity("alice", "Alice", cosmetic_ids=("",))
        with self.assertRaises(ValueError):
            HorseCard("", "Ember Stride")


if __name__ == "__main__":
    unittest.main()
