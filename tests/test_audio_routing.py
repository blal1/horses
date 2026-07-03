import unittest
from pathlib import Path

from horse_racing_game.audio.audio_engine import AudioEngine
from horse_racing_game.audio.event_cues import SoundCueMap
from horse_racing_game.audio.event_router import AudioEventRouter
from horse_racing_game.audio.fake_backend import FakeAudioBackend
from horse_racing_game.audio.pygame_backend import PygameAudioBackend
from horse_racing_game.audio.audio_backend import RelativeAudioPosition
from horse_racing_game.audio.sound_catalog import SoundAsset, SoundCatalog
from horse_racing_game.content.loaders import load_sound_catalog
from horse_racing_game.simulation.race_events import RaceEvent


class AudioRoutingTests(unittest.TestCase):
    def test_status_event_uses_voice_backend(self) -> None:
        root = Path(__file__).parent.parent
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")
        backend = FakeAudioBackend()
        engine = AudioEngine(AudioEventRouter(catalog, backend))

        engine.render_events(
            (
                RaceEvent(
                    event_type="status_requested",
                    priority=40,
                    timestamp_s=2.0,
                    subject_id="ember_stride",
                    data={"rank": 2, "distance_remaining_m": 1440.0, "stamina": 79.5},
                ),
            )
        )

        self.assertEqual(backend.calls[0].method, "speak")
        self.assertIn("Rank 2", backend.calls[0].text or "")

    def test_turn_entry_apex_and_rail_events_are_spoken(self) -> None:
        root = Path(__file__).parent.parent
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")
        backend = FakeAudioBackend()
        engine = AudioEngine(AudioEventRouter(catalog, backend))

        engine.render_events(
            (
                RaceEvent("turn_entry", 60, 1.0, "ember_stride", {"direction": "left"}),
                RaceEvent("turn_apex", 58, 1.2, "ember_stride", {"direction": "left"}),
                RaceEvent("turn_rail_inside", 52, 1.4, "ember_stride", {"direction": "left"}),
                RaceEvent("turn_too_wide", 70, 1.6, "ember_stride", {"direction": "left"}),
            )
        )

        spoken = [call.text for call in backend.calls if call.method == "speak"]
        self.assertIn("Turn entry left.", spoken)
        self.assertIn("Apex left.", spoken)
        self.assertIn("Inside rail left.", spoken)
        self.assertIn("Too wide left.", spoken)

    def test_pace_state_event_is_spoken(self) -> None:
        root = Path(__file__).parent.parent
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")
        backend = FakeAudioBackend()
        engine = AudioEngine(AudioEventRouter(catalog, backend))

        engine.render_events(
            (
                RaceEvent(
                    event_type="pace_overpushing",
                    priority=36,
                    timestamp_s=2.0,
                    subject_id="ember_stride",
                    data={"pace": 0.91, "speed": 15.2, "stamina": 41.0},
                ),
            )
        )

        self.assertEqual(backend.calls[0].method, "speak")
        self.assertEqual(backend.calls[0].text, "Overpushing.")

    def test_opponent_event_uses_spatial_backend_with_explicit_cue(self) -> None:
        root = Path(__file__).parent.parent
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")
        backend = FakeAudioBackend()
        engine = AudioEngine(AudioEventRouter(catalog, backend))

        engine.render_events(
            (
                RaceEvent(
                    event_type="opponent_approaching",
                    priority=60,
                    timestamp_s=3.0,
                    subject_id="night_rail",
                    data={"forward_m": -4.0, "right_m": 1.0},
                ),
            )
        )

        self.assertEqual(backend.calls[0].method, "play_3d")
        self.assertEqual(backend.calls[0].sound_id, "opponent_approach_right")
        self.assertEqual(backend.calls[0].position.forward_m, -4.0)
        self.assertEqual(backend.calls[0].position.right_m, 1.0)

    def test_repeated_opponent_event_is_throttled_by_subject(self) -> None:
        root = Path(__file__).parent.parent
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")
        backend = FakeAudioBackend()
        engine = AudioEngine(AudioEventRouter(catalog, backend))

        engine.render_events(
            (
                RaceEvent("opponent_approaching", 60, 3.0, "night_rail", {"forward_m": -4.0, "right_m": 1.0}),
                RaceEvent("opponent_approaching", 60, 3.2, "night_rail", {"forward_m": -3.0, "right_m": 1.0}),
                RaceEvent("opponent_approaching", 60, 4.1, "night_rail", {"forward_m": -2.0, "right_m": 1.0}),
            )
        )

        self.assertEqual(len(backend.calls), 2)
        self.assertEqual(backend.calls[0].position.forward_m, -4.0)
        self.assertEqual(backend.calls[1].position.forward_m, -2.0)

    def test_repeated_status_event_is_throttled(self) -> None:
        root = Path(__file__).parent.parent
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")
        backend = FakeAudioBackend()
        engine = AudioEngine(AudioEventRouter(catalog, backend))

        engine.render_events(
            (
                RaceEvent("status_requested", 40, 1.0, "ember_stride", {"rank": 1, "distance_remaining_m": 100.0, "stamina": 50.0}),
                RaceEvent("status_requested", 40, 1.2, "ember_stride", {"rank": 1, "distance_remaining_m": 98.0, "stamina": 49.0}),
                RaceEvent("status_requested", 40, 1.8, "ember_stride", {"rank": 1, "distance_remaining_m": 92.0, "stamina": 47.0}),
            )
        )

        self.assertEqual(len(backend.calls), 2)
        self.assertIn("100.0 meters", backend.calls[0].text or "")
        self.assertIn("92.0 meters", backend.calls[1].text or "")

    def test_repeated_pace_event_is_throttled(self) -> None:
        root = Path(__file__).parent.parent
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")
        backend = FakeAudioBackend()
        engine = AudioEngine(AudioEventRouter(catalog, backend))

        engine.render_events(
            (
                RaceEvent("pace_cruising", 36, 1.0, "ember_stride", {}),
                RaceEvent("pace_cruising", 36, 1.4, "ember_stride", {}),
                RaceEvent("pace_cruising", 36, 2.7, "ember_stride", {}),
            )
        )

        self.assertEqual([call.text for call in backend.calls if call.method == "speak"], ["Cruising.", "Cruising."])

    def test_opponent_signature_sound_is_layered_with_directional_cue(self) -> None:
        root = Path(__file__).parent.parent
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")
        backend = FakeAudioBackend()
        router = AudioEventRouter(catalog, backend)

        router.route(
            RaceEvent(
                "opponent_approaching",
                60,
                1.0,
                "copper_gate",
                {"forward_m": -4.0, "right_m": -1.0, "signature_sound": "mixkit_horse_7", "horse_name": "Copper Gate"},
            )
        )

        self.assertEqual([call.sound_id for call in backend.calls], ["opponent_approach_left", "mixkit_horse_7"])
        self.assertEqual(backend.calls[1].position.right_m, -1.0)
        self.assertLess(backend.calls[1].volume, backend.calls[0].volume)

    def test_opponent_falling_behind_and_blocking_inside_have_distinct_cues(self) -> None:
        root = Path(__file__).parent.parent
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")
        backend = FakeAudioBackend()
        router = AudioEventRouter(catalog, backend)

        router.route(
            RaceEvent(
                "opponent_falling_behind",
                45,
                1.0,
                "copper_gate",
                {"forward_m": -18.0, "right_m": 0.8, "signature_sound": "mixkit_horse_7", "horse_name": "Copper Gate"},
            )
        )
        router.route(
            RaceEvent(
                "opponent_blocking_inside",
                68,
                2.0,
                "copper_gate",
                {"forward_m": 4.0, "right_m": -0.6, "signature_sound": "mixkit_horse_7", "horse_name": "Copper Gate"},
            )
        )

        played = [call.sound_id for call in backend.calls if call.method == "play_3d"]
        spoken = " ".join(call.text or "" for call in backend.calls if call.method == "speak")
        self.assertEqual(played, ["horse_recover_exhale", "mixkit_horse_7", "collision_brush_shoulders", "mixkit_horse_7"])
        self.assertIn("Copper Gate blocks inside", spoken)
    def test_obstacle_warning_uses_spatial_cue_and_voice(self) -> None:
        root = Path(__file__).parent.parent
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")
        backend = FakeAudioBackend()
        engine = AudioEngine(AudioEventRouter(catalog, backend))

        engine.render_events(
            (
                RaceEvent(
                    event_type="obstacle_warning",
                    priority=70,
                    timestamp_s=5.0,
                    subject_id="cone_1",
                    data={"label": "cone", "forward_m": 22.0, "right_m": -1.15},
                ),
            )
        )

        self.assertEqual(backend.calls[0].method, "play_3d")
        self.assertEqual(backend.calls[0].sound_id, "obstacle_warning_diamond")
        self.assertEqual(backend.calls[0].position.forward_m, 22.0)
        self.assertEqual(backend.calls[0].position.right_m, -1.15)
        self.assertEqual(backend.calls[1].method, "speak")
        self.assertIn("Obstacle cone", backend.calls[1].text or "")

    def test_obstacle_radar_is_spatial_and_non_verbal_with_volume_ramp(self) -> None:
        root = Path(__file__).parent.parent
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")
        backend = FakeAudioBackend()
        router = AudioEventRouter(catalog, backend)

        router.route(RaceEvent("obstacle_radar", 58, 1.0, "cone_1", {"forward_m": 115.0, "right_m": -1.15}))
        router.route(RaceEvent("obstacle_radar", 58, 2.0, "cone_1", {"forward_m": 12.0, "right_m": -1.15}))

        self.assertEqual([call.method for call in backend.calls], ["play_3d", "play_3d", "play_3d"])
        self.assertEqual(backend.calls[0].sound_id, "obstacle_warning_diamond")
        self.assertEqual(backend.calls[0].position.right_m, -1.15)
        self.assertLess(backend.calls[0].volume, backend.calls[1].volume)

    def test_obstacle_radar_uses_distinct_action_signatures(self) -> None:
        root = Path(__file__).parent.parent
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")
        backend = FakeAudioBackend()
        router = AudioEventRouter(catalog, backend)

        router.route(RaceEvent("obstacle_radar", 58, 1.0, "dodge", {"required_action": "dodge", "forward_m": 40.0, "right_m": 0.0}))
        router.route(RaceEvent("obstacle_radar", 58, 2.0, "jump", {"required_action": "jump", "forward_m": 40.0, "right_m": 0.0}))
        router.route(RaceEvent("obstacle_radar", 58, 3.0, "duck", {"required_action": "duck", "forward_m": 40.0, "right_m": 0.0}))

        self.assertEqual(
            [call.sound_id for call in backend.calls],
            ["obstacle_warning_diamond", "horse_jump_takeoff", "ui_cancel_low_tap"],
        )

    def test_imminent_obstacle_radar_uses_double_beep(self) -> None:
        root = Path(__file__).parent.parent
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")
        backend = FakeAudioBackend()
        router = AudioEventRouter(catalog, backend)

        router.route(RaceEvent("obstacle_radar", 58, 1.0, "jump", {"required_action": "jump", "warning_stage": "imminent", "forward_m": 12.0, "right_m": 0.0}))

        self.assertEqual(len(backend.calls), 3)
        self.assertEqual(backend.calls[0].sound_id, "horse_jump_takeoff")
        self.assertGreater(backend.calls[1].volume, backend.calls[0].volume)

    def test_obstacle_jump_duck_and_hit_use_specific_generated_cues(self) -> None:
        root = Path(__file__).parent.parent
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")
        backend = FakeAudioBackend()
        router = AudioEventRouter(catalog, backend)

        router.route(RaceEvent("obstacle_avoided", 70, 1.0, "rail", {"resolution": "jump", "timing_quality": "perfect", "forward_m": 1.0, "right_m": 0.0}))
        router.route(RaceEvent("obstacle_avoided", 70, 2.0, "gate", {"resolution": "duck", "timing_quality": "good", "forward_m": 1.0, "right_m": 0.0}))
        router.route(RaceEvent("obstacle_hit", 90, 3.0, "rail", {"kind": "rail", "label": "rail", "required_action": "jump", "forward_m": 1.0, "right_m": 0.0}))

        played = [call.sound_id for call in backend.calls if call.method == "play_3d"]
        spoken = [call.text for call in backend.calls if call.method == "speak"]
        self.assertIn("horse_jump_landing", played)
        self.assertIn("horse_lane_change_hoof_sweep", played)
        self.assertIn("obstacle_hit_rail_marker", played)
        self.assertIn("Perfect jump confirmed.", spoken)
        self.assertIn("Good duck confirmed.", spoken)

    def test_obstacle_near_miss_and_soft_hit_have_distinct_audio(self) -> None:
        root = Path(__file__).parent.parent
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")
        backend = FakeAudioBackend()
        router = AudioEventRouter(catalog, backend)

        router.route(RaceEvent("obstacle_near_miss", 76, 1.0, "puddle", {"label": "puddle", "kind": "puddle", "forward_m": 0.5, "right_m": 1.15}))
        router.route(RaceEvent("obstacle_hit", 90, 2.0, "puddle", {"label": "puddle", "kind": "puddle", "forward_m": 0.2, "right_m": 0.0}))

        played = [call.sound_id for call in backend.calls if call.method == "play_3d"]
        spoken = [call.text for call in backend.calls if call.method == "speak"]
        self.assertIn("obstacle_warning_diamond", played)
        self.assertIn("horse_stumble_light_dirt", played)
        self.assertIn("Near miss puddle.", spoken)

    def test_stamina_finish_and_final_stretch_events_speak(self) -> None:
        root = Path(__file__).parent.parent
        catalog = load_sound_catalog(root / "content" / "sound_manifest.json")
        backend = FakeAudioBackend()
        engine = AudioEngine(AudioEventRouter(catalog, backend))

        engine.render_events(
            (
                RaceEvent("low_stamina", 55, 1.0, "ember_stride", {}),
                RaceEvent("critical_stamina", 65, 2.0, "ember_stride", {}),
                RaceEvent("final_stretch", 80, 3.0, "ember_stride", {}),
                RaceEvent("finish_line_crossed", 95, 4.0, "ember_stride", {"rank": 1}),
                RaceEvent("race_finished", 95, 5.0, "ember_stride", {}),
            )
        )

        spoken = " ".join(call.text or "" for call in backend.calls if call.method == "speak")
        self.assertIn("Low stamina", spoken)
        self.assertIn("Critical stamina", spoken)
        self.assertIn("Final stretch", spoken)
        self.assertIn("Finished rank 1", spoken)

    def test_fake_backend_stop_all_is_recorded(self) -> None:
        backend = FakeAudioBackend()

        backend.stop_all()

        self.assertEqual(backend.calls[0].method, "stop_all")

    def test_pygame_backend_spatialization_has_strong_left_right_pan(self) -> None:
        backend = PygameAudioBackend.__new__(PygameAudioBackend)

        left = backend._stereo_volume(RelativeAudioPosition(forward_m=10.0, right_m=-2.3), 0.8)
        right = backend._stereo_volume(RelativeAudioPosition(forward_m=10.0, right_m=2.3), 0.8)

        self.assertGreater(left[0], left[1])
        self.assertGreater(right[1], right[0])
        self.assertEqual(backend._bounded_volume(1.5), 1.0)
        self.assertEqual(backend._bounded_volume(-0.5), 0.0)

    def test_cue_map_falls_back_when_preferred_sound_is_missing(self) -> None:
        catalog = SoundCatalog(
            (
                SoundAsset(
                    sound_id="fallback_confirmation",
                    path=Path("assets/fallback.wav"),
                    source="test",
                    license="test",
                    category="ui",
                    loop=False,
                    default_volume=0.5,
                    priority=40,
                ),
            )
        )

        cue = SoundCueMap(catalog).cue_for("finish_line_crossed")

        self.assertIsNotNone(cue)
        self.assertEqual(cue.sound_id, "fallback_confirmation")


if __name__ == "__main__":
    unittest.main()


