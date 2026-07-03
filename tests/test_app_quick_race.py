import unittest
import os
import tempfile
from pathlib import Path

from horse_racing_game.app.bootstrap import _validate_catalog_paths, build_quick_race_services
from horse_racing_game.app.config import AppConfig
from horse_racing_game.app.game_app import GameApp
from horse_racing_game.audio.debug_backend import DebugAudioBackend
from horse_racing_game.audio.sound_catalog import SoundAsset, SoundCatalog
from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.resources.loader import default_provider
from horse_racing_game.resources.pack import PackWriter


class AppQuickRaceTests(unittest.TestCase):
    def test_build_services_validates_and_wires_fake_audio(self) -> None:
        root = Path(__file__).parent.parent
        config = AppConfig(content_root=root / "content", max_race_seconds=5.0)

        services = build_quick_race_services(config)

        self.assertEqual(services.track.track_id, "ashford_oval")
        self.assertEqual(len(services.horses), 12)
        self.assertEqual(len(services.stables), 4)
        self.assertGreaterEqual(len(services.sound_catalog), 148)
        self.assertEqual(services.audio_backend.calls, [])

    def test_catalog_validation_accepts_assets_in_resource_pack(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dist = root / "dist"
            dist.mkdir()
            writer = PackWriter()
            writer.add("assets/packed.ogg", b"audio")
            writer.write(dist / "resources.dat")
            catalog = SoundCatalog(
                (SoundAsset("packed", Path("assets/packed.ogg"), "test", "test", "ui", False, 0.5, 40),)
            )
            old_cwd = Path.cwd()
            try:
                os.chdir(root)
                default_provider.cache_clear()
                _validate_catalog_paths(AppConfig(content_root=root / "content"), catalog)
            finally:
                os.chdir(old_cwd)
                default_provider.cache_clear()

    def test_build_services_uses_injected_audio_backend(self) -> None:
        root = Path(__file__).parent.parent
        config = AppConfig(content_root=root / "content", max_race_seconds=5.0)
        backend = DebugAudioBackend()

        services = build_quick_race_services(config, backend)

        self.assertIs(services.audio_backend, backend)

    def test_build_services_applies_training_boost_to_player_horse(self) -> None:
        root = Path(__file__).parent.parent
        base_config = AppConfig(content_root=root / "content", max_race_seconds=5.0, horse_training_level=0)
        trained_config = AppConfig(content_root=root / "content", max_race_seconds=5.0, horse_training_level=3)

        base_services = build_quick_race_services(base_config)
        trained_services = build_quick_race_services(trained_config)
        base_player = next(horse for horse in base_services.horses if horse.horse_id == base_config.player_horse_id)
        trained_player = next(horse for horse in trained_services.horses if horse.horse_id == trained_config.player_horse_id)

        self.assertGreater(trained_player.stats.acceleration, base_player.stats.acceleration)
        self.assertGreater(trained_player.stats.stamina_capacity, base_player.stats.stamina_capacity)

    def test_build_services_applies_stable_boost_to_player_horse(self) -> None:
        root = Path(__file__).parent.parent
        base_config = AppConfig(content_root=root / "content", max_race_seconds=5.0, stable_id="oak_lane")
        speed_config = AppConfig(content_root=root / "content", max_race_seconds=5.0, stable_id="stormforge")

        base_services = build_quick_race_services(base_config)
        speed_services = build_quick_race_services(speed_config)
        base_player = next(horse for horse in base_services.horses if horse.horse_id == base_config.player_horse_id)
        speed_player = next(horse for horse in speed_services.horses if horse.horse_id == speed_config.player_horse_id)

        self.assertGreater(speed_player.stats.max_speed_mps, base_player.stats.max_speed_mps)
        self.assertIn("stable_stormforge", speed_player.traits)

    def test_build_services_applies_stable_boost_to_rival_horse(self) -> None:
        root = Path(__file__).parent.parent
        base_config = AppConfig(content_root=root / "content", max_race_seconds=5.0)
        rival_config = AppConfig(
            content_root=root / "content",
            max_race_seconds=5.0,
            rival_stable_ids={"golden_switch": "stormforge"},
        )

        base_services = build_quick_race_services(base_config)
        rival_services = build_quick_race_services(rival_config)
        base_rival = next(horse for horse in base_services.horses if horse.horse_id == "golden_switch")
        boosted_rival = next(horse for horse in rival_services.horses if horse.horse_id == "golden_switch")

        self.assertGreater(boosted_rival.stats.max_speed_mps, base_rival.stats.max_speed_mps)
        self.assertIn("stable_stormforge", boosted_rival.traits)

    def test_quick_race_runs_simulation_and_routes_audio_events(self) -> None:
        root = Path(__file__).parent.parent
        config = AppConfig(content_root=root / "content", max_race_seconds=20.0)
        app = GameApp(config, build_quick_race_services(config))
        commands = [RaceCommand(throttle_delta=1.0, request_status=True) for _ in range(12)]

        result = app.run_quick_race(commands)

        self.assertGreater(result.state.elapsed_s, 0.0)
        self.assertGreater(len(result.events), 0)
        self.assertGreater(len(result.audio_calls), 0)
        self.assertEqual(result.events[0].event_type, "race_started")


if __name__ == "__main__":
    unittest.main()
