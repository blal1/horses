import unittest
from pathlib import Path
from types import SimpleNamespace

import pygame

from horse_racing_game.audio.fake_backend import FakeAudioBackend
from horse_racing_game.audio.sound_catalog import SoundAsset, SoundCatalog
from horse_racing_game.simulation.race_events import RaceEvent
from horse_racing_game.simulation.race_state import RaceState, RunnerState
from horse_racing_game.ui.pygame_game import PygameRaceGame


class PygameGameInputTests(unittest.TestCase):
    def test_jump_and_duck_keydown_are_buffered_briefly(self) -> None:
        game = PygameRaceGame.__new__(PygameRaceGame)
        game._held_keys = set()
        game._jump_buffer_s = 0.0
        game._duck_buffer_s = 0.0
        game._paused = False

        running, next_action = game._handle_keydown(pygame.K_j, True, "quit")
        self.assertTrue(running)
        self.assertEqual(next_action, "quit")
        self.assertGreater(game._jump_buffer_s, 0.0)

        game._handle_keydown(pygame.K_k, True, "quit")
        self.assertGreater(game._duck_buffer_s, 0.0)

        game._tick_action_buffers(1.0)
        self.assertEqual(game._jump_buffer_s, 0.0)
        self.assertEqual(game._duck_buffer_s, 0.0)

    def test_held_arrow_keys_drive_race_command(self) -> None:
        game = PygameRaceGame.__new__(PygameRaceGame)
        game._held_keys = {pygame.K_UP, pygame.K_LEFT}
        game._jump_buffer_s = 0.0
        game._duck_buffer_s = 0.0

        command = game._poll_command()

        self.assertEqual(command.throttle_delta, 1.0)
        self.assertEqual(command.lateral_delta, -1.0)

    def test_azerty_zqsd_keys_drive_race_command(self) -> None:
        game = PygameRaceGame.__new__(PygameRaceGame)
        game._held_keys = {pygame.K_z, pygame.K_q}
        game._jump_buffer_s = 0.0
        game._duck_buffer_s = 0.0

        command = game._poll_command()

        self.assertEqual(command.throttle_delta, 1.0)
        self.assertEqual(command.lateral_delta, -1.0)

    def test_q_is_left_control_not_quit_in_race(self) -> None:
        game = PygameRaceGame.__new__(PygameRaceGame)
        game._held_keys = set()
        game._jump_buffer_s = 0.0
        game._duck_buffer_s = 0.0
        game._paused = False

        running, next_action = game._handle_keydown(pygame.K_q, True, "quit")

        self.assertTrue(running)
        self.assertEqual(next_action, "quit")
        self.assertIn(pygame.K_q, game._held_keys)

    def test_keyup_releases_held_control(self) -> None:
        game = PygameRaceGame.__new__(PygameRaceGame)
        game._held_keys = {pygame.K_UP}

        game._handle_keyup(pygame.K_UP)

        self.assertNotIn(pygame.K_UP, game._held_keys)

    def test_action_keys_play_immediate_audio_cues(self) -> None:
        backend = FakeAudioBackend()
        game = PygameRaceGame.__new__(PygameRaceGame)
        game._held_keys = set()
        game._jump_buffer_s = 0.0
        game._duck_buffer_s = 0.0
        game._paused = False
        game._services = SimpleNamespace(
            audio_backend=backend,
            sound_catalog=SoundCatalog(
                (
                    _sound("horse_push_surge"),
                    _sound("horse_jump_takeoff"),
                    _sound("horse_lane_change_hoof_sweep"),
                )
            ),
        )

        game._handle_keydown(pygame.K_SPACE, True, "quit")
        game._handle_keydown(pygame.K_j, True, "quit")
        game._handle_keydown(pygame.K_k, True, "quit")

        self.assertEqual(
            [call.sound_id for call in backend.calls],
            ["horse_push_surge", "horse_jump_takeoff", "horse_lane_change_hoof_sweep"],
        )

    def test_continuous_audio_delegates_player_state(self) -> None:
        game = PygameRaceGame.__new__(PygameRaceGame)
        game._project_root = Path(".")
        game._audio_duck_s = 0.0
        game._mix_profile = SimpleNamespace(music_volume=0.5)
        recorder = _ContinuousAudioSpy()
        game._continuous_audio = recorder

        game._update_continuous_audio(_state(speed_mps=5.0), 0.1)

        self.assertEqual(recorder.updates, [(5.0, False)])

    def test_finished_race_is_passed_to_continuous_audio(self) -> None:
        game = PygameRaceGame.__new__(PygameRaceGame)
        game._project_root = Path(".")
        game._audio_duck_s = 0.0
        game._mix_profile = SimpleNamespace(music_volume=0.5)
        recorder = _ContinuousAudioSpy()
        game._continuous_audio = recorder

        game._update_continuous_audio(_state(speed_mps=0.0, finished=True), 0.1)

        self.assertEqual(recorder.updates, [(0.0, True)])

    def test_priority_events_trigger_music_ducking(self) -> None:
        game = PygameRaceGame.__new__(PygameRaceGame)
        game._audio_duck_s = 0.0

        game._duck_audio_for_priority_events((RaceEvent("obstacle_radar", 58, 1.0, "cone", {"forward_m": 20.0}),))

        self.assertGreater(game._audio_duck_s, 0.0)

    def test_countdown_plays_when_available(self) -> None:
        backend = FakeAudioBackend()
        game = PygameRaceGame.__new__(PygameRaceGame)
        game._services = SimpleNamespace(
            audio_backend=backend,
            sound_catalog=SoundCatalog((_sound("race_countdown_three_beeps"),)),
        )

        game._play_countdown()

        self.assertEqual(backend.calls[0].sound_id, "race_countdown_three_beeps")
    def test_looping_weather_ambient_uses_loop_channel(self) -> None:
        backend = FakeAudioBackend()
        game = PygameRaceGame.__new__(PygameRaceGame)
        game._training_mode = False
        game._ambient_sound_id = None
        game._mix_profile = SimpleNamespace(ambient_volume=0.42)
        game._services = SimpleNamespace(
            audio_backend=backend,
            weather=SimpleNamespace(ambient_sound_id="wind_loop"),
            sound_catalog=SoundCatalog((_sound("wind_loop", loop=True),)),
        )

        game._play_ambient()
        game._stop_ambient()

        self.assertEqual([(call.method, call.sound_id) for call in backend.calls], [("play_loop", "wind_loop"), ("stop_sound", "wind_loop")])

    def test_non_looping_weather_ambient_remains_one_shot(self) -> None:
        backend = FakeAudioBackend()
        game = PygameRaceGame.__new__(PygameRaceGame)
        game._training_mode = False
        game._ambient_sound_id = None
        game._mix_profile = SimpleNamespace(ambient_volume=0.42)
        game._services = SimpleNamespace(
            audio_backend=backend,
            weather=SimpleNamespace(ambient_sound_id="wind_hit"),
            sound_catalog=SoundCatalog((_sound("wind_hit", loop=False),)),
        )

        game._play_ambient()

        self.assertEqual([(call.method, call.sound_id) for call in backend.calls], [("play_2d", "wind_hit")])
        self.assertIsNone(game._ambient_sound_id)


class _ContinuousAudioSpy:
    def __init__(self) -> None:
        self.updates = []

    def update(self, player: RunnerState, is_finished: bool) -> None:
        self.updates.append((player.speed_mps, is_finished))

def _sound(sound_id: str, loop: bool = False) -> SoundAsset:
    return SoundAsset(
        sound_id=sound_id,
        path=Path(f"assets/{sound_id}.mp3"),
        source="test",
        license="test",
        category="horse",
        loop=loop,
        default_volume=0.5,
        priority=40,
    )


def _state(speed_mps: float, finished: bool = False) -> RaceState:
    return RaceState(
        elapsed_s=1.0,
        runners=(RunnerState("ember_stride", "Ember Stride", 10.0, 0.0, speed_mps, 80.0, 1.0, True, 1),),
        is_finished=finished,
    )


if __name__ == "__main__":
    unittest.main()


