import unittest
from pathlib import Path

from horse_racing_game.audio.audio_backend import RelativeAudioPosition
from horse_racing_game.audio.fake_backend import FakeAudioBackend
from horse_racing_game.audio.opponent_spatial_audio import OpponentSpatialAudio, OpponentSpatialAudioConfig
from horse_racing_game.audio.sound_catalog import SoundAsset, SoundCatalog
from horse_racing_game.audio.spatial_mixer import SpatialAudioMixer
from horse_racing_game.domain.track import Track, TrackSegment
from horse_racing_game.domain.weather import Weather
from horse_racing_game.simulation.race_state import RaceState, RunnerState


SOUND_IDS = (
    "horse_walk_loop_stable_yard",
    "horse_trot_loop_turf",
    "horse_canter_loop_turf",
    "horse_player_gallop_loop_turf",
    "horse_gallop_loop_dirt",
    "horse_gallop_loop_mud",
    "horse_gallop_loop_sand",
    "horse_gallop_loop_inner_rail_close",
)


def _catalog(sound_ids: tuple[str, ...] = SOUND_IDS) -> SoundCatalog:
    return SoundCatalog(
        tuple(SoundAsset(sound_id, Path(f"assets/{sound_id}.mp3"), "test", "test", "horse", True, 0.5, 40) for sound_id in sound_ids)
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
            TrackSegment(0.0, 300.0, "none", 0.0, 0.0, "straight"),
            TrackSegment(300.0, 700.0, "left", 0.5, 0.0, "inner_rail_left"),
            TrackSegment(700.0, 1000.0, "none", 0.0, 0.0, "finish"),
        ),
    )


def _weather(weather_id: str = "clear") -> Weather:
    return Weather(weather_id, weather_id.title(), 1.0, 1.0, 1.0, None)


def _runner(
    runner_id: str,
    distance_m: float,
    lateral_position: float,
    speed_mps: float = 13.0,
    stamina: float = 80.0,
    is_player: bool = False,
) -> RunnerState:
    return RunnerState(runner_id, runner_id.title(), distance_m, lateral_position, speed_mps, stamina, 1.0, is_player, 1)


def _state(*runners: RunnerState, finished: bool = False) -> RaceState:
    return RaceState(12.0, runners, finished)

class CapturingBackend(FakeAudioBackend):
    def __init__(self) -> None:
        super().__init__()
        self.loop_sound_ids: list[str] = []

    def update_loop_3d(self, sound_id: str, position: RelativeAudioPosition, volume: float, loop_id: str | None = None) -> None:
        self.loop_sound_ids.append(sound_id)
        super().update_loop_3d(sound_id, position, volume, loop_id=loop_id)


class SpatialAudioMixerTests(unittest.TestCase):
    def test_lateral_position_shapes_left_and_right_channels(self) -> None:
        mixer = SpatialAudioMixer()

        left = mixer.mix(RelativeAudioPosition(forward_m=8.0, right_m=-2.3), 0.8)
        right = mixer.mix(RelativeAudioPosition(forward_m=8.0, right_m=2.3), 0.8)

        self.assertGreater(left.left, left.right)
        self.assertGreater(right.right, right.left)

    def test_distance_and_rear_position_reduce_gain(self) -> None:
        mixer = SpatialAudioMixer(hearing_range_m=45.0)

        near = mixer.mix(RelativeAudioPosition(forward_m=3.0, right_m=0.0), 0.8)
        far = mixer.mix(RelativeAudioPosition(forward_m=45.0, right_m=0.0), 0.8)
        rear = mixer.mix(RelativeAudioPosition(forward_m=-3.0, right_m=0.0), 0.8)

        self.assertGreater(near.gain, far.gain)
        self.assertGreater(near.gain, rear.gain)


class OpponentSpatialAudioTests(unittest.TestCase):
    def test_nearby_opponents_update_positioned_loop_sources(self) -> None:
        backend = FakeAudioBackend()
        audio = OpponentSpatialAudio(backend, _catalog(), _track(), _weather())
        player = _runner("player", 100.0, 1.15, is_player=True)
        rival_left = _runner("rival_left", 108.0, 0.0)
        rival_right = _runner("rival_right", 92.0, 2.3)

        audio.update(_state(player, rival_left, rival_right))

        calls = [call for call in backend.calls if call.method == "update_loop_3d"]
        self.assertEqual([call.sound_id for call in calls], ["opponent:rival_left", "opponent:rival_right"])
        self.assertAlmostEqual(calls[0].position.forward_m, 8.0)
        self.assertAlmostEqual(calls[0].position.right_m, -1.15)
        self.assertAlmostEqual(calls[1].position.forward_m, -8.0)
        self.assertAlmostEqual(calls[1].position.right_m, 1.15)

    def test_sound_pool_limits_active_opponents_and_stops_stale_loops(self) -> None:
        backend = FakeAudioBackend()
        audio = OpponentSpatialAudio(
            backend,
            _catalog(),
            _track(),
            _weather(),
            OpponentSpatialAudioConfig(max_sources=1, hearing_range_m=25.0),
        )
        player = _runner("player", 100.0, 1.15, is_player=True)
        near = _runner("near", 103.0, 1.15)
        farther = _runner("farther", 118.0, 1.15)

        audio.update(_state(player, near, farther))
        audio.update(_state(player, _runner("near", 180.0, 1.15), farther))

        updates = [call.sound_id for call in backend.calls if call.method == "update_loop_3d"]
        stops = [call.sound_id for call in backend.calls if call.method == "stop_sound"]
        self.assertEqual(updates, ["opponent:near", "opponent:farther"])
        self.assertIn("opponent:near", stops)

    def test_finished_race_stops_active_opponent_loops(self) -> None:
        backend = FakeAudioBackend()
        audio = OpponentSpatialAudio(backend, _catalog(), _track(), _weather())
        player = _runner("player", 100.0, 1.15, is_player=True)
        rival = _runner("rival", 103.0, 1.15)

        audio.update(_state(player, rival))
        audio.update(_state(player, rival, finished=True))

        self.assertIn(("stop_sound", "opponent:rival"), [(call.method, call.sound_id) for call in backend.calls])

    def test_surface_weather_and_rail_select_matching_gallop_loop(self) -> None:
        player = _runner("player", 100.0, 1.15, is_player=True)
        rail_player = _runner("player", 316.0, 1.15, is_player=True)
        dirt_backend = CapturingBackend()
        rain_backend = CapturingBackend()
        rail_backend = CapturingBackend()

        OpponentSpatialAudio(dirt_backend, _catalog(), _track("dirt"), _weather()).update(_state(player, _runner("dirt", 104.0, 1.15)))
        OpponentSpatialAudio(rain_backend, _catalog(), _track("turf"), _weather("rain")).update(_state(player, _runner("rain", 104.0, 1.15)))
        OpponentSpatialAudio(rail_backend, _catalog(), _track("turf"), _weather()).update(_state(rail_player, _runner("rail", 320.0, 1.15)))

        self.assertEqual(dirt_backend.loop_sound_ids, ["horse_gallop_loop_dirt"])
        self.assertEqual(rain_backend.loop_sound_ids, ["horse_gallop_loop_mud"])
        self.assertEqual(rail_backend.loop_sound_ids, ["horse_gallop_loop_inner_rail_close"])


if __name__ == "__main__":
    unittest.main()


