import tempfile
import unittest
from pathlib import Path

from horse_racing_game.app.progress import GameProgress
from horse_racing_game.app.replay import RaceReplay, ReplayTimeline
from horse_racing_game.app.replay import replay_to_dict
from horse_racing_game.app.replay_exports import build_last_replay_share_bundle, load_replay_share_index, save_replay_share_bundle
from horse_racing_game.app.replay_sharing import (
    ReplayBrowser,
    ReplayLibraryEntry,
    TimelineScrubber,
    create_command_log_share,
    create_highlight_clips,
    create_photo_finish_frame,
    create_replay_summary,
    create_shared_ghost_file,
    export_race_text,
)
from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.simulation.race_events import RaceEvent
from horse_racing_game.simulation.race_state import RaceState, RunnerState


class ReplaySharingTests(unittest.TestCase):
    def _replay(self) -> RaceReplay:
        return RaceReplay(
            seed=7,
            track_id="ashford_oval",
            player_horse_id="ember_stride",
            weather_id="clear",
            stable_id="oak_lane",
            tick_seconds=0.25,
            commands=(RaceCommand(throttle_delta=1.0), RaceCommand(push_requested=True)),
        )

    def _state(self) -> RaceState:
        return RaceState(
            elapsed_s=71.5,
            is_finished=True,
            runners=(
                RunnerState("ember_stride", "Ember Stride", 1200.0, 0.0, 0.0, 32.0, 1.0, True, 2),
                RunnerState("copper_gate", "Copper Gate", 1201.5, 0.0, 0.0, 30.0, 1.0, False, 1),
            ),
        )

    def _timeline(self) -> ReplayTimeline:
        events = (
            RaceEvent("race_started", 100, 0.0, None, {}),
            RaceEvent("opponent_passing", 70, 12.0, "copper_gate", {}),
            RaceEvent("final_stretch", 80, 58.0, None, {}),
            RaceEvent("race_finished", 100, 71.5, None, {}),
        )
        return ReplayTimeline(events=events, key_indices=(0, 1, 2, 3), final_stretch_index=2)

    def test_replay_summary_uses_final_state_when_available(self) -> None:
        summary = create_replay_summary("replay-1", "Close Finish", 10.0, self._replay(), self._state(), ("cup", "cup"))

        self.assertEqual(summary.duration_s, 71.5)
        self.assertEqual(summary.final_rank, 2)
        self.assertEqual(summary.tags, ("cup",))

    def test_replay_browser_lists_recent_and_filters_by_tag(self) -> None:
        replay = self._replay()
        early = create_replay_summary("early", "Early", 1.0, replay, tags=("career",))
        late = create_replay_summary("late", "Late", 2.0, replay, tags=("career", "favorite"))
        browser = ReplayBrowser(
            (
                ReplayLibraryEntry(early, replay),
                ReplayLibraryEntry(late, replay),
            )
        )

        self.assertEqual([item.replay_id for item in browser.list_recent()], ["late", "early"])
        self.assertEqual([item.replay_id for item in browser.filter_by_tag("favorite")], ["late"])
        self.assertEqual(browser.get("early").summary.title, "Early")
        with self.assertRaises(ValueError):
            browser.add(ReplayLibraryEntry(early, replay))

    def test_timeline_scrubber_seeks_steps_and_jumps_to_key_moments(self) -> None:
        scrubber = TimelineScrubber(self._timeline())

        self.assertEqual(scrubber.current_event().event_type, "race_started")
        self.assertEqual(scrubber.step(2).current_event().event_type, "final_stretch")
        self.assertEqual(scrubber.seek(99).index, 3)
        self.assertEqual(scrubber.seek(1).seek_key_moment(1).current_event().event_type, "final_stretch")
        self.assertEqual(scrubber.seek(3).seek_key_moment(-1).current_event().event_type, "final_stretch")
        self.assertEqual(scrubber.seek_final_stretch().current_event().event_type, "final_stretch")

    def test_shared_ghost_and_command_log_use_replay_payload(self) -> None:
        replay = self._replay()

        ghost = create_shared_ghost_file("ghost-1", replay, "Ember Ghost")
        command_log = create_command_log_share("replay-1", replay)

        self.assertEqual(ghost.replay_payload["seed"], 7)
        self.assertEqual(ghost.duration_s, 0.5)
        self.assertEqual(command_log.command_count, 2)
        self.assertEqual(command_log.payload["track_id"], "ashford_oval")

    def test_export_text_includes_title_and_lines(self) -> None:
        summary = create_replay_summary("replay-1", "Close Finish", 10.0, self._replay())
        export = export_race_text(summary, ("Replay line one.", "Replay line two."))

        self.assertEqual(export.format, "text")
        self.assertEqual(export.lines[0], "Close Finish")
        self.assertIn("Replay line two.", export.lines)

    def test_last_replay_share_bundle_saves_export_files(self) -> None:
        root = Path(__file__).parent.parent
        progress = GameProgress(
            last_replay=replay_to_dict(self._replay()),
            last_replay_lines=("Replay line one.", "Replay line two."),
        )
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            bundle = build_last_replay_share_bundle(root / "content", progress)
            assert bundle is not None
            result = save_replay_share_bundle(project_root, bundle)

            self.assertEqual(len(result.files), 7)
            self.assertTrue(all(path.exists() for path in result.files))
            self.assertIn("Replay line two.", (result.directory / "last-replay-race.txt").read_text(encoding="utf-8"))
            self.assertTrue((result.directory / "last-replay-ghost.json").exists())

    def test_replay_share_index_loads_exported_manifests(self) -> None:
        root = Path(__file__).parent.parent
        progress = GameProgress(last_replay=replay_to_dict(self._replay()), last_replay_lines=("Replay line one.",))
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            bundle = build_last_replay_share_bundle(root / "content", progress)
            assert bundle is not None
            save_replay_share_bundle(project_root, bundle)

            index = load_replay_share_index(project_root)

            self.assertEqual(len(index), 1)
            self.assertEqual(index[0].replay_id, "last-replay")
            self.assertEqual(index[0].title, "Last Race Replay")
            self.assertEqual(index[0].track_id, "ashford_oval")
            self.assertEqual(len(index[0].files), 7)

    def test_replay_share_index_skips_corrupt_or_incomplete_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            share_dir = Path(directory) / "save" / "replay_shares"
            share_dir.mkdir(parents=True)
            (share_dir / "bad-manifest.json").write_text('{"replay_id": "", "files": []}', encoding="utf-8")
            (share_dir / "missing-manifest.json").write_text(
                '{"replay_id": "missing", "files": ["missing-summary.json"]}',
                encoding="utf-8",
            )

            self.assertEqual(load_replay_share_index(Path(directory)), ())

    def test_last_replay_share_bundle_returns_none_without_replay(self) -> None:
        root = Path(__file__).parent.parent

        self.assertIsNone(build_last_replay_share_bundle(root / "content", GameProgress()))

    def test_highlight_clips_are_built_from_key_moments(self) -> None:
        clips = create_highlight_clips("replay-1", self._timeline(), window_s=6.0)

        self.assertEqual(len(clips), 4)
        self.assertEqual(clips[0].clip_id, "replay-1-clip-1")
        self.assertEqual(clips[0].start_s, 0.0)
        self.assertEqual(clips[2].label, "final stretch")
        with self.assertRaises(ValueError):
            create_highlight_clips("replay-1", self._timeline(), window_s=0.0)

    def test_photo_finish_orders_by_rank_then_distance(self) -> None:
        frame = create_photo_finish_frame("replay-1", self._state())

        self.assertEqual(frame.timestamp_s, 71.5)
        self.assertEqual([item[0] for item in frame.runner_distances], ["copper_gate", "ember_stride"])

    def test_invalid_values_are_rejected(self) -> None:
        replay = self._replay()
        with self.assertRaises(ValueError):
            create_replay_summary("", "Title", 1.0, replay)
        with self.assertRaises(ValueError):
            export_race_text(create_replay_summary("id", "Title", 1.0, replay), ())
        with self.assertRaises(ValueError):
            create_shared_ghost_file("", replay, "Ghost")


if __name__ == "__main__":
    unittest.main()
