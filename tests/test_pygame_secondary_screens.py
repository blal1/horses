import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from horse_racing_game.app.progress import GameProgress
from horse_racing_game.app.progress import load_progress
from horse_racing_game.app.progress import record_online_lobby_settings
from horse_racing_game.app.profile import load_player_profile
from horse_racing_game.app.replay import build_replay, replay_to_dict
from horse_racing_game.app.config import AppConfig
from horse_racing_game.app.network import InMemoryLockstepTransport
from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.ui.menu_models import MenuSelection
from horse_racing_game.ui.pygame_career_hub import PygameCareerHubScreen
from horse_racing_game.ui.pygame_career_result import PygameCareerResultScreen
from horse_racing_game.ui.pygame_online_lobby import OnlineLobbyResult, PygameOnlineLobbyScreen
from horse_racing_game.ui.pygame_profile import PygameProfileScreen
from horse_racing_game.ui.pygame_replay import PygameReplayScreen
from horse_racing_game.ui.pygame_stats import PygameStatsScreen
from horse_racing_game.ui.pygame_track_editor import FIELD_NAMES, PygameTrackEditorScreen


class PygameSecondaryScreenTests(unittest.TestCase):
    def setUp(self) -> None:
        pygame.init()
        self.root = Path(__file__).parent.parent
        self.fonts = (
            pygame.font.Font(None, 52),
            pygame.font.Font(None, 28),
            pygame.font.Font(None, 22),
        )

    def tearDown(self) -> None:
        pygame.quit()

    def test_replay_screen_defaults_when_no_replay_and_draws(self) -> None:
        screen = PygameReplayScreen(self.root / "content", self.root, GameProgress())
        surface = pygame.Surface((980, 640))

        screen._draw(surface, *self.fonts)

        self.assertIn("No replay is available", screen._lines[0])
        self.assertNotEqual(surface.get_at((60, 44))[:3], (0, 0, 0))

    def test_replay_screen_steps_final_stretch_and_key_moment(self) -> None:
        commands = tuple(RaceCommand(throttle_delta=0.8, push_requested=index > 200) for index in range(500))
        replay = replay_to_dict(build_replay(AppConfig(content_root=self.root / "content", tick_hz=4), commands))
        screen = PygameReplayScreen(self.root / "content", self.root, GameProgress(last_replay=replay))
        surface = pygame.Surface((980, 640))

        self.assertTrue(screen._timeline.has_events)
        self.assertTrue(screen._handle_key(pygame.K_RIGHT))
        self.assertFalse(screen._playing)
        self.assertTrue(screen._handle_key(pygame.K_f))
        self.assertTrue(screen._handle_key(pygame.K_r))
        screen._draw(surface, *self.fonts)

        self.assertNotEqual(surface.get_at((60, 44))[:3], (0, 0, 0))

    def test_replay_screen_exports_share_files(self) -> None:
        commands = tuple(RaceCommand(throttle_delta=0.8, push_requested=index > 200) for index in range(500))
        replay = replay_to_dict(build_replay(AppConfig(content_root=self.root / "content", tick_hz=4), commands))
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            screen = PygameReplayScreen(
                self.root / "content",
                project_root,
                GameProgress(last_replay=replay, last_replay_lines=("Replay line one.",)),
            )

            self.assertTrue(screen._handle_key(pygame.K_s))

            share_dir = project_root / "save" / "replay_shares"
            self.assertTrue((share_dir / "last-replay-manifest.json").exists())
            self.assertIn("Exported 7 files", screen._share_status)

            refreshed = PygameReplayScreen(
                self.root / "content",
                project_root,
                GameProgress(last_replay=replay, last_replay_lines=("Replay line one.",)),
            )
            self.assertIn("1 saved share", refreshed._share_status)

    def test_online_lobby_local_host_join_and_draw(self) -> None:
        host_calls: list[tuple[str, int, object | None, float]] = []
        connect_calls: list[tuple[str, int, object | None, float]] = []

        def host_factory(host: str, port: int, handshake=None, countdown_s: float = 0.0):
            host_calls.append((host, port, handshake, countdown_s))
            return InMemoryLockstepTransport()

        def connect_factory(host: str, port: int, handshake=None, countdown_s: float = 0.0):
            connect_calls.append((host, port, handshake, countdown_s))
            return InMemoryLockstepTransport()

        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            record_online_lobby_settings(project_root, "ROOM42", "127.0.0.1", 45678, "host", True)
            lobby = PygameOnlineLobbyScreen(
                self.root / "content",
                project_root,
                host_factory=host_factory,
                connect_factory=connect_factory,
            )
            surface = pygame.Surface((980, 640))

            self.assertEqual(lobby._activate_row(), OnlineLobbyResult.local())
            initial_ready = lobby._ready
            lobby._selected_row = 6
            lobby._activate_row()
            self.assertNotEqual(lobby._ready, initial_ready)
            lobby._selected_row = 7
            lobby._activate_row()
            self.assertEqual(lobby._selected_row, 1)
            self.assertEqual(lobby._room_code, lobby._progress.last_online_room_code)
            room_code = lobby._room_code
            lobby._selected_row = 3
            lobby._activate_row()
            self.assertNotEqual(lobby._room_code, room_code)
            lobby._selected_row = 1
            lobby._start_connection("host")
            assert lobby._connection_thread is not None
            lobby._connection_thread.join(timeout=1.0)
            host_result = lobby._poll_connection()
            self.assertEqual(host_result.session.local_peer_id, "host")
            self.assertEqual(host_calls[-1][2].room_code, lobby._room_code)
            self.assertTrue(host_calls[-1][2].is_ready)
            self.assertEqual(host_calls[-1][3], lobby._start_countdown_s)

            lobby._selected_row = 2
            lobby._start_connection("guest")
            assert lobby._connection_thread is not None
            lobby._connection_thread.join(timeout=1.0)
            guest_result = lobby._poll_connection()
            self.assertEqual(guest_result.session.local_peer_id, "guest")
            self.assertEqual(connect_calls[-1][2].room_code, lobby._room_code)
            self.assertTrue(connect_calls[-1][2].is_ready)
            self.assertEqual(connect_calls[-1][3], lobby._start_countdown_s)
            lobby._draw(surface, *self.fonts)

            self.assertNotEqual(surface.get_at((60, 44))[:3], (0, 0, 0))

    def test_stats_screen_lines_spoken_summary_and_draw(self) -> None:
        progress = GameProgress(
            career_points=8,
            career_races_completed=1,
            finished_races=2,
            wins=1,
            podiums=1,
            best_rank=1,
            rival_championship_points={"copper_gate": 5},
            rival_championship_races={"copper_gate": 1},
            last_career_result_summary={"base_reward": 10, "contract_reward": 40, "staff_upkeep": 8, "net_reward": 42},
        )
        screen = PygameStatsScreen(self.root / "content", self.root, progress)
        surface = pygame.Surface((980, 640))

        spoken = screen._spoken_summary()
        stats_lines = screen._stats_lines()
        standing_lines = screen._standing_lines()
        screen._draw(surface, *self.fonts)

        self.assertIn("Statistics.", spoken)
        self.assertTrue(any("Career points: 8" in line for line in stats_lines))
        self.assertTrue(
            any("Last career result: Rewards: base 10 | contract 40 | staff upkeep 8 | net 42." in line for line in stats_lines)
        )
        self.assertTrue(any("You" in line for line in standing_lines))
        self.assertIn("Next race:", screen._next_race_line())
        self.assertNotEqual(surface.get_at((60, 44))[:3], (0, 0, 0))

    def test_career_result_screen_lines_spoken_summary_and_draw(self) -> None:
        progress = GameProgress(
            last_career_result_summary={
                "finished": True,
                "rank": 2,
                "base_reward": 20,
                "contract_reward": 35,
                "staff_upkeep": 8,
                "fatigue_before": 40,
                "fatigue_after": 62,
                "injury_days": 1,
                "net_reward": 47,
                "rewards_balance": 61,
            },
        )
        screen = PygameCareerResultScreen(self.root / "content", self.root, progress)
        surface = pygame.Surface((980, 520))

        lines = screen._lines()
        spoken = screen._spoken_summary()
        screen._draw(surface, *self.fonts)

        self.assertEqual(lines[0], "Career result: rank 2.")
        self.assertIn("Rewards: base 20 | contract 35 | staff upkeep 8 | net 47.", lines)
        self.assertIn("Condition: fatigue 40 to 62 | injury days 1.", lines)
        self.assertIn("Stable consequence: staff upkeep reduced race earnings by 8.", lines)
        self.assertIn("Career result.", spoken)
        self.assertNotEqual(surface.get_at((60, 44))[:3], (0, 0, 0))

    def test_career_result_screen_explains_incomplete_attempt(self) -> None:
        progress = GameProgress(
            last_career_result_summary={
                "finished": False,
                "rank": None,
                "base_reward": 0,
                "contract_reward": 0,
                "staff_upkeep": 0,
                "net_reward": 0,
                "rewards_balance": 14,
            },
        )
        screen = PygameCareerResultScreen(self.root / "content", self.root, progress)

        self.assertEqual(
            screen._lines(),
            ("Career attempt incomplete.", "No career rewards were paid.", "Rewards balance: 14."),
        )

    def test_stats_next_race_complete_after_calendar(self) -> None:
        progress = GameProgress(career_races_completed=99)
        screen = PygameStatsScreen(self.root / "content", self.root, progress)

        self.assertEqual(screen._next_race_line(), "Next championship race: complete")

    def test_profile_screen_claims_reward_equips_items_and_draws(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            screen = PygameProfileScreen(self.root / "content", project_root)
            surface = pygame.Surface((980, 640))

            self.assertTrue(any("Rider:" in line for line in screen._summary_lines()))
            screen._selected_row = 0
            screen._activate_selected()
            screen._selected_row = 1
            self.assertEqual(screen._selected_title(), "rookie_rider")
            screen._cycle_selected(1)
            self.assertEqual(screen._selected_title(), "storm_rider")
            screen._activate_selected()
            screen._selected_row = 2
            self.assertEqual(screen._selected_badge(), "founder")
            screen._activate_selected()
            screen._selected_row = 3
            self.assertEqual(screen._selected_cosmetic(), "red_silks")
            screen._activate_selected()
            screen._draw(surface, *self.fonts)

            loaded = load_player_profile(project_root)
            self.assertEqual(loaded.identity.title_id, "storm_rider")
            self.assertEqual(loaded.identity.badge_ids, ("founder",))
            self.assertEqual(loaded.identity.cosmetic_ids, ("red_silks",))
            self.assertEqual(loaded.economy.wallet.soft_currency, 120)
            self.assertNotEqual(surface.get_at((60, 44))[:3], (0, 0, 0))

    def test_career_hub_enforces_energy_gates_and_draws(self) -> None:
        progress = GameProgress(
            career_races_completed=2,
            career_points=17,
            career_energy=1,
            career_fatigue=42,
            career_rewards=6,
            last_stable_id="oak_lane",
            horse_training_levels={"ember_stride": 3},
        )
        screen = PygameCareerHubScreen(
            self.root / "content",
            self.root,
            progress,
            MenuSelection(
                player_horse_id="ember_stride",
                track_id="ashford_oval",
                stable_id="oak_lane",
                difficulty_id="pro",
                mode="career",
            ),
        )
        surface = pygame.Surface((980, 640))

        self.assertTrue(any("Reputation: 17" in line for line in screen._season_lines()))
        self.assertTrue(any("Contract: Regional Backer" in line for line in screen._season_lines()))
        self.assertTrue(any("Selected contract: Regional Backer | available" in line for line in screen._season_lines()))
        self.assertTrue(any("Projected win net after staff upkeep: 110" in line for line in screen._season_lines()))
        self.assertTrue(any("Condition: moderate fatigue | Injury risk: 19%" in line for line in screen._season_lines()))
        self.assertTrue(any("Funds: 40" in line for line in screen._stable_lines()))
        self.assertTrue(any("Next race upkeep warning: 0 rewards" in line for line in screen._stable_lines()))
        self.assertTrue(any("Rest recovery: +1 energy" in line for line in screen._stable_lines()))
        self.assertTrue(any("Rest health: -20 fatigue | injury -1 day(s)" in line for line in screen._stable_lines()))
        self.assertTrue(any("Training bonus:" in line for line in screen._stable_lines()))
        self.assertIn("Current contract pays 110", screen._selection_text())
        self.assertIn("Staff upkeep will deduct 0", screen._selection_text())
        self.assertIn("injury risk 19 percent", screen._selection_text())
        self.assertIsNotNone(screen._handle_keydown(pygame.K_RETURN))
        screen._selected_row = 1
        self.assertIn("Stable training bonus", screen._selection_text())
        self.assertIsNotNone(screen._handle_keydown(pygame.K_RETURN))
        screen._selected_row = 2
        self.assertIn("Recover 1 energy", screen._selection_text())
        self.assertIsNotNone(screen._handle_keydown(pygame.K_RETURN))
        screen._progress = GameProgress(career_energy=0)
        screen._selected_row = 1
        self.assertIsNone(screen._handle_keydown(pygame.K_RETURN))
        screen._progress = GameProgress(career_energy=2, career_injury_days=1)
        screen._selected_row = 0
        self.assertIsNone(screen._handle_keydown(pygame.K_RETURN))
        screen._selected_row = 1
        self.assertIsNone(screen._handle_keydown(pygame.K_RETURN))
        screen._progress = GameProgress(career_energy=3)
        screen._selected_row = 2
        self.assertIsNone(screen._handle_keydown(pygame.K_RETURN))
        screen._selected_row = 9
        self.assertIsNotNone(screen._handle_keydown(pygame.K_RETURN))
        screen._draw(surface, *self.fonts)

        self.assertNotEqual(surface.get_at((60, 44))[:3], (0, 0, 0))

    def test_career_hub_signs_contract_buys_upgrade_and_hires_staff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            progress = GameProgress(career_points=17, career_rewards=22, podiums=1)
            screen = PygameCareerHubScreen(
                self.root / "content",
                project_root,
                progress,
                MenuSelection(
                    player_horse_id="ember_stride",
                    track_id="ashford_oval",
                    stable_id="oak_lane",
                    difficulty_id="pro",
                    mode="career",
                ),
            )

            screen._selected_row = 4
            self.assertIsNone(screen._handle_keydown(pygame.K_RETURN))
            screen._selected_row = 6
            self.assertIsNone(screen._handle_keydown(pygame.K_RETURN))
            screen._selected_row = 8
            self.assertIsNone(screen._handle_keydown(pygame.K_RETURN))
            saved = load_progress(project_root)

            self.assertEqual(saved.active_career_contract_id, "regional_backer")
            self.assertEqual(saved.stable_upgrade_ids, ("training_ring_1",))
            self.assertEqual(saved.stable_staff_ids, ("assistant_trainer",))
            self.assertEqual(saved.career_rewards, 8)
            self.assertTrue(any("Signed: regional_backer" in line for line in screen._season_lines()))
            self.assertTrue(any("Upgrades: 1 owned" in line for line in screen._stable_lines()))
            self.assertTrue(any("Staff: 1 hired" in line for line in screen._stable_lines()))
            self.assertTrue(any("Training bonus: 1.06" in line for line in screen._stable_lines()))
            self.assertTrue(any("Rest recovery: +1 energy" in line for line in screen._stable_lines()))
            self.assertTrue(any("Next race upkeep warning: 8 rewards" in line for line in screen._stable_lines()))
            screen._selected_row = 0
            self.assertIn("Staff upkeep will deduct 8", screen._selection_text())
            self.assertTrue(any("Projected win net after staff upkeep: 102" in line for line in screen._season_lines()))

    def test_career_hub_cycles_upgrade_and_staff_choices(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            screen = PygameCareerHubScreen(
                self.root / "content",
                project_root,
                GameProgress(career_rewards=30),
                MenuSelection(
                    player_horse_id="ember_stride",
                    track_id="ashford_oval",
                    stable_id="oak_lane",
                    difficulty_id="pro",
                    mode="career",
                ),
            )

            self.assertEqual(screen._selected_upgrade().upgrade_id, "training_ring_1")
            screen._selected_row = 5
            self.assertIsNone(screen._handle_keydown(pygame.K_RETURN))
            self.assertEqual(screen._selected_upgrade().upgrade_id, "recovery_clinic_1")
            self.assertIn("recovery_clinic_1", screen._selection_text())
            screen._selected_row = 6
            self.assertIsNone(screen._handle_keydown(pygame.K_RETURN))

            self.assertEqual(screen._selected_staff_member().staff_id, "assistant_trainer")
            screen._selected_row = 7
            self.assertIsNone(screen._handle_keydown(pygame.K_RETURN))
            self.assertEqual(screen._selected_staff_member().staff_id, "stable_vet")
            self.assertIn("stable_vet", screen._selection_text())
            screen._selected_row = 8
            self.assertIsNone(screen._handle_keydown(pygame.K_RETURN))

            saved = load_progress(project_root)
            self.assertEqual(saved.stable_upgrade_ids, ("recovery_clinic_1",))
            self.assertEqual(saved.stable_staff_ids, ("stable_vet",))
            self.assertEqual(saved.career_rewards, 13)
            self.assertTrue(any("Rest recovery: +3 energy" in line for line in screen._stable_lines()))
            screen._selected_row = 2
            self.assertIn("Recover 3 energy", screen._selection_text())

    def test_career_hub_cycles_available_contracts_before_signing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            screen = PygameCareerHubScreen(
                self.root / "content",
                project_root,
                GameProgress(career_points=17),
                MenuSelection(
                    player_horse_id="ember_stride",
                    track_id="ashford_oval",
                    stable_id="oak_lane",
                    difficulty_id="pro",
                    mode="career",
                ),
            )

            self.assertEqual(screen._selected_contract().contract_id, "regional_backer")
            screen._selected_row = 3
            self.assertIsNone(screen._handle_keydown(pygame.K_RETURN))
            self.assertEqual(screen._selected_contract().contract_id, "elite_syndicate")
            self.assertIn("locked, reputation 28 required", screen._selection_text())
            screen._selected_row = 4
            self.assertIsNone(screen._handle_keydown(pygame.K_RETURN))
            self.assertIsNone(load_progress(project_root).active_career_contract_id)
            screen._selected_row = 3
            self.assertIsNone(screen._handle_keydown(pygame.K_RETURN))
            self.assertEqual(screen._selected_contract().contract_id, "rookie_sponsor")
            self.assertIn("Rookie Feed Co.", screen._selection_text())
            screen._selected_row = 4
            self.assertIsNone(screen._handle_keydown(pygame.K_RETURN))

            self.assertEqual(load_progress(project_root).active_career_contract_id, "rookie_sponsor")

    def test_track_editor_key_flow_preview_save_and_draw(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            content_root = project_root / "content"
            content_root.mkdir()
            for name in ("tracks.json", "sound_manifest.json", "elevenlabs_audio_prompts.json"):
                source = self.root / "content" / name
                if source.exists():
                    (content_root / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

            screen = PygameTrackEditorScreen(content_root, project_root, GameProgress())
            surface = pygame.Surface((980, 640))

            self.assertTrue(screen._handle_key(pygame.K_DOWN, True))
            self.assertEqual(screen._field_index, 1)
            self.assertTrue(screen._handle_key(pygame.K_RIGHT, True))
            self.assertTrue(screen._handle_key(pygame.K_r, True))
            screen._field_index = len(FIELD_NAMES) - 1
            self.assertFalse(screen._handle_key(pygame.K_RETURN, True))
            screen._draw(surface, *self.fonts)

            self.assertEqual(screen.saved_track_id, "custom_audio_track")
            self.assertNotEqual(surface.get_at((60, 44))[:3], (0, 0, 0))

    def test_track_editor_escape_exits(self) -> None:
        screen = PygameTrackEditorScreen(self.root / "content", self.root, GameProgress())

        self.assertFalse(screen._handle_key(pygame.K_ESCAPE, True))


if __name__ == "__main__":
    unittest.main()
