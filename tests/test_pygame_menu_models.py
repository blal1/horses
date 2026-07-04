import unittest
from pathlib import Path

import pygame

from horse_racing_game.audio.mix_profile import MIX_PROFILES
from horse_racing_game.content.loaders import load_horses, load_stables, load_tracks, load_weather
from horse_racing_game.ui.pygame_menu import PygameMainMenu
from horse_racing_game.ui.menu_models import PygameMenuState


class PygameMenuStateTests(unittest.TestCase):
    def test_menu_cycles_horse_and_track_options(self) -> None:
        root = Path(__file__).parent.parent
        horses = tuple(horse for horse in load_horses(root / "content" / "horses.json") if horse.role == "player")
        tracks = load_tracks(root / "content" / "tracks.json")
        state = PygameMenuState(horses, tracks)

        state.cycle_current_option(1)
        self.assertEqual(state.selected_horse_index, 1)

        state.move_row(1)
        state.cycle_current_option(1)
        self.assertEqual(state.selected_track_index, 1)

        selection = state.selection()
        self.assertEqual(selection.player_horse_id, horses[1].horse_id)
        self.assertEqual(selection.track_id, tracks[1].track_id)
        self.assertEqual(selection.mode, "race")

        tutorial_selection = state.selection("tutorial")
        self.assertEqual(tutorial_selection.mode, "tutorial")

    def test_menu_rows_wrap(self) -> None:
        root = Path(__file__).parent.parent
        horses = tuple(horse for horse in load_horses(root / "content" / "horses.json") if horse.role == "player")
        tracks = load_tracks(root / "content" / "tracks.json")
        state = PygameMenuState(horses, tracks)

        state.move_row(-1)
        self.assertEqual(state.selected_row, 19)
        state.move_row(1)
        self.assertEqual(state.selected_row, 0)

    def test_menu_can_restore_last_selection_by_id(self) -> None:
        root = Path(__file__).parent.parent
        horses = tuple(horse for horse in load_horses(root / "content" / "horses.json") if horse.role == "player")
        tracks = load_tracks(root / "content" / "tracks.json")
        weather_options = load_weather(root / "content" / "weather.json")
        stables = load_stables(root / "content" / "stables.json")
        state = PygameMenuState(horses, tracks, weather_options, MIX_PROFILES, stables)

        state.select_ids(
            horses[-1].horse_id,
            tracks[-1].track_id,
            weather_options[-1].weather_id,
            MIX_PROFILES[-1].profile_id,
            stables[-1].stable_id,
            "elite",
        )

        self.assertEqual(state.selected_horse, horses[-1])
        self.assertEqual(state.selected_track, tracks[-1])
        self.assertEqual(state.selected_weather, weather_options[-1])
        self.assertEqual(state.selected_audio_profile, MIX_PROFILES[-1])
        self.assertEqual(state.selected_stable, stables[-1])
        self.assertEqual(state.selected_difficulty.tier_id, "elite")

    def test_enter_is_contextual_not_always_start(self) -> None:
        root = Path(__file__).parent.parent
        pygame.init()
        try:
            menu = PygameMainMenu(root / "content", root)

            result = menu._handle_keydown(pygame.K_RETURN)
            self.assertIsNone(result.selection)
            self.assertEqual(menu._state.selected_row, 0)
            self.assertEqual(menu._state.selected_horse_index, 1)

            menu._handle_keydown(pygame.K_DOWN)
            self.assertEqual(menu._state.selected_row, 1)
            result = menu._handle_keydown(pygame.K_RETURN)
            self.assertIsNone(result.selection)
            self.assertEqual(menu._state.selected_track_index, 1)

            menu._handle_keydown(pygame.K_DOWN)
            menu._handle_keydown(pygame.K_DOWN)
            menu._handle_keydown(pygame.K_DOWN)
            menu._handle_keydown(pygame.K_DOWN)
            self.assertEqual(menu._state.selected_row, 5)
            result = menu._handle_keydown(pygame.K_RETURN)
            self.assertIsNone(result.selection)
            self.assertEqual(menu._state.selected_difficulty.tier_id, "elite")

            menu._handle_keydown(pygame.K_DOWN)
            self.assertEqual(menu._state.selected_row, 6)
            result = menu._handle_keydown(pygame.K_RETURN)
            self.assertIsNotNone(result.selection)
            self.assertEqual(result.selection.mode, "race")
        finally:
            pygame.quit()

    def test_r_repeats_selection_without_leaving_menu(self) -> None:
        from horse_racing_game.ui.pygame_menu import _MenuAction

        root = Path(__file__).parent.parent
        pygame.init()
        try:
            menu = PygameMainMenu(root / "content", root)
            menu._handle_keydown(pygame.K_DOWN)
            row_before = menu._state.selected_row
            result = menu._handle_keydown(pygame.K_r)
            self.assertIs(result, _MenuAction.CONTINUE)
            self.assertEqual(menu._state.selected_row, row_before)
        finally:
            pygame.quit()

    def test_wasd_navigation_matches_arrows(self) -> None:
        root = Path(__file__).parent.parent
        pygame.init()
        try:
            menu = PygameMainMenu(root / "content", root)
            menu._handle_keydown(pygame.K_s)
            self.assertEqual(menu._state.selected_row, 1)
            menu._handle_keydown(pygame.K_d)
            self.assertEqual(menu._state.selected_track_index, 1)
            menu._handle_keydown(pygame.K_w)
            self.assertEqual(menu._state.selected_row, 0)
            menu._handle_keydown(pygame.K_a)
            self.assertEqual(menu._state.selected_horse_index, len(menu._state.horses) - 1)
        finally:
            pygame.quit()

    def test_selection_text_describes_current_menu_row(self) -> None:
        root = Path(__file__).parent.parent
        pygame.init()
        try:
            menu = PygameMainMenu(root / "content", root)

            self.assertIn("Horse.", menu._selection_text())
            self.assertIn(menu._state.selected_horse.name, menu._selection_text())

            menu._state.selected_row = 1
            self.assertIn("Track.", menu._selection_text())
            self.assertIn(menu._state.selected_track.name, menu._selection_text())

            menu._state.selected_row = 2
            self.assertIn("Weather.", menu._selection_text())

            menu._state.selected_row = 3
            self.assertIn("Audio profile.", menu._selection_text())

            menu._state.selected_row = 4
            self.assertIn("Stable.", menu._selection_text())

            menu._state.selected_row = 5
            self.assertEqual(menu._selection_text(), "Difficulty. Pro. Press enter to change.")

            menu._state.selected_row = 6
            self.assertEqual(menu._selection_text(), "Quick race. Press enter to launch.")

            menu._state.selected_row = 7
            self.assertEqual(menu._selection_text(), "Tutorial. Press enter for guided controls.")

            menu._state.selected_row = 8
            self.assertEqual(menu._selection_text(), "Training. Press enter to improve the selected horse.")

            menu._state.selected_row = 9
            self.assertEqual(menu._selection_text(), "Career. Press enter to open race, training, and rest choices.")

            menu._state.selected_row = 10
            self.assertEqual(menu._selection_text(), "Obstacle lab. Press enter to test dodge, jump, and duck obstacles.")

            menu._state.selected_row = 11
            self.assertEqual(menu._selection_text(), "Time trial. Press enter to race the clock and save your best time.")

            menu._state.selected_row = 12
            self.assertEqual(menu._selection_text(), "Ghost race. Press enter to race against the last saved replay.")

            menu._state.selected_row = 13
            self.assertEqual(menu._selection_text(), "Multiplayer. Press enter for local duel or online lobby.")

            menu._state.selected_row = 14
            self.assertEqual(menu._selection_text(), "Replay. Press enter to hear the last race again.")

            menu._state.selected_row = 15
            self.assertEqual(menu._selection_text(), "Track editor. Press enter to build a custom audio track.")

            menu._state.selected_row = 16
            self.assertEqual(menu._selection_text(), "Profile. Press enter to view identity, wallet, and unlocks.")

            menu._state.selected_row = 17
            self.assertEqual(menu._selection_text(), "Statistics. Press enter to view season stats and standings.")

            menu._state.selected_row = 18
            self.assertEqual(menu._selection_text(), "Special events. Press enter to open scenario challenges.")

            menu._state.selected_row = 19
            self.assertEqual(menu._selection_text(), "Quit. Press enter to exit.")
        finally:
            pygame.quit()

    def test_training_row_starts_training_mode(self) -> None:
        root = Path(__file__).parent.parent
        pygame.init()
        try:
            menu = PygameMainMenu(root / "content", root)
            menu._state.selected_row = 8

            result = menu._handle_keydown(pygame.K_RETURN)

            self.assertIsNotNone(result.selection)
            self.assertEqual(result.selection.mode, "training")
        finally:
            pygame.quit()

    def test_career_row_starts_career_mode(self) -> None:
        root = Path(__file__).parent.parent
        pygame.init()
        try:
            menu = PygameMainMenu(root / "content", root)
            menu._state.selected_row = 9

            result = menu._handle_keydown(pygame.K_RETURN)

            self.assertIsNotNone(result.selection)
            self.assertEqual(result.selection.mode, "career")
        finally:
            pygame.quit()

    def test_statistics_row_starts_stats_mode(self) -> None:
        root = Path(__file__).parent.parent
        pygame.init()
        try:
            menu = PygameMainMenu(root / "content", root)
            menu._state.selected_row = 17

            result = menu._handle_keydown(pygame.K_RETURN)

            self.assertIsNotNone(result.selection)
            self.assertEqual(result.selection.mode, "stats")
        finally:
            pygame.quit()

    def test_profile_row_starts_profile_mode(self) -> None:
        root = Path(__file__).parent.parent
        pygame.init()
        try:
            menu = PygameMainMenu(root / "content", root)
            menu._state.selected_row = 16

            result = menu._handle_keydown(pygame.K_RETURN)

            self.assertIsNotNone(result.selection)
            self.assertEqual(result.selection.mode, "profile")
        finally:
            pygame.quit()

    def test_track_editor_row_starts_editor_mode(self) -> None:
        root = Path(__file__).parent.parent
        pygame.init()
        try:
            menu = PygameMainMenu(root / "content", root)
            menu._state.selected_row = 15

            result = menu._handle_keydown(pygame.K_RETURN)

            self.assertIsNotNone(result.selection)
            self.assertEqual(result.selection.mode, "track_editor")
        finally:
            pygame.quit()

    def test_special_events_row_starts_special_event_mode(self) -> None:
        root = Path(__file__).parent.parent
        pygame.init()
        try:
            menu = PygameMainMenu(root / "content", root)
            menu._state.selected_row = 18

            result = menu._handle_keydown(pygame.K_RETURN)

            self.assertIsNotNone(result.selection)
            self.assertEqual(result.selection.mode, "special_event")
        finally:
            pygame.quit()

    def test_obstacle_lab_row_starts_obstacle_lab_mode(self) -> None:
        root = Path(__file__).parent.parent
        pygame.init()
        try:
            menu = PygameMainMenu(root / "content", root)
            menu._state.selected_row = 10

            result = menu._handle_keydown(pygame.K_RETURN)

            self.assertIsNotNone(result.selection)
            self.assertEqual(result.selection.mode, "obstacle_lab")
        finally:
            pygame.quit()

    def test_replay_row_starts_replay_mode(self) -> None:
        root = Path(__file__).parent.parent
        pygame.init()
        try:
            menu = PygameMainMenu(root / "content", root)
            menu._state.selected_row = 14

            result = menu._handle_keydown(pygame.K_RETURN)

            self.assertIsNotNone(result.selection)
            self.assertEqual(result.selection.mode, "replay")
        finally:
            pygame.quit()

    def test_multiplayer_row_starts_multiplayer_mode(self) -> None:
        root = Path(__file__).parent.parent
        pygame.init()
        try:
            menu = PygameMainMenu(root / "content", root)
            menu._state.selected_row = 13

            result = menu._handle_keydown(pygame.K_RETURN)

            self.assertIsNotNone(result.selection)
            self.assertEqual(result.selection.mode, "multiplayer")
        finally:
            pygame.quit()

    def test_time_trial_and_ghost_rows_start_modes(self) -> None:
        root = Path(__file__).parent.parent
        pygame.init()
        try:
            menu = PygameMainMenu(root / "content", root)
            menu._state.selected_row = 11

            result = menu._handle_keydown(pygame.K_RETURN)

            self.assertIsNotNone(result.selection)
            self.assertEqual(result.selection.mode, "time_trial")

            menu._state.selected_row = 12
            result = menu._handle_keydown(pygame.K_RETURN)

            self.assertIsNotNone(result.selection)
            self.assertEqual(result.selection.mode, "ghost_race")
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
