from pathlib import Path

import pygame

from horse_racing_game.audio.audio_backend import RelativeAudioPosition
from horse_racing_game.audio.fake_backend import FakeAudioBackend
from horse_racing_game.audio.playback_codecs import channel_playback_supported, format_info
from horse_racing_game.audio.pygame_mixer import ensure_pygame_mixer
from horse_racing_game.audio.spatial_mixer import SpatialAudioMixer
from horse_racing_game.app.runtime_log import write_runtime_log
from horse_racing_game.audio.speech import create_speaker
from horse_racing_game.audio.sound_catalog import SoundAsset, SoundCatalog


class PygameAudioBackend(FakeAudioBackend):
    def __init__(self, project_root: Path, catalog: SoundCatalog) -> None:
        super().__init__()
        self._project_root = project_root
        self._catalog = catalog
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._loop_channels: dict[str, pygame.mixer.Channel] = {}
        self._failed_sound_ids: set[str] = set()
        self._mixer_failed = False
        self._speaker = create_speaker(project_root)
        self._spatial_mixer = SpatialAudioMixer()

    def play_2d(self, sound_id: str, volume: float) -> None:
        super().play_2d(sound_id, volume)
        write_runtime_log(self._project_root, f"audio: play_2d {sound_id} volume={volume:.2f}")
        sound = self._sound(sound_id)
        if sound is None:
            return
        channel = sound.play()
        if channel is not None:
            channel.set_volume(self._bounded_volume(volume))

    def play_3d(self, sound_id: str, position: RelativeAudioPosition, volume: float) -> None:
        super().play_3d(sound_id, position, volume)
        write_runtime_log(
            self._project_root,
            f"audio: play_3d {sound_id} forward={position.forward_m:.1f} right={position.right_m:.1f} volume={volume:.2f}",
        )
        sound = self._sound(sound_id)
        if sound is None:
            return
        channel = sound.play()
        if channel is not None:
            left, right = self._stereo_volume(position, volume)
            channel.set_volume(left, right)

    def play_loop(self, sound_id: str, volume: float) -> None:
        super().play_loop(sound_id, volume)
        write_runtime_log(self._project_root, f"audio: play_loop {sound_id} volume={volume:.2f}")
        self._play_loop_channel(sound_id, sound_id, volume)

    def play_loop_3d(
        self,
        sound_id: str,
        position: RelativeAudioPosition,
        volume: float,
        loop_id: str | None = None,
    ) -> None:
        super().play_loop_3d(sound_id, position, volume, loop_id=loop_id)
        key = loop_id or sound_id
        write_runtime_log(
            self._project_root,
            f"audio: play_loop_3d {key}->{sound_id} forward={position.forward_m:.1f} right={position.right_m:.1f} volume={volume:.2f}",
        )
        self._play_loop_channel(sound_id, key, volume, position)

    def update_loop_3d(
        self,
        sound_id: str,
        position: RelativeAudioPosition,
        volume: float,
        loop_id: str | None = None,
    ) -> None:
        FakeAudioBackend.update_loop_3d(self, sound_id, position, volume, loop_id=loop_id)
        key = loop_id or sound_id
        write_runtime_log(
            self._project_root,
            f"audio: update_loop_3d {key}->{sound_id} forward={position.forward_m:.1f} right={position.right_m:.1f} volume={volume:.2f}",
        )
        self._play_loop_channel(sound_id, key, volume, position)

    def _play_loop_channel(
        self,
        sound_id: str,
        key: str,
        volume: float,
        position: RelativeAudioPosition | None = None,
    ) -> None:
        channel = self._loop_channels.get(key)
        if channel is not None and channel.get_busy():
            self._set_channel_volume(channel, volume, position)
            return
        sound = self._sound(sound_id)
        if sound is None:
            return
        channel = sound.play(loops=-1)
        if channel is None:
            return
        self._set_channel_volume(channel, volume, position)
        self._loop_channels[key] = channel

    def stop_sound(self, sound_id: str) -> None:
        super().stop_sound(sound_id)
        channel = self._loop_channels.pop(sound_id, None)
        if channel is not None:
            channel.stop()
        write_runtime_log(self._project_root, f"audio: stop_sound {sound_id}")

    def speak(self, text: str, priority: int) -> None:
        super().speak(text, priority)
        write_runtime_log(self._project_root, f"voice:{priority} {text}")
        self._speaker.speak(text)

    def stop_all(self) -> None:
        super().stop_all()
        self._loop_channels.clear()
        if pygame.mixer.get_init() is not None:
            pygame.mixer.stop()

    def _sound(self, sound_id: str) -> pygame.mixer.Sound | None:
        if sound_id in self._sounds:
            return self._sounds[sound_id]
        if sound_id in self._failed_sound_ids:
            return None

        asset = self._catalog.get(sound_id)
        if asset is None:
            self._failed_sound_ids.add(sound_id)
            return None
        sound = self._load_sound(asset)
        if sound is None:
            self._failed_sound_ids.add(sound_id)
            return None
        self._sounds[sound_id] = sound
        return sound

    def _load_sound(self, asset: SoundAsset) -> pygame.mixer.Sound | None:
        if self._mixer_failed:
            return None
        sound_path = self._project_root / asset.path
        if not sound_path.exists():
            return None
        if not channel_playback_supported(asset.path):
            info = format_info(asset.path)
            write_runtime_log(self._project_root, f"audio: unsupported channel codec for {asset.sound_id}: {info.extension} ({info.family})")
            return None
        if not self._ensure_mixer():
            return None
        try:
            sound = pygame.mixer.Sound(str(sound_path))
        except pygame.error as error:
            write_runtime_log(self._project_root, f"audio: unable to load {asset.sound_id}: {error}")
            return None
        sound.set_volume(self._bounded_volume(asset.default_volume))
        return sound

    def _ensure_mixer(self) -> bool:
        if self._mixer_failed:
            return False
        if ensure_pygame_mixer(self._project_root):
            return True
        self._mixer_failed = True
        return False

    def _set_channel_volume(self, channel: pygame.mixer.Channel, volume: float, position: RelativeAudioPosition | None) -> None:
        if position is None:
            channel.set_volume(self._bounded_volume(volume))
            return
        left, right = self._stereo_volume(position, volume)
        channel.set_volume(left, right)

    def _stereo_volume(self, position: RelativeAudioPosition, volume: float) -> tuple[float, float]:
        mixer = getattr(self, "_spatial_mixer", None)
        if mixer is None:
            mixer = SpatialAudioMixer()
            self._spatial_mixer = mixer
        mix = mixer.mix(position, volume)
        return mix.left, mix.right

    def _bounded_volume(self, volume: float) -> float:
        return min(max(volume, 0.0), 1.0)



