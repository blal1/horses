import tempfile
import unittest
from pathlib import Path

from horse_racing_game.app.diagnostics import build_diagnostic_report, read_runtime_log_tail
from horse_racing_game.app.live_ops import (
    AnalyticsEvent,
    RemoteConfig,
    TelemetryStore,
    crash_report_from_exception,
    save_telemetry_store,
)
from horse_racing_game.app.progress import GameProgress, record_race_result
from horse_racing_game.app.runtime_log import runtime_log_path, write_runtime_log


class DiagnosticsTests(unittest.TestCase):
    def test_runtime_log_tail_reads_recent_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            write_runtime_log(project_root, "first")
            write_runtime_log(project_root, "second")
            write_runtime_log(project_root, "third")

            tail = read_runtime_log_tail(project_root, 2)

            self.assertEqual(len(tail), 2)
            self.assertIn("second", tail[0])
            self.assertIn("third", tail[1])
            self.assertEqual(read_runtime_log_tail(project_root, 0), ())

    def test_diagnostic_report_summarizes_files_telemetry_and_troubleshooting_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            record_race_result(project_root, GameProgress(), "ember_stride", "ashford_oval", is_tutorial=False, finished=True, rank=1)
            store = TelemetryStore(telemetry_consent_enabled=True)
            store.set_remote_config(RemoteConfig("remote-1"))
            store.record_analytics(AnalyticsEvent("menu_action", "alice", 1.0, {"item": "career"}))
            store.record_crash(crash_report_from_exception("crash-1", 2.0, RuntimeError("boom"), "stack"))
            save_telemetry_store(project_root, store)
            write_runtime_log(project_root, "diagnostic line")

            report = build_diagnostic_report(project_root, tail_lines=1)
            lines = report.troubleshooting_lines()

            statuses = {status.label: status for status in report.files}
            self.assertTrue(statuses["runtime_log"].exists)
            self.assertTrue(statuses["progress"].exists)
            self.assertTrue(statuses["live_ops"].exists)
            self.assertFalse(statuses["profile"].exists)
            self.assertEqual(report.crash_report_count, 1)
            self.assertEqual(report.analytics_event_count, 1)
            self.assertIn("diagnostic line", report.runtime_log_tail[0])
            self.assertTrue(any("Crash reports: 1" in line for line in lines))
            self.assertTrue(any("Missing files:" in line for line in lines))
            self.assertTrue(runtime_log_path(project_root).exists())

    def test_diagnostic_report_rejects_negative_tail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                build_diagnostic_report(Path(directory), tail_lines=-1)


if __name__ == "__main__":
    unittest.main()
