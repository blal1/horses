import tempfile
import unittest
from pathlib import Path

from horse_racing_game.app.racing_modes import ScenarioProgress, racing_mode_by_id
from horse_racing_game.app.special_events import (
    SpecialEventResult,
    default_special_events,
    evaluate_special_event,
    load_special_event_records,
    observed_values_for,
    record_special_event_result,
    run_special_event,
    special_event_by_id,
    special_event_summary,
)
from horse_racing_game.simulation.race_state import RaceState, RunnerState


def _result(event_id: str, completed_ids: tuple[str, ...], elapsed_s: float, is_finished: bool = True) -> SpecialEventResult:
    challenge = special_event_by_id(event_id)
    return SpecialEventResult(
        challenge=challenge,
        progress=ScenarioProgress(event_id, completed_ids),
        elapsed_s=elapsed_s,
        rank=1,
        is_finished=is_finished,
    )


def _root() -> Path:
    return Path(__file__).parent.parent


def _state(is_finished: bool, rank: int, elapsed_s: float, stamina: float) -> RaceState:
    return RaceState(
        elapsed_s=elapsed_s,
        runners=(
            RunnerState("player", "You", 1000.0, 0.0, 12.0, stamina, 1.0, True, rank),
            RunnerState("copper_gate", "Copper Gate", 1000.0, 0.1, 12.0, 40.0, 1.0, False, 2),
        ),
        is_finished=is_finished,
    )


class SpecialEventTests(unittest.TestCase):
    def test_default_catalog_is_valid_and_matches_scenario_mode(self) -> None:
        events = default_special_events()
        self.assertGreaterEqual(len(events), 3)
        ids = [event.event_id for event in events]
        self.assertEqual(len(ids), len(set(ids)))
        scenario = racing_mode_by_id("scenario")
        for event in events:
            # every challenge reuses the shared scenario mode + event-spec validation
            event.spec.validate_for_mode(scenario)
            self.assertTrue(event.objectives)

    def test_lookup_by_id_and_unknown_raises(self) -> None:
        self.assertEqual(special_event_by_id("ashford_champion_charge").track_id, "ashford_oval")
        with self.assertRaises(ValueError):
            special_event_by_id("nope")

    def test_objectives_score_from_a_winning_finish(self) -> None:
        challenge = special_event_by_id("fog_sprint_gauntlet")
        values = observed_values_for(challenge, _state(True, 1, 90.0, 30.0))
        self.assertEqual(values["finish"], 1.0)
        self.assertEqual(values["beat_time"], 1.0)  # 90s under the 110s limit
        self.assertEqual(values["podium"], 1.0)
        progress = evaluate_special_event(challenge, _state(True, 1, 90.0, 30.0))
        self.assertEqual(set(progress.completed_objective_ids), {"finish", "beat_time", "podium"})

    def test_missed_objectives_are_not_marked_complete(self) -> None:
        challenge = special_event_by_id("fog_sprint_gauntlet")
        # finished but 5th and over the time limit -> only "finish" met
        progress = evaluate_special_event(challenge, _state(True, 5, 200.0, 30.0))
        self.assertEqual(progress.completed_objective_ids, ("finish",))

    def test_stamina_reserve_objective_respects_target(self) -> None:
        challenge = special_event_by_id("highcliff_endurance_climb")
        low = evaluate_special_event(challenge, _state(True, 2, 120.0, 4.0))
        high = evaluate_special_event(challenge, _state(True, 2, 120.0, 20.0))
        self.assertNotIn("stamina_reserve", low.completed_objective_ids)
        self.assertIn("stamina_reserve", high.completed_objective_ids)

    def test_unfinished_race_completes_nothing(self) -> None:
        challenge = special_event_by_id("ashford_champion_charge")
        progress = evaluate_special_event(challenge, _state(False, 1, 300.0, 50.0))
        self.assertEqual(progress.completed_objective_ids, ())

    def test_summary_reports_met_and_missed(self) -> None:
        challenge = special_event_by_id("fog_sprint_gauntlet")
        progress = evaluate_special_event(challenge, _state(True, 5, 200.0, 30.0))
        summary = special_event_summary(challenge, progress)
        self.assertIn("1 of 3 objectives met", summary)
        self.assertIn("Cross the finish line: met.", summary)
        self.assertIn("Finish in the top three: missed.", summary)

    def test_run_special_event_drives_the_core_loop_headlessly(self) -> None:
        challenge = special_event_by_id("ashford_champion_charge")
        result = run_special_event(_root(), challenge)
        self.assertIsInstance(result, SpecialEventResult)
        self.assertTrue(result.is_finished)
        self.assertGreaterEqual(result.rank, 1)
        # "finish" must always be met for a completed race
        self.assertIn("finish", result.progress.completed_objective_ids)


class SpecialEventPersistenceTests(unittest.TestCase):
    def test_no_save_yields_empty_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_special_event_records(Path(tmp)), {})

    def test_record_persists_and_survives_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = record_special_event_result(
                root, _result("ashford_champion_charge", ("finish", "win"), 100.0)
            )
            self.assertTrue(record.completed)
            self.assertEqual(record.best_objectives_met, 2)

            reloaded = load_special_event_records(root)["ashford_champion_charge"]
            self.assertTrue(reloaded.completed)
            self.assertEqual(reloaded.best_elapsed_s, 100.0)

    def test_best_objectives_and_time_are_kept_across_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # first attempt: only one objective, slow
            record_special_event_result(root, _result("fog_sprint_gauntlet", ("finish",), 150.0))
            # second attempt: more objectives, faster
            record_special_event_result(
                root, _result("fog_sprint_gauntlet", ("finish", "beat_time", "podium"), 90.0)
            )
            # third attempt: regressed, slower
            final = record_special_event_result(root, _result("fog_sprint_gauntlet", ("finish",), 200.0))

            self.assertEqual(final.best_objectives_met, 3)  # best is kept
            self.assertTrue(final.completed)  # once complete, stays complete
            self.assertEqual(final.best_elapsed_s, 90.0)  # best time is kept

    def test_unfinished_attempt_does_not_set_best_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = record_special_event_result(
                root, _result("highcliff_endurance_climb", (), 0.0, is_finished=False)
            )
            self.assertFalse(record.completed)
            self.assertIsNone(record.best_elapsed_s)


if __name__ == "__main__":
    unittest.main()
