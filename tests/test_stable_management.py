import unittest

from horse_racing_game.app.stable_management import (
    DEFAULT_STABLE_STAFF,
    DEFAULT_STABLE_UPGRADES,
    StaffMember,
    StableManagementState,
    StableUpgrade,
    SupplyInventory,
    TrainingPlan,
    stable_rest_energy_gain,
    stable_staff_by_id,
    stable_staff_weekly_cost,
    stable_upgrade_by_id,
)


class StableManagementTests(unittest.TestCase):
    def test_buy_upgrade_spends_funds_and_prevents_duplicate(self) -> None:
        state = StableManagementState("oak_lane", funds=500)
        upgrade = StableUpgrade("track_1", "track", 1, 200)

        updated = state.buy_upgrade(upgrade)

        self.assertEqual(updated.funds, 300)
        self.assertEqual(updated.upgrades, (upgrade,))
        with self.assertRaises(ValueError):
            updated.buy_upgrade(upgrade)

    def test_hire_staff_and_weekly_cost(self) -> None:
        state = StableManagementState("oak_lane", funds=500)
        trainer = StaffMember("trainer_1", "trainer", skill=7, weekly_cost=80)
        vet = StaffMember("vet_1", "vet", skill=6, weekly_cost=90)

        updated = state.hire_staff(trainer).hire_staff(vet)

        self.assertEqual(updated.weekly_cost(), 170)
        with self.assertRaises(ValueError):
            updated.hire_staff(trainer)

    def test_default_staff_catalog_supports_shared_cost_lookup(self) -> None:
        trainer = stable_staff_by_id("assistant_trainer")

        self.assertIsNotNone(trainer)
        self.assertEqual(trainer.weekly_cost, 8)
        self.assertIn(trainer, DEFAULT_STABLE_STAFF)
        self.assertEqual(stable_staff_weekly_cost(("assistant_trainer", "stable_vet", "unknown")), 15)

    def test_default_upgrade_catalog_supports_rest_recovery_lookup(self) -> None:
        clinic = stable_upgrade_by_id("recovery_clinic_1")

        self.assertIsNotNone(clinic)
        self.assertEqual(clinic.category, "clinic")
        self.assertIn(clinic, DEFAULT_STABLE_UPGRADES)
        self.assertEqual(stable_rest_energy_gain((), ()), 1)
        self.assertEqual(stable_rest_energy_gain(("recovery_clinic_1",), ()), 2)
        self.assertEqual(stable_rest_energy_gain((), ("stable_vet",)), 2)
        self.assertEqual(stable_rest_energy_gain(("recovery_clinic_1",), ("stable_vet",)), 3)
        self.assertEqual(stable_rest_energy_gain(("unknown",), ("unknown",)), 1)

    def test_training_plan_replaces_plan_for_same_horse(self) -> None:
        state = StableManagementState("oak_lane", funds=500)
        speed_plan = TrainingPlan("plan_1", "ember_stride", "speed", 3)
        recovery_plan = TrainingPlan("plan_2", "ember_stride", "recovery", 2)

        updated = state.add_training_plan(speed_plan).add_training_plan(recovery_plan)

        self.assertEqual(updated.training_plans, (recovery_plan,))
        self.assertEqual(speed_plan.fatigue_cost(), 6)
        self.assertEqual(recovery_plan.fatigue_cost(), 0)

    def test_supplies_consume_with_validation(self) -> None:
        supplies = SupplyInventory(feed_units=10, medicine_units=3)

        updated = supplies.consume(feed_units=4, medicine_units=1)

        self.assertEqual(updated.feed_units, 6)
        self.assertEqual(updated.medicine_units, 2)
        with self.assertRaises(ValueError):
            updated.consume(feed_units=7)

    def test_specialization_and_bonuses_use_staff_and_upgrades(self) -> None:
        state = StableManagementState("oak_lane", funds=1000)
        state = state.buy_upgrade(StableUpgrade("track_1", "track", 2, 200))
        state = state.buy_upgrade(StableUpgrade("clinic_1", "clinic", 1, 150))
        state = state.hire_staff(StaffMember("trainer_1", "trainer", 8, 80))
        state = state.hire_staff(StaffMember("vet_1", "vet", 6, 90))
        state = state.specialize_horse("ember_stride", "speed")

        self.assertEqual(state.horse_specializations, {"ember_stride": "speed"})
        self.assertEqual(state.training_effect_bonus("speed"), 1.13)
        self.assertEqual(state.vet_recovery_bonus(), 1.13)

    def test_invalid_stable_management_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            StableUpgrade("", "track", 1, 100)
        with self.assertRaises(ValueError):
            StableUpgrade("bad", "pool", 1, 100)
        with self.assertRaises(ValueError):
            StaffMember("staff", "chef", 5, 10)
        with self.assertRaises(ValueError):
            StaffMember("staff", "trainer", 0, 10)
        with self.assertRaises(ValueError):
            TrainingPlan("plan", "horse", "speed", 0)
        with self.assertRaises(ValueError):
            SupplyInventory(-1, 0)
        with self.assertRaises(ValueError):
            StableManagementState("", 100)
        with self.assertRaises(ValueError):
            StableManagementState("oak_lane", 50).buy_upgrade(StableUpgrade("track_1", "track", 1, 100))


if __name__ == "__main__":
    unittest.main()
