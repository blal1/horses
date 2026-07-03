import unittest
from pathlib import Path

from horse_racing_game.audio.continuous_race_audio import ContinuousRaceAudio
from horse_racing_game.audio.fake_backend import FakeAudioBackend
from horse_racing_game.audio.sound_catalog import SoundAsset, SoundCatalog
from horse_racing_game.domain.track import Track, TrackSegment
from horse_racing_game.domain.weather import Weather
from horse_racing_game.simulation.race_state import RunnerState


SOUND_IDS = (
    "horse_walk_loop_stable_yard",
    "horse_trot_loop_turf",
    "horse_canter_loop_turf",
    "horse_player_gallop_loop_turf",
    "horse_gallop_loop_dirt",
    "horse_gallop_loop_mud",
    "horse_gallop_loop_sand",
    "horse_gallop_loop_inner_rail_close",
    "horse_breath_low_stamina",
    "horse_recover_exhale",
)


def _catalog() -> SoundCatalog:
    return SoundCatalog(
        tuple(SoundAsset(sound_id, Path(f"assets/{sound_id}.mp3"), "test", "test", "horse", True, 0.5, 40) for sound_id in SOUND_IDS)
    )


def _track(surface: str = "turf") -> Track:
    return Track(
        track_id="test_track",
        name="Test Track",
        length_m=1000.0,
        surface=surface,
        lanes=6,
        handedness="left",
        final_stretch_start_m=750.0,
        audio_profile={},
        segments=(
            TrackSegment(0.0, 400.0, "none", 0.0, 0.0, "straight"),
            TrackSegment(400.0, 800.0, "left", 0.5, 0.0, "inner_rail_left"),
            TrackSegment(800.0, 1000.0, "none", 0.0, 0.0, "finish"),
        ),
    )


def _weather(weather_id: str = "clear") -> Weather:
    return Weather(weather_id, weather_id.title(), 1.0, 1.0, 1.0, None)


def _runner(speed_mps: float, stamina: float = 80.0, distance_m: float = 100.0) -> RunnerState:
    return RunnerState("player", "Ember", distance_m, 0.0, speed_mps, stamina, 1.0, True, 1)


class ContinuousRaceAudioTests(unittest.TestCase):
    def test_gait_loop_changes_with_speed(self) -> None:
        backend = FakeAudioBackend()
        audio = ContinuousRaceAudio(backend, _catalog(), _track(), _weather())

        audio.update(_runner(1.0), False)
        audio.update(_runner(5.0), False)
        audio.update(_runner(9.0), False)
        audio.update(_runner(13.0), False)

        self.assertEqual(
            [(call.method, call.sound_id) for call in backend.calls],
            [
                ("play_loop", "horse_walk_loop_stable_yard"),
                ("stop_sound", "horse_walk_loop_stable_yard"),
                ("play_loop", "horse_trot_loop_turf"),
                ("stop_sound", "horse_trot_loop_turf"),
                ("play_loop", "horse_canter_loop_turf"),
                ("stop_sound", "horse_canter_loop_turf"),
                ("play_loop", "horse_player_gallop_loop_turf"),
            ],
        )

    def test_surface_and_rail_specific_gallop_layers(self) -> None:
        backend = FakeAudioBackend()
        dirt_audio = ContinuousRaceAudio(backend, _catalog(), _track("dirt"), _weather())
        rain_audio = ContinuousRaceAudio(backend, _catalog(), _track("turf"), _weather("rain"))
        rail_audio = ContinuousRaceAudio(backend, _catalog(), _track("turf"), _weather())

        dirt_audio.update(_runner(13.0, distance_m=100.0), False)
        rain_audio.update(_runner(13.0, distance_m=100.0), False)
        rail_audio.update(_runner(13.0, distance_m=450.0), False)

        self.assertEqual(backend.calls[0].sound_id, "horse_gallop_loop_dirt")
        self.assertEqual(backend.calls[1].sound_id, "horse_gallop_loop_mud")
        self.assertEqual(backend.calls[2].sound_id, "horse_gallop_loop_inner_rail_close")

    def test_low_stamina_breathing_and_recovery_exhale(self) -> None:
        backend = FakeAudioBackend()
        audio = ContinuousRaceAudio(backend, _catalog(), _track(), _weather())

        audio.update(_runner(12.0, stamina=33.0), False)
        audio.update(_runner(12.0, stamina=42.0), False)
        audio.update(_runner(12.0, stamina=48.0), False)

        self.assertIn(("play_loop", "horse_breath_low_stamina"), [(call.method, call.sound_id) for call in backend.calls])
        self.assertIn(("stop_sound", "horse_breath_low_stamina"), [(call.method, call.sound_id) for call in backend.calls])
        self.assertIn(("play_2d", "horse_recover_exhale"), [(call.method, call.sound_id) for call in backend.calls])

    def test_finish_stops_active_continuous_layers(self) -> None:
        backend = FakeAudioBackend()
        audio = ContinuousRaceAudio(backend, _catalog(), _track(), _weather())

        audio.update(_runner(12.0, stamina=30.0), False)
        audio.update(_runner(12.0, stamina=30.0), True)

        stopped = [call.sound_id for call in backend.calls if call.method == "stop_sound"]
        self.assertIn("horse_player_gallop_loop_turf", stopped)
        self.assertIn("horse_breath_low_stamina", stopped)


if __name__ == "__main__":
    unittest.main()
