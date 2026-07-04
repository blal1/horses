import tempfile
import unittest
from pathlib import Path

from horse_racing_game.app.save_sync import (
    SAVE_SYNC_CONFLICTS_DIR,
    build_save_sync_manifest,
    load_save_sync_manifest,
    save_sync_manifest_path,
    sync_save_directory,
)
from horse_racing_game.app.savedata import atomic_write_json, load_json_object


class SaveSyncTests(unittest.TestCase):
    def test_upload_writes_snapshot_manifest_and_local_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "local"
            sync_root = Path(directory) / "sync"
            atomic_write_json(root / "save" / "progress.json", {"wins": 1})

            result = sync_save_directory(root, sync_root, "laptop", 1, 10.0)

            self.assertEqual(result.decision.action, "upload")
            self.assertTrue((sync_root / "files" / "progress.json").exists())
            self.assertTrue(save_sync_manifest_path(root).exists())
            remote = load_save_sync_manifest(sync_root / "save_sync_manifest.json")
            self.assertIsNotNone(remote)
            assert remote is not None
            self.assertEqual(remote.device_id, "laptop")
            self.assertEqual(remote.revision, 1)
            self.assertEqual(remote.files[0].path, "progress.json")

    def test_download_restores_newer_remote_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            target = Path(directory) / "target"
            sync_root = Path(directory) / "sync"
            atomic_write_json(source / "save" / "progress.json", {"wins": 5})
            sync_save_directory(source, sync_root, "desktop", 3, 30.0)
            atomic_write_json(target / "save" / "progress.json", {"wins": 1})

            result = sync_save_directory(target, sync_root, "laptop", 1, 10.0)

            self.assertEqual(result.decision.action, "download")
            self.assertEqual(load_json_object(target / "save" / "progress.json"), {"wins": 5})
            self.assertEqual(load_save_sync_manifest(save_sync_manifest_path(target)).device_id, "desktop")

    def test_conflict_download_keeps_local_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            target = Path(directory) / "target"
            sync_root = Path(directory) / "sync"
            atomic_write_json(source / "save" / "profile.json", {"title": "remote"})
            sync_save_directory(source, sync_root, "desktop", 2, 30.0)
            atomic_write_json(target / "save" / "profile.json", {"title": "local"})

            result = sync_save_directory(target, sync_root, "laptop", 2, 20.0)

            self.assertEqual(result.decision.action, "conflict")
            self.assertEqual(result.decision.winning_device_id, "desktop")
            self.assertIsNotNone(result.conflict_backup)
            assert result.conflict_backup is not None
            self.assertEqual(load_json_object(target / "save" / "profile.json"), {"title": "remote"})
            self.assertEqual(
                load_json_object(result.conflict_backup / "profile.json"),
                {"title": "local"},
            )
            self.assertIn(SAVE_SYNC_CONFLICTS_DIR, result.conflict_backup.as_posix())

    def test_corrupt_synced_file_is_rejected_before_restore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            target = Path(directory) / "target"
            sync_root = Path(directory) / "sync"
            atomic_write_json(source / "save" / "progress.json", {"wins": 5})
            sync_save_directory(source, sync_root, "desktop", 3, 30.0)
            (sync_root / "files" / "progress.json").write_text('{"wins": 99}', encoding="utf-8")
            atomic_write_json(target / "save" / "progress.json", {"wins": 1})

            with self.assertRaises(ValueError):
                sync_save_directory(target, sync_root, "laptop", 1, 10.0)

            self.assertEqual(load_json_object(target / "save" / "progress.json"), {"wins": 1})

    def test_manifest_ignores_sync_metadata_and_conflict_backups(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            atomic_write_json(root / "save" / "progress.json", {"wins": 1})
            atomic_write_json(root / "save" / "save_sync_manifest.json", {"ignored": True})
            atomic_write_json(root / "save" / "sync_conflicts" / "desktop-rev1" / "progress.json", {"wins": 0})

            manifest = build_save_sync_manifest(root, "laptop", 1, 1.0)

            self.assertEqual([item.path for item in manifest.files], ["progress.json"])


if __name__ == "__main__":
    unittest.main()
