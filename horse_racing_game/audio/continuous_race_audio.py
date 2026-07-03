from __future__ import annotations

from dataclasses import dataclass

from horse_racing_game.audio.audio_backend import AudioBackend
from horse_racing_game.audio.sound_catalog import SoundCatalog
from horse_racing_game.domain.track import Track
from horse_racing_game.domain.weather import Weather
from horse_racing_game.simulation.race_state import RunnerState


@dataclass(frozen=True)
class ContinuousRaceAudioConfig:
    horse_volume: float = 1.0
    low_stamina_threshold: float = 34.0
    recovery_threshold: float = 46.0
    volume_update_threshold: float = 0.03


class ContinuousRaceAudio:
    """State-driven race bed for the player's horse.

    Event cues tell the player what happened; this layer tells them what is
    happening continuously through gait, surface, fatigue, and recovery sounds.
    """

    def __init__(
        self,
        backend: AudioBackend,
        catalog: SoundCatalog,
        track: Track,
        weather: Weather,
        config: ContinuousRaceAudioConfig | None = None,
    ) -> None:
        self._backend = backend
        self._catalog = catalog
        self._track = track
        self._weather = weather
        self._config = config or ContinuousRaceAudioConfig()
        self._current_gait_sound_id: str | None = None
        self._current_breath_sound_id: str | None = None
        self._last_gait_volume = 0.0
        self._last_breath_volume = 0.0
        self._previous_stamina: float | None = None
        self._was_low_stamina = False

    def update(self, player: RunnerState, is_finished: bool) -> None:
        if is_finished:
            self.stop()
            return
        self._update_gait(player)
        self._update_stamina_layer(player)
        self._previous_stamina = player.stamina

    def stop(self) -> None:
        self._stop_gait_loop()
        self._stop_breath_loop()
        self._previous_stamina = None
        self._was_low_stamina = False

    def _update_gait(self, player: RunnerState) -> None:
        sound_id = self._gait_sound_id(player)
        if self._catalog.get(sound_id) is None:
            return
        volume = self._gait_volume(player.speed_mps)
        if self._current_gait_sound_id is not None and self._current_gait_sound_id != sound_id:
            self._backend.stop_sound(self._current_gait_sound_id)
            self._last_gait_volume = 0.0
        self._current_gait_sound_id = sound_id
        if self._should_update_volume(volume, self._last_gait_volume):
            self._last_gait_volume = volume
            self._backend.play_loop(sound_id, volume)

    def _update_stamina_layer(self, player: RunnerState) -> None:
        low_threshold = self._config.low_stamina_threshold
        recovery_threshold = self._config.recovery_threshold
        if player.stamina <= low_threshold:
            self._was_low_stamina = True
            self._play_breath_loop(player)
            return

        self._stop_breath_loop()
        previous = self._previous_stamina
        if self._was_low_stamina and previous is not None and player.stamina >= recovery_threshold and player.stamina > previous:
            self._play_recovery_exhale(player)
            self._was_low_stamina = False

    def _play_breath_loop(self, player: RunnerState) -> None:
        sound_id = "horse_breath_low_stamina"
        if self._catalog.get(sound_id) is None:
            return
        volume = self._breath_volume(player.stamina)
        if self._current_breath_sound_id is None:
            self._current_breath_sound_id = sound_id
            self._last_breath_volume = 0.0
        if self._should_update_volume(volume, self._last_breath_volume):
            self._last_breath_volume = volume
            self._backend.play_loop(sound_id, volume)

    def _play_recovery_exhale(self, player: RunnerState) -> None:
        sound_id = "horse_recover_exhale"
        if self._catalog.get(sound_id) is None:
            return
        speed_factor = min(max(player.speed_mps / 14.0, 0.0), 1.0)
        self._backend.play_2d(sound_id, 0.36 + speed_factor * 0.16)

    def _gait_sound_id(self, player: RunnerState) -> str:
        if player.speed_mps < 2.5:
            return "horse_walk_loop_stable_yard"
        if player.speed_mps < 7.0:
            return "horse_trot_loop_turf"
        if player.speed_mps < 11.0:
            return "horse_canter_loop_turf"
        return self._surface_gallop_sound_id(player)

    def _surface_gallop_sound_id(self, player: RunnerState) -> str:
        segment = self._track.segment_at(player.distance_m)
        marker = segment.audio_marker.lower()
        if "inner_rail" in marker and self._catalog.get("horse_gallop_loop_inner_rail_close") is not None:
            return "horse_gallop_loop_inner_rail_close"
        surface = self._track.surface.lower()
        weather_id = self._weather.weather_id.lower()
        if "rain" in weather_id or surface in {"mud", "wet", "sloppy"}:
            return "horse_gallop_loop_mud"
        if surface == "dirt":
            return "horse_gallop_loop_dirt"
        if surface == "sand":
            return "horse_gallop_loop_sand"
        return "horse_player_gallop_loop_turf"

    def _gait_volume(self, speed_mps: float) -> float:
        speed_ratio = min(max(speed_mps / 15.0, 0.0), 1.0)
        return min(0.74, 0.18 + speed_ratio * 0.5) * self._config.horse_volume

    def _breath_volume(self, stamina: float) -> float:
        fatigue = 1.0 - min(max(stamina / self._config.low_stamina_threshold, 0.0), 1.0)
        return (0.38 + fatigue * 0.22) * self._config.horse_volume

    def _should_update_volume(self, volume: float, previous: float) -> bool:
        return abs(volume - previous) >= self._config.volume_update_threshold

    def _stop_gait_loop(self) -> None:
        if self._current_gait_sound_id is None:
            return
        self._backend.stop_sound(self._current_gait_sound_id)
        self._current_gait_sound_id = None
        self._last_gait_volume = 0.0

    def _stop_breath_loop(self) -> None:
        if self._current_breath_sound_id is None:
            return
        self._backend.stop_sound(self._current_breath_sound_id)
        self._current_breath_sound_id = None
        self._last_breath_volume = 0.0
