import unittest
import tempfile
from pathlib import Path

from horse_racing_game.app.live_ops import (
    AnalyticsBuffer,
    AnalyticsEvent,
    BalanceTuning,
    Experiment,
    ExperimentVariant,
    RemoteConfig,
    RolloutRule,
    SeasonalEvent,
    TelemetryStore,
    active_seasonal_events,
    content_enabled_for_player,
    crash_report_from_exception,
    live_ops_path,
    load_telemetry_store,
    save_telemetry_store,
)


class LiveOpsTests(unittest.TestCase):
    def test_remote_config_typed_access_and_merge(self) -> None:
        base = RemoteConfig("base", "stable", {"reward_multiplier": 1.0, "enabled": False})
        override = RemoteConfig("override", "stable", {"reward_multiplier": 1.25, "enabled": True})

        merged = base.merged(override)

        self.assertEqual(merged.config_id, "override")
        self.assertEqual(merged.get_float("reward_multiplier", 1.0), 1.25)
        self.assertTrue(merged.get_bool("enabled"))
        self.assertEqual(merged.get_float("enabled", 2.0), 2.0)
        with self.assertRaises(ValueError):
            base.merged(RemoteConfig("beta", "beta"))

    def test_analytics_buffer_records_caps_and_flushes_payload(self) -> None:
        buffer = AnalyticsBuffer(max_events=2)
        buffer.record(AnalyticsEvent("race_start", "alice", 1.0, {"track": "ashford"}))
        buffer.record(AnalyticsEvent("menu_action", "alice", 2.0, {"item": "career"}))
        buffer.record(AnalyticsEvent("race_finish", "alice", 3.0, {"rank": 1}))

        payload = buffer.flush_payload()

        self.assertEqual([item["event_type"] for item in payload], ["menu_action", "race_finish"])
        self.assertEqual(buffer.events, ())
        with self.assertRaises(ValueError):
            AnalyticsEvent("unknown", "alice", 1.0)
        with self.assertRaises(ValueError):
            AnalyticsBuffer(max_events=0)

    def test_telemetry_store_requires_consent_and_uses_privacy_safe_payloads(self) -> None:
        no_consent = TelemetryStore()
        event = AnalyticsEvent("menu_action", "alice", 2.0, {"item": "career"})
        report = crash_report_from_exception("crash-1", 3.0, RuntimeError("boom"), "stack")

        self.assertIsNone(no_consent.record_analytics(event))
        self.assertIsNone(no_consent.record_crash(report))
        self.assertEqual(no_consent.analytics_events, ())
        self.assertEqual(no_consent.crash_reports, ())

        store = TelemetryStore(telemetry_consent_enabled=True)
        store.record_analytics(event)
        store.record_crash(report)
        payload = store.privacy_safe_analytics_payload()

        self.assertEqual(store.analytics_events, (event,))
        self.assertEqual(store.crash_reports, (report,))
        self.assertNotIn("player_id", payload[0])
        self.assertIn("player_hash", payload[0])
        self.assertNotEqual(payload[0]["player_hash"], "alice")

    def test_crash_report_hashes_stack_and_keeps_context(self) -> None:
        error = RuntimeError("audio backend failed")

        report = crash_report_from_exception("crash-1", 4.0, error, "stack line", {"screen": "race"})
        duplicate = crash_report_from_exception("crash-2", 5.0, error, "stack line")

        self.assertEqual(report.exception_type, "RuntimeError")
        self.assertEqual(report.message, "audio backend failed")
        self.assertEqual(report.stack_hash, duplicate.stack_hash)
        self.assertEqual(report.context["screen"], "race")

    def test_telemetry_store_persists_config_events_and_crashes(self) -> None:
        store = TelemetryStore(telemetry_consent_enabled=True)
        config = store.set_remote_config(RemoteConfig("remote-1", "stable", {"reward_multiplier": 1.2}))
        event = store.record_analytics(AnalyticsEvent("race_finish", "alice", 8.0, {"rank": 1}))
        report = store.record_crash(crash_report_from_exception("crash-1", 9.0, RuntimeError("audio"), "stack", {"screen": "race"}))
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)

            save_telemetry_store(project_root, store)
            loaded = load_telemetry_store(project_root)

            self.assertTrue(live_ops_path(project_root).exists())
            self.assertTrue(loaded.telemetry_consent_enabled)
            self.assertEqual(loaded.remote_config, config)
            self.assertEqual(loaded.analytics_events, (event,))
            self.assertEqual(loaded.crash_reports, (report,))

    def test_corrupt_telemetry_store_loads_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            path = live_ops_path(project_root)
            path.parent.mkdir(parents=True)
            path.write_text('{"remote_config": {"config_id": "", "channel": "stable"}}', encoding="utf-8")

            loaded = load_telemetry_store(project_root)

            self.assertFalse(loaded.telemetry_consent_enabled)
            self.assertIsNone(loaded.remote_config)
            self.assertEqual(loaded.analytics_events, ())

    def test_experiment_assignment_is_deterministic_and_weighted(self) -> None:
        experiment = Experiment(
            "balance-test",
            (
                ExperimentVariant("control", 1, RemoteConfig("control")),
                ExperimentVariant("faster", 3, RemoteConfig("faster")),
            ),
        )

        first = experiment.assign("alice")
        second = experiment.assign("alice")
        assigned = {experiment.assign(f"player-{index}").variant_id for index in range(20)}

        self.assertEqual(first, second)
        self.assertTrue(assigned <= {"control", "faster"})
        self.assertIn("faster", assigned)
        with self.assertRaises(ValueError):
            Experiment("bad", ())

    def test_balance_tuning_applies_remote_values(self) -> None:
        tuning = BalanceTuning()
        config = RemoteConfig(
            "tuning",
            values={
                "opponent_strength_multiplier": 1.05,
                "reward_multiplier": 1.2,
                "stamina_cost_multiplier": "ignore",
            },
        )

        updated = tuning.apply_remote_config(config)

        self.assertEqual(updated.opponent_strength_multiplier, 1.05)
        self.assertEqual(updated.reward_multiplier, 1.2)
        self.assertEqual(updated.stamina_cost_multiplier, 1.0)
        with self.assertRaises(ValueError):
            BalanceTuning(reward_multiplier=0.0)

    def test_active_seasonal_events_are_time_filtered_and_sorted(self) -> None:
        early = SeasonalEvent("spring", "Spring Cup", 10.0, 20.0, ("badge",))
        late = SeasonalEvent("summer", "Summer Cup", 15.0, 30.0)
        inactive = SeasonalEvent("fall", "Fall Cup", 40.0, 50.0)

        active = active_seasonal_events((late, inactive, early), 16.0)

        self.assertEqual([event.event_id for event in active], ["spring", "summer"])
        self.assertTrue(early.is_active(10.0))
        self.assertFalse(early.is_active(20.0))
        with self.assertRaises(ValueError):
            SeasonalEvent("bad", "Bad", 2.0, 2.0)

    def test_content_rollout_filters_by_channel_and_percentage(self) -> None:
        stable_all = RolloutRule("official-tracks", "stable", 100, ("track-a", "track-b"))
        stable_none = RolloutRule("hidden", "stable", 0, ("track-hidden",))
        beta_all = RolloutRule("beta-tracks", "beta", 100, ("track-c",))

        self.assertEqual(
            content_enabled_for_player((stable_none, beta_all, stable_all), "alice", "stable"),
            ("track-a", "track-b"),
        )
        self.assertEqual(content_enabled_for_player((stable_all, beta_all), "alice", "beta"), ("track-c",))
        self.assertTrue(stable_all.includes_player("alice"))
        self.assertFalse(stable_none.includes_player("alice"))
        with self.assertRaises(ValueError):
            RolloutRule("bad", "stable", 101, ("x",))

    def test_invalid_live_ops_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RemoteConfig("", "stable")
        with self.assertRaises(ValueError):
            RemoteConfig("id", "nightly")
        with self.assertRaises(ValueError):
            ExperimentVariant("control", 0, RemoteConfig("control"))
        with self.assertRaises(ValueError):
            RolloutRule("rollout", "stable", 50, ("",))


if __name__ == "__main__":
    unittest.main()
