from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from horse_racing_game.audio.sound_catalog import SoundAsset, SoundCatalog


CHANNEL_AUDIO_EXTENSIONS = frozenset({".wav", ".ogg", ".oga", ".opus", ".mp3", ".flac"})
STREAM_AUDIO_EXTENSIONS = CHANNEL_AUDIO_EXTENSIONS | frozenset({".mod", ".xm", ".it", ".s3m"})
COMPRESSED_EXTENSIONS = frozenset({".ogg", ".oga", ".opus", ".mp3", ".flac"})
LOOP_PREFERRED_EXTENSIONS = frozenset({".ogg", ".oga", ".opus"})
TRACKER_MODULE_EXTENSIONS = frozenset({".mod", ".xm", ".it", ".s3m"})


@dataclass(frozen=True)
class AudioFormatInfo:
    extension: str
    family: str
    channel_supported: bool
    stream_supported: bool
    compressed: bool
    loop_preferred: bool


@dataclass(frozen=True)
class CodecUsageReport:
    total_assets: int
    by_extension: dict[str, int]
    unsupported_channel_assets: tuple[str, ...]
    stream_preferred_assets: tuple[str, ...]


def format_info(path: str | Path) -> AudioFormatInfo:
    extension = _extension(path)
    return AudioFormatInfo(
        extension=extension,
        family=_family(extension),
        channel_supported=extension in CHANNEL_AUDIO_EXTENSIONS,
        stream_supported=extension in STREAM_AUDIO_EXTENSIONS,
        compressed=extension in COMPRESSED_EXTENSIONS,
        loop_preferred=extension in LOOP_PREFERRED_EXTENSIONS,
    )


def channel_playback_supported(path: str | Path) -> bool:
    return format_info(path).channel_supported


def stream_playback_supported(path: str | Path) -> bool:
    return format_info(path).stream_supported


def should_stream_path(path: str | Path) -> bool:
    info = format_info(path)
    return info.extension in TRACKER_MODULE_EXTENSIONS


def compression_recommendation(asset: SoundAsset) -> str:
    """Return the preferred compressed delivery extension for future assets."""
    if asset.category == "music":
        return ".opus"
    if asset.loop or asset.category in {"ambient", "ambience", "wind", "rain"}:
        return ".ogg"
    return ".ogg" if asset.category in {"horse", "obstacle", "race"} else ".wav"


def codec_usage_report(catalog: SoundCatalog) -> CodecUsageReport:
    by_extension: dict[str, int] = {}
    unsupported: list[str] = []
    stream_preferred: list[str] = []
    for asset in catalog.assets():
        info = format_info(asset.path)
        by_extension[info.extension] = by_extension.get(info.extension, 0) + 1
        if not info.channel_supported:
            unsupported.append(asset.sound_id)
        if should_stream_path(asset.path) or (asset.category == "music" and info.stream_supported):
            stream_preferred.append(asset.sound_id)
    return CodecUsageReport(
        total_assets=len(catalog.assets()),
        by_extension=dict(sorted(by_extension.items())),
        unsupported_channel_assets=tuple(unsupported),
        stream_preferred_assets=tuple(stream_preferred),
    )


def _extension(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    return suffix if suffix else "<none>"


def _family(extension: str) -> str:
    if extension in {".ogg", ".oga"}:
        return "Ogg Vorbis"
    if extension == ".opus":
        return "Opus"
    if extension == ".mp3":
        return "MP3"
    if extension == ".wav":
        return "WAV/PCM"
    if extension == ".flac":
        return "FLAC"
    if extension in TRACKER_MODULE_EXTENSIONS:
        return "tracker module"
    return "unknown"
