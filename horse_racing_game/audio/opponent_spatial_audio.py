from __future__ import annotations

from dataclasses import dataclass

from horse_racing_game.audio.audio_backend import AudioBackend, RelativeAudioPosition
from horse_racing_game.audio.sound_catalog import SoundCatalog
from horse_racing_game.audio.spatial_mixer import SpatialAudioMixer
from horse_racing_game.domain.track import Track
from horse_racing_game.domain.weather import Weather
from horse_racing_game.simulation.race_state import RaceState, RunnerState


@dataclass(frozen=True)
class OpponentSpatialAudioConfig:
    max_sources: int = 4
    hearing_range_m: float = 58.0
    lateral_range_m: float = 4.8
    base_volume: float = 0.16
    speed_volume: float = 0.32
    tired_volume: float = 0.08


class OpponentSpatialAudio:
    """Moving 3D loop layer for nearby rival horses.

    The race engine still emits discrete readability cues. This class fills the
    gaps between events with pooled, distance-shaped hoof loops for the nearest
    opponents.
    """

    def __init__(
        self,
        backend: AudioBackend,
        catalog: SoundCatalog,
        track: Track,
        weather: Weather,
        config: OpponentSpatialAudioConfig | None = None,
    ) -> None:
        self._backend = backend
        self._catalog = catalog
        self._track = track
        self._weather = weather
        self._config = config or OpponentSpatialAudioConfig()
        self._mixer = SpatialAudioMixer(hearing_range_m=self._config.hearing_range_m)
        self._active_loop_ids: set[str] = set()

    def update(self, state: RaceState) -> None:
        if state.is_finished:
            self.stop()
            return

        player = state.player()
        audible = self._audible_opponents(player, state.runners)
        next_loop_ids: set[str] = set()
        for runner, position in audible[: self._config.max_sources]:
            sound_id = self._loop_sound_id(runner)
            if sound_id is None:
                continue
            loop_id = self._loop_id(runner)
            volume = self._volume(runner, position)
            self._backend.update_loop_3d(sound_id, position, volume, loop_id=loop_id)
            next_loop_ids.add(loop_id)

        self._stop_stale_loops(next_loop_ids)
        self._active_loop_ids = next_loop_ids

    def stop(self) -> None:
        for loop_id in sorted(self._active_loop_ids):
            self._backend.stop_sound(loop_id)
        self._active_loop_ids.clear()

    def _audible_opponents(
        self,
        player: RunnerState,
        runners: tuple[RunnerState, ...],
    ) -> list[tuple[RunnerState, RelativeAudioPosition]]:
        candidates: list[tuple[float, RunnerState, RelativeAudioPosition]] = []
        for runner in runners:
            if runner.is_player:
                continue
            position = RelativeAudioPosition(
                forward_m=runner.distance_m - player.distance_m,
                right_m=runner.lateral_position - player.lateral_position,
            )
            if not self._is_audible(position):
                continue
            distance_score = abs(position.forward_m) + abs(position.right_m) * 3.0
            candidates.append((distance_score, runner, position))
        candidates.sort(key=lambda item: item[0])
        return [(runner, position) for _, runner, position in candidates]

    def _is_audible(self, position: RelativeAudioPosition) -> bool:
        if abs(position.forward_m) > self._config.hearing_range_m:
            return False
        return abs(position.right_m) <= self._config.lateral_range_m

    def _loop_sound_id(self, runner: RunnerState) -> str | None:
        if runner.speed_mps < 2.5:
            return self._first_existing(("horse_walk_loop_stable_yard", "horse_trot_loop_turf"))
        if runner.speed_mps < 7.0:
            return self._first_existing(("horse_trot_loop_turf", "horse_canter_loop_turf"))
        if runner.speed_mps < 11.0:
            return self._first_existing(("horse_canter_loop_turf", "horse_player_gallop_loop_turf"))

        segment = self._track.segment_at(runner.distance_m)
        marker = segment.audio_marker.lower()
        if "inner_rail" in marker:
            rail = self._first_existing(("horse_gallop_loop_inner_rail_close",))
            if rail is not None:
                return rail
        surface = self._track.surface.lower()
        weather_id = self._weather.weather_id.lower()
        if "rain" in weather_id or surface in {"mud", "wet", "sloppy"}:
            return self._first_existing(("horse_gallop_loop_mud", "horse_player_gallop_loop_turf"))
        if surface == "dirt":
            return self._first_existing(("horse_gallop_loop_dirt", "horse_player_gallop_loop_turf"))
        if surface == "sand":
            return self._first_existing(("horse_gallop_loop_sand", "horse_player_gallop_loop_turf"))
        return self._first_existing(("horse_player_gallop_loop_turf", "horse_canter_loop_turf"))

    def _volume(self, runner: RunnerState, position: RelativeAudioPosition) -> float:
        speed_ratio = min(max(runner.speed_mps / 15.0, 0.0), 1.0)
        tired_ratio = 1.0 - min(max(runner.stamina / 100.0, 0.0), 1.0)
        source_volume = self._config.base_volume + speed_ratio * self._config.speed_volume + tired_ratio * self._config.tired_volume
        return self._mixer.distance_gain(position, source_volume)

    def _first_existing(self, sound_ids: tuple[str, ...]) -> str | None:
        for sound_id in sound_ids:
            if self._catalog.get(sound_id) is not None:
                return sound_id
        return None

    def _stop_stale_loops(self, next_loop_ids: set[str]) -> None:
        for loop_id in sorted(self._active_loop_ids - next_loop_ids):
            self._backend.stop_sound(loop_id)

    def _loop_id(self, runner: RunnerState) -> str:
        return f"opponent:{runner.runner_id}"
