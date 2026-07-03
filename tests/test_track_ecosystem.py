import unittest
import tempfile
from pathlib import Path

from horse_racing_game.app.track_ecosystem import (
    EventRuleset,
    TrackCatalog,
    TrackRating,
    TrackShare,
    WeatherPreset,
    load_track_catalog,
    save_track_catalog,
    track_catalog_path,
)


class TrackEcosystemTests(unittest.TestCase):
    def test_publish_and_rate_track_updates_average(self) -> None:
        catalog = TrackCatalog()
        catalog.publish(TrackShare("custom_turf_loop", "alice", "public", version=2))

        catalog.rate(TrackRating("custom_turf_loop", "bob", 5, ("technical",)))
        catalog.rate(TrackRating("custom_turf_loop", "carol", 3, ("technical", "short")))

        self.assertEqual(catalog.average_rating("custom_turf_loop"), 4.0)

    def test_discovery_orders_public_tracks_by_score_and_filters_tags(self) -> None:
        catalog = TrackCatalog()
        catalog.publish(TrackShare("custom_turf_loop", "alice", "public", version=1))
        catalog.publish(TrackShare("custom_dirt_sprint", "bob", "public", version=3))
        catalog.publish(TrackShare("private_turf_test", "carol", "private", version=9))
        catalog.rate(TrackRating("custom_turf_loop", "bob", 4, ("technical",)))
        catalog.rate(TrackRating("custom_dirt_sprint", "alice", 5, ("sprint",)))

        results = catalog.discover(tag_id="sprint")

        self.assertEqual([result.track_id for result in results], ["custom_dirt_sprint"])
        self.assertEqual(results[0].average_rating, 5.0)

    def test_discovery_can_filter_by_surface_hint(self) -> None:
        catalog = TrackCatalog()
        catalog.publish(TrackShare("community_sand_bowl", "alice", "public"))
        catalog.publish(TrackShare("community_mud_loop", "bob", "public"))

        results = catalog.discover(surface="sand")

        self.assertEqual([result.track_id for result in results], ["community_sand_bowl"])

    def test_weather_presets_and_rulesets_validate_references(self) -> None:
        catalog = TrackCatalog()
        catalog.add_weather_preset(WeatherPreset("storm_day", "rain", "Storm Day"))
        ruleset = catalog.add_ruleset(
            EventRuleset(
                "wet_sprint",
                allowed_surface_variants=("mud", "soft_turf"),
                weather_preset_ids=("storm_day",),
                obstacle_density="light",
            )
        )

        self.assertTrue(ruleset.allows_surface("mud"))
        self.assertFalse(ruleset.allows_surface("dirt"))
        self.assertEqual(catalog.ruleset("wet_sprint"), ruleset)
        with self.assertRaises(ValueError):
            catalog.add_ruleset(EventRuleset("missing_weather", weather_preset_ids=("foggy",)))

    def test_track_catalog_persists_shares_ratings_presets_and_rulesets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            catalog = TrackCatalog()
            catalog.publish(TrackShare("custom_turf_loop", "alice", "public", version=2))
            catalog.rate(TrackRating("custom_turf_loop", "bob", 5, ("technical",)))
            catalog.add_weather_preset(WeatherPreset("storm_day", "rain", "Storm Day"))
            catalog.add_ruleset(
                EventRuleset(
                    "wet_sprint",
                    allowed_surface_variants=("mud", "soft_turf"),
                    weather_preset_ids=("storm_day",),
                    obstacle_density="light",
                )
            )

            save_track_catalog(project_root, catalog)
            loaded = load_track_catalog(project_root)

            self.assertTrue(track_catalog_path(project_root).exists())
            self.assertEqual(loaded.shares(), catalog.shares())
            self.assertEqual(loaded.ratings(), catalog.ratings())
            self.assertEqual(loaded.weather_presets(), catalog.weather_presets())
            self.assertEqual(loaded.rulesets(), catalog.rulesets())
            self.assertEqual([result.track_id for result in loaded.discover(tag_id="technical")], ["custom_turf_loop"])

    def test_corrupt_track_catalog_loads_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            path = track_catalog_path(project_root)
            path.parent.mkdir(parents=True)
            path.write_text('{"shares": [{"track_id": "", "author_id": "alice"}]}', encoding="utf-8")

            loaded = load_track_catalog(project_root)

            self.assertEqual(loaded.shares(), ())

    def test_invalid_track_ecosystem_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TrackShare("", "alice")
        with self.assertRaises(ValueError):
            TrackShare("track", "alice", "global")
        with self.assertRaises(ValueError):
            TrackRating("track", "alice", 0)
        with self.assertRaises(ValueError):
            WeatherPreset("", "clear", "Clear")
        with self.assertRaises(ValueError):
            EventRuleset("rules", allowed_surface_variants=("ice",))
        with self.assertRaises(ValueError):
            TrackCatalog().rate(TrackRating("unpublished", "alice", 5))


if __name__ == "__main__":
    unittest.main()
