from __future__ import annotations

from pathlib import Path

import pygame

from horse_racing_game.app.runtime_log import write_runtime_log


MIXER_FREQUENCY = 44100
MIXER_SIZE = -16
MIXER_OUTPUT_CHANNELS = 2
MIXER_BUFFER = 512
PLAYBACK_CHANNELS = 32


def ensure_pygame_mixer(project_root: Path) -> bool:
    if pygame.mixer.get_init() is None:
        try:
            pygame.mixer.init(
                frequency=MIXER_FREQUENCY,
                size=MIXER_SIZE,
                channels=MIXER_OUTPUT_CHANNELS,
                buffer=MIXER_BUFFER,
            )
        except pygame.error as error:
            write_runtime_log(project_root, f"audio: mixer unavailable: {error}")
            return False
        _log_mixer_ready(project_root)
    _ensure_playback_channels()
    return True


def _ensure_playback_channels() -> None:
    if pygame.mixer.get_num_channels() < PLAYBACK_CHANNELS:
        pygame.mixer.set_num_channels(PLAYBACK_CHANNELS)


def _log_mixer_ready(project_root: Path) -> None:
    version = _sdl_mixer_version()
    write_runtime_log(
        project_root,
        "audio: SDL_mixer ready "
        f"version={version} frequency={MIXER_FREQUENCY} output_channels={MIXER_OUTPUT_CHANNELS} "
        f"buffer={MIXER_BUFFER} playback_channels={PLAYBACK_CHANNELS}",
    )


def _sdl_mixer_version() -> str:
    getter = getattr(pygame.mixer, "get_sdl_mixer_version", None)
    if getter is None:
        return "unknown"
    try:
        version = getter()
    except TypeError:
        version = getter(linked=True)
    except pygame.error:
        return "unknown"
    if isinstance(version, tuple):
        return ".".join(str(part) for part in version)
    return str(version)
