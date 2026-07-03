import tempfile
import unittest
from pathlib import Path

from horse_racing_game.audio.sound_catalog import SoundAsset, SoundCatalog


class SoundCatalogTests(unittest.TestCase):
    def test_catalog_lookup_missing_files_and_matching_fallbacks(self) -> None:
        assets = (
            SoundAsset("ui_confirm", Path("present.wav"), "test", "test", "ui", False, 0.5, 40),
            SoundAsset("horse_gallop", Path("missing.wav"), "test", "test", "horse", True, 0.6, 50),
        )
        catalog = SoundCatalog(assets)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "present.wav").write_bytes(b"ok")

            self.assertEqual(catalog.assets(), assets)
            self.assertEqual(catalog.get("ui_confirm"), assets[0])
            self.assertEqual(catalog.first_by_category("ui"), assets[0])
            self.assertEqual(catalog.first_id_by_category("horse"), "horse_gallop")
            self.assertEqual(catalog.first_matching_id("ui", "confirm"), "ui_confirm")
            self.assertEqual(catalog.first_matching_id("ui", "missing-token"), "ui_confirm")
            self.assertEqual(catalog.first_matching_id("missing", "anything"), None)
            self.assertEqual(catalog.missing_files(root), (Path("missing.wav"),))


if __name__ == "__main__":
    unittest.main()
