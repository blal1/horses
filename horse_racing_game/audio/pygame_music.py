from pathlib import Path

import pygame

from horse_racing_game.app.runtime_log import write_runtime_log
from horse_racing_game.audio.playback_codecs import format_info, stream_playback_supported
from horse_racing_game.audio.pygame_mixer import ensure_pygame_mixer


def play_music(project_root: Path, relative_path: str, volume: float) -> None:
    music_path = project_root / relative_path
    if not music_path.exists():
        write_runtime_log(project_root, f"music: missing {relative_path}")
        return
    if not stream_playback_supported(music_path):
        info = format_info(music_path)
        write_runtime_log(project_root, f"music: unsupported stream codec {relative_path}: {info.extension} ({info.family})")
        return
    try:
        if not ensure_pygame_mixer(project_root):
            return
        pygame.mixer.music.load(str(music_path))
        pygame.mixer.music.set_volume(min(max(volume, 0.0), 1.0))
        pygame.mixer.music.play(loops=-1)
        write_runtime_log(project_root, f"music: playing {relative_path}")
    except pygame.error as error:
        write_runtime_log(project_root, f"music: unable to play {relative_path}: {error}")


def set_music_volume(project_root: Path, volume: float) -> None:
    try:
        if pygame.mixer.get_init() is not None:
            pygame.mixer.music.set_volume(min(max(volume, 0.0), 1.0))
    except pygame.error as error:
        write_runtime_log(project_root, f"music: unable to set volume: {error}")


def stop_music(project_root: Path) -> None:
    try:
        if pygame.mixer.get_init() is not None:
            pygame.mixer.music.stop()
    except pygame.error as error:
        write_runtime_log(project_root, f"music: unable to stop: {error}")
