import json
import tempfile
import unittest
from pathlib import Path

from horse_racing_game.app.savedata import read_secure_object
from horse_racing_game.app.progress import (
    GameProgress,
    load_progress,
    progress_path,
    record_career_contract,
    record_ghost_race_result,
    record_online_lobby_settings,
    record_online_race_summary,
    record_race_result,
    record_career_rest,
    record_rival_championship_result,
    record_rival_encounter,
    record_stable_staff_hire,
    record_stable_upgrade_purchase,
    record_time_trial_result,
    record_track_editor_selection,
    record_user_settings,
    save_progress,
    time_trial_key,
)


class ProgressTests(unittest.TestCase):
    def test_missing_progress_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            progress = load_progress(Path(directory))

        self.assertEqual(progress, GameProgress())

    def test_save_and_load_progress_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = GameProgress(
                quick_races_completed=3,
                tutorial_completed=True,
                last_horse_id="midnight_vector",
                last_track_id="stormglass_sprint",
                last_online_room_code="ROOM42",
                last_online_host="127.0.0.1",
                last_online_port=45678,
                last_online_peer_id="host",
                last_online_ready=True,
                active_career_contract_id="regional_backer",
                stable_upgrade_ids=("training_ring_1",),
                stable_staff_ids=("assistant_trainer",),
                career_fatigue=41,
                career_injury_days=1,
                speech_verbosity="detailed",
                language_id="fr-FR",
                controller_profile_id="controller-accessible",
                mobile_gesture_profile_id="android-large-gestures",
                haptics_enabled=True,
                controller_only_navigation=True,
                best_time_trial_times={"ember_stride|ashford_oval|clear": 112.5},
                last_time_trial_summary={"elapsed_s": 112.5},
                last_ghost_race_summary={"delta_s": -1.2},
            )
            save_progress(root, expected)

            self.assertEqual(load_progress(root), expected)
            self.assertEqual(read_secure_object(progress_path(root))["career_rewards"], 0)
            self.assertNotIn(b"career_rewards", progress_path(root).read_bytes())

    def test_corrupt_progress_falls_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = progress_path(root)
            path.parent.mkdir(parents=True)
            path.write_text("not json", encoding="utf-8")

            self.assertEqual(load_progress(root), GameProgress())

    def test_non_object_progress_falls_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = progress_path(root)
            path.parent.mkdir(parents=True)
            path.write_text("[]", encoding="utf-8")

            self.assertEqual(load_progress(root), GameProgress())

    def test_malformed_progress_values_are_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = progress_path(root)
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "quick_races_completed": "bad",
                        "career_races_completed": 999,
                        "career_fatigue": 150,
                        "career_injury_days": "2",
                        "speech_verbosity": "verbose",
                        "language_id": "fr-FR",
                        "haptics_enabled": True,
                        "finished_races": -4,
                        "best_rank": 0,
                        "horse_training_levels": {"ember_stride": "2", "bad": -5},
                        "rival_encounters": [],
                        "last_replay_lines": ["Kept.", 12],
                        "best_time_trial_times": {"good": "95.5", "bad": -2, "skip": "x"},
                    }
                ),
                encoding="utf-8",
            )

            progress = load_progress(root)

            self.assertEqual(progress.quick_races_completed, 0)
            self.assertEqual(progress.career_races_completed, 6)
            self.assertEqual(progress.career_fatigue, 100)
            self.assertEqual(progress.career_injury_days, 2)
            self.assertEqual(progress.speech_verbosity, "standard")
            self.assertEqual(progress.language_id, "fr-FR")
            self.assertTrue(progress.haptics_enabled)
            self.assertEqual(progress.finished_races, 0)
            self.assertIsNone(progress.best_rank)
            self.assertEqual(progress.horse_training_levels, {"ember_stride": 2, "bad": 0})
            self.assertEqual(progress.rival_encounters, {})
            self.assertEqual(progress.last_replay_lines, ("Kept.",))
            self.assertEqual(progress.best_time_trial_times, {"good": 95.5})
            self.assertIsNotNone(read_secure_object(path))

    def test_record_race_result_updates_counts_and_last_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_race_result(
                root,
                GameProgress(),
                "h1",
                "t1",
                is_tutorial=False,
                finished=True,
                weather_id="rain",
                audio_mix_id="descriptive",
                stable_id="stormforge",
                difficulty_id="elite",
                replay_lines=("Replay line one.", "Replay line two."),
            )

            self.assertEqual(progress.quick_races_completed, 1)
            self.assertFalse(progress.tutorial_completed)
            self.assertEqual(progress.last_horse_id, "h1")
            self.assertEqual(progress.last_track_id, "t1")
            self.assertEqual(progress.last_weather_id, "rain")
            self.assertEqual(progress.last_audio_mix_id, "descriptive")
            self.assertEqual(progress.last_stable_id, "stormforge")
            self.assertEqual(progress.last_difficulty_id, "elite")
            self.assertEqual(progress.last_replay_lines, ("Replay line one.", "Replay line two."))
            self.assertEqual(progress.finished_races, 1)
            self.assertEqual(read_secure_object(progress_path(root))["quick_races_completed"], 1)

    def test_record_tutorial_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_race_result(root, GameProgress(), "h1", "t1", is_tutorial=True, finished=True)

            self.assertEqual(progress.quick_races_completed, 0)
            self.assertTrue(progress.tutorial_completed)

    def test_record_career_result_adds_points_without_quick_race_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_race_result(
                root,
                GameProgress(),
                "h1",
                "t1",
                is_tutorial=False,
                finished=True,
                is_career=True,
                rank=2,
            )

            self.assertEqual(progress.quick_races_completed, 0)
            self.assertEqual(progress.career_races_completed, 1)
            self.assertEqual(progress.career_points, 7)
            self.assertEqual(progress.career_energy, 1)
            self.assertEqual(progress.career_rewards, 7)
            self.assertEqual(progress.career_fatigue, 18)
            self.assertEqual(progress.career_injury_days, 0)
            self.assertEqual(progress.finished_races, 1)
            self.assertEqual(progress.podiums, 1)
            self.assertEqual(progress.best_rank, 2)

    def test_record_career_result_applies_active_contract_payout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_race_result(
                root,
                GameProgress(active_career_contract_id="regional_backer"),
                "h1",
                "t1",
                is_tutorial=False,
                finished=True,
                is_career=True,
                rank=1,
            )

            self.assertEqual(progress.career_points, 10)
            self.assertEqual(progress.career_rewards, 120)
            self.assertEqual(load_progress(root).active_career_contract_id, "regional_backer")
            self.assertEqual(progress.last_career_result_summary["contract_reward"], 110)

    def test_record_career_result_deducts_staff_upkeep_and_summarizes_rewards(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_race_result(
                root,
                GameProgress(stable_staff_ids=("assistant_trainer",), career_rewards=5),
                "h1",
                "t1",
                is_tutorial=False,
                finished=True,
                is_career=True,
                rank=1,
            )

            self.assertEqual(progress.career_rewards, 7)
            self.assertEqual(progress.last_career_result_summary["base_reward"], 10)
            self.assertEqual(progress.last_career_result_summary["contract_reward"], 0)
            self.assertEqual(progress.last_career_result_summary["staff_upkeep"], 8)
            self.assertEqual(progress.last_career_result_summary["fatigue_before"], 0)
            self.assertEqual(progress.last_career_result_summary["fatigue_after"], 18)
            self.assertEqual(progress.last_career_result_summary["net_reward"], 2)
            self.assertEqual(load_progress(root).last_career_result_summary["rewards_balance"], 7)

    def test_record_career_result_summarizes_incomplete_attempt_without_rewards(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_race_result(
                root,
                GameProgress(career_rewards=12, last_career_result_summary={"finished": True, "net_reward": 10}),
                "h1",
                "t1",
                is_tutorial=False,
                finished=False,
                is_career=True,
                rank=None,
            )

            self.assertEqual(progress.career_races_completed, 0)
            self.assertEqual(progress.career_rewards, 12)
            self.assertEqual(progress.career_fatigue, 0)
            self.assertFalse(progress.last_career_result_summary["finished"])
            self.assertEqual(progress.last_career_result_summary["net_reward"], 0)
            self.assertEqual(load_progress(root).last_career_result_summary["rewards_balance"], 12)

    def test_record_race_result_tracks_wins_podiums_and_best_rank(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_race_result(root, GameProgress(), "h1", "t1", is_tutorial=False, finished=True, rank=3)
            progress = record_race_result(root, progress, "h1", "t1", is_tutorial=False, finished=True, rank=1)

            self.assertEqual(progress.finished_races, 2)
            self.assertEqual(progress.wins, 1)
            self.assertEqual(progress.podiums, 2)
            self.assertEqual(progress.best_rank, 1)

    def test_record_online_race_summary_persists_and_survives_later_race_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary = {
                "race_id": "seed:track",
                "peer_id": "host",
                "finished": True,
                "rank": 1,
                "ticks": 240,
                "distance_m": 812.5,
            }
            progress = record_online_race_summary(root, summary)
            progress = record_race_result(root, progress, "h1", "t1", is_tutorial=False, finished=True, rank=2)

            self.assertEqual(progress.last_online_race_summary, summary)
            self.assertEqual(load_progress(root).last_online_race_summary, summary)

    def test_time_trial_result_tracks_best_time_and_does_not_increment_quick_races(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_race_result(
                root,
                GameProgress(),
                "ember_stride",
                "ashford_oval",
                is_tutorial=False,
                finished=True,
                rank=1,
                count_quick_race=False,
            )
            progress = record_time_trial_result(
                root,
                progress,
                horse_id="ember_stride",
                track_id="ashford_oval",
                weather_id="clear",
                elapsed_s=112.5,
                finished=True,
            )
            progress = record_time_trial_result(
                root,
                progress,
                horse_id="ember_stride",
                track_id="ashford_oval",
                weather_id="clear",
                elapsed_s=120.0,
                finished=True,
            )

            key = time_trial_key("ember_stride", "ashford_oval", "clear")
            self.assertEqual(progress.quick_races_completed, 0)
            self.assertEqual(progress.best_time_trial_times[key], 112.5)
            self.assertFalse(progress.last_time_trial_summary["personal_best"])
            self.assertEqual(load_progress(root).best_time_trial_times[key], 112.5)

    def test_ghost_race_result_persists_delta_and_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_ghost_race_result(
                root,
                GameProgress(),
                horse_id="ember_stride",
                track_id="ashford_oval",
                weather_id="clear",
                elapsed_s=111.0,
                finished=True,
                ghost_elapsed_s=112.5,
            )

            self.assertEqual(progress.last_ghost_race_summary["delta_s"], -1.5)
            self.assertTrue(progress.last_ghost_race_summary["beat_ghost"])
            self.assertTrue(load_progress(root).last_ghost_race_summary["beat_ghost"])

    def test_record_online_lobby_settings_persists_reconnect_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            progress = record_online_lobby_settings(root, "ROOM42", "127.0.0.1", 45678, "guest", True)

            self.assertEqual(progress.last_online_room_code, "ROOM42")
            self.assertEqual(progress.last_online_host, "127.0.0.1")
            self.assertEqual(progress.last_online_port, 45678)
            self.assertEqual(progress.last_online_peer_id, "guest")
            self.assertTrue(progress.last_online_ready)
            self.assertEqual(load_progress(root).last_online_room_code, "ROOM42")

    def test_record_user_settings_persists_and_survives_later_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_user_settings(
                root,
                GameProgress(),
                audio_mix_id="descriptive",
                speech_verbosity="detailed",
                language_id="es-ES",
                controller_profile_id="controller-accessible",
                mobile_gesture_profile_id="android-large-gestures",
                haptics_enabled=True,
                controller_only_navigation=True,
            )
            progress = record_race_result(
                root,
                progress,
                "h1",
                "t1",
                is_tutorial=False,
                finished=True,
                audio_mix_id="descriptive",
            )

            loaded = load_progress(root)
            self.assertEqual(loaded.last_audio_mix_id, "descriptive")
            self.assertEqual(loaded.speech_verbosity, "detailed")
            self.assertEqual(loaded.language_id, "es-ES")
            self.assertEqual(loaded.controller_profile_id, "controller-accessible")
            self.assertEqual(loaded.mobile_gesture_profile_id, "android-large-gestures")
            self.assertTrue(loaded.haptics_enabled)
            self.assertTrue(loaded.controller_only_navigation)

    def test_record_user_settings_rejects_invalid_speech_verbosity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                record_user_settings(
                    Path(directory),
                    GameProgress(),
                    speech_verbosity="verbose",
                )

    def test_record_training_result_increases_selected_horse_level(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_race_result(
                root,
                GameProgress(),
                "h1",
                "t1",
                is_tutorial=False,
                finished=True,
                is_training=True,
            )

            self.assertEqual(progress.quick_races_completed, 0)
            self.assertEqual(progress.horse_training_levels["h1"], 1)
            self.assertEqual(load_progress(root).horse_training_levels["h1"], 1)

    def test_record_career_rest_recovers_energy_and_stable_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_career_rest(root, GameProgress(career_energy=1), "ironwood")

            self.assertEqual(progress.career_energy, 2)
            self.assertEqual(progress.last_stable_id, "ironwood")
            self.assertEqual(load_progress(root).career_energy, 2)

    def test_record_career_rest_uses_stable_recovery_investments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_career_rest(
                root,
                GameProgress(
                    career_energy=0,
                    stable_upgrade_ids=("recovery_clinic_1",),
                    stable_staff_ids=("stable_vet",),
                ),
                "oak_lane",
            )

            self.assertEqual(progress.career_energy, 3)
            self.assertEqual(progress.career_fatigue, 0)
            self.assertEqual(progress.career_injury_days, 0)
            self.assertEqual(load_progress(root).career_energy, 3)

    def test_career_condition_persists_through_race_rest_and_other_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_race_result(
                root,
                GameProgress(career_energy=0, career_fatigue=58),
                "h1",
                "t1",
                is_tutorial=False,
                finished=True,
                is_career=True,
                rank=5,
            )

            self.assertGreaterEqual(progress.career_injury_days, 1)
            self.assertGreater(progress.career_fatigue, 58)
            self.assertEqual(load_progress(root).career_injury_days, progress.career_injury_days)

            lobby_progress = record_online_lobby_settings(root, "ROOM42", "127.0.0.1", 45678, "host", True)
            self.assertEqual(lobby_progress.career_fatigue, progress.career_fatigue)
            self.assertEqual(lobby_progress.career_injury_days, progress.career_injury_days)

            rested = record_career_rest(root, lobby_progress, "oak_lane")
            self.assertLess(rested.career_fatigue, lobby_progress.career_fatigue)
            self.assertLess(rested.career_injury_days, lobby_progress.career_injury_days)

    def test_record_rival_encounter_increments_counter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_rival_encounter(root, GameProgress(), "copper_gate")
            progress = record_rival_encounter(root, progress, "copper_gate")

            self.assertEqual(progress.rival_encounters["copper_gate"], 2)
            self.assertEqual(load_progress(root).rival_encounters["copper_gate"], 2)

    def test_record_rival_championship_result_tracks_points_and_races(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = record_rival_championship_result(root, GameProgress(), "copper_gate", 7)
            progress = record_rival_championship_result(root, progress, "copper_gate", 10)

            self.assertEqual(progress.rival_championship_points["copper_gate"], 17)
            self.assertEqual(progress.rival_championship_races["copper_gate"], 2)
            saved = load_progress(root)
            self.assertEqual(saved.rival_championship_points["copper_gate"], 17)
            self.assertEqual(saved.rival_championship_races["copper_gate"], 2)

    def test_record_track_editor_selection_updates_last_track_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_progress(root, GameProgress(quick_races_completed=4, last_track_id="old_track"))

            progress = record_track_editor_selection(root, "custom_audio_track")

            self.assertEqual(progress.quick_races_completed, 4)
            self.assertEqual(progress.last_track_id, "custom_audio_track")
            self.assertEqual(load_progress(root).last_track_id, "custom_audio_track")

    def test_record_career_contract_persists_active_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            progress = record_career_contract(root, GameProgress(), "regional_backer")

            self.assertEqual(progress.active_career_contract_id, "regional_backer")
            self.assertEqual(load_progress(root).active_career_contract_id, "regional_backer")

    def test_record_stable_upgrade_purchase_spends_rewards_and_persists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            progress = record_stable_upgrade_purchase(
                root,
                GameProgress(career_rewards=8),
                "training_ring_1",
                6,
            )
            unchanged = record_stable_upgrade_purchase(root, progress, "training_ring_1", 6)

            self.assertEqual(progress.career_rewards, 2)
            self.assertEqual(progress.stable_upgrade_ids, ("training_ring_1",))
            self.assertEqual(unchanged, progress)
            self.assertEqual(load_progress(root).stable_upgrade_ids, ("training_ring_1",))

    def test_record_stable_staff_hire_spends_rewards_and_persists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            progress = record_stable_staff_hire(
                root,
                GameProgress(career_rewards=12),
                "assistant_trainer",
                8,
            )
            unchanged = record_stable_staff_hire(root, progress, "assistant_trainer", 8)

            self.assertEqual(progress.career_rewards, 4)
            self.assertEqual(progress.stable_staff_ids, ("assistant_trainer",))
            self.assertEqual(unchanged, progress)
            self.assertEqual(load_progress(root).stable_staff_ids, ("assistant_trainer",))


if __name__ == "__main__":
    unittest.main()
