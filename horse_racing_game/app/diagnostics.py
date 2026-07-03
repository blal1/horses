from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from horse_racing_game.app.chat import chat_session_path
from horse_racing_game.app.community import community_hub_path
from horse_racing_game.app.file_directories import FileDirectories
from horse_racing_game.app.live_ops import load_telemetry_store, live_ops_path
from horse_racing_game.app.profile import profile_path
from horse_racing_game.app.runtime_log import runtime_log_path
from horse_racing_game.app.social import social_graph_path
from horse_racing_game.app.track_ecosystem import track_catalog_path


@dataclass(frozen=True)
class DiagnosticFileStatus:
    label: str
    path: Path
    exists: bool
    size_bytes: int


@dataclass(frozen=True)
class DiagnosticReport:
    project_root: Path
    files: tuple[DiagnosticFileStatus, ...]
    runtime_log_tail: tuple[str, ...]
    crash_report_count: int
    analytics_event_count: int

    def troubleshooting_lines(self) -> tuple[str, ...]:
        missing = [status.label for status in self.files if not status.exists]
        present = [f"{status.label}={status.size_bytes} bytes" for status in self.files if status.exists]
        return (
            f"Diagnostics for {self.project_root}",
            f"Present files: {', '.join(present) if present else 'none'}",
            f"Missing files: {', '.join(missing) if missing else 'none'}",
            f"Crash reports: {self.crash_report_count}",
            f"Analytics events queued: {self.analytics_event_count}",
            f"Recent log: {' | '.join(self.runtime_log_tail) if self.runtime_log_tail else 'none'}",
        )


def build_diagnostic_report(project_root: Path, tail_lines: int = 8) -> DiagnosticReport:
    if tail_lines < 0:
        raise ValueError("tail_lines must be non-negative")
    telemetry = load_telemetry_store(project_root)
    return DiagnosticReport(
        project_root=project_root,
        files=tuple(_file_status(label, path) for label, path in _diagnostic_paths(project_root)),
        runtime_log_tail=read_runtime_log_tail(project_root, tail_lines),
        crash_report_count=len(telemetry.crash_reports),
        analytics_event_count=len(telemetry.analytics_events),
    )


def read_runtime_log_tail(project_root: Path, line_count: int = 8) -> tuple[str, ...]:
    if line_count < 0:
        raise ValueError("line_count must be non-negative")
    path = runtime_log_path(project_root)
    if line_count == 0 or not path.exists():
        return ()
    try:
        return tuple(path.read_text(encoding="utf-8").splitlines()[-line_count:])
    except OSError:
        return ()


def _diagnostic_paths(project_root: Path) -> tuple[tuple[str, Path], ...]:
    directories = FileDirectories(project_root)
    return (
        ("runtime_log", runtime_log_path(project_root)),
        ("progress", directories.progress_file()),
        ("profile", profile_path(project_root)),
        ("track_catalog", track_catalog_path(project_root)),
        ("social_graph", social_graph_path(project_root)),
        ("community_hub", community_hub_path(project_root)),
        ("chat_session", chat_session_path(project_root)),
        ("live_ops", live_ops_path(project_root)),
    )


def _file_status(label: str, path: Path) -> DiagnosticFileStatus:
    if not path.exists():
        return DiagnosticFileStatus(label, path, False, 0)
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return DiagnosticFileStatus(label, path, True, size)
