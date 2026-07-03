from dataclasses import dataclass

from horse_racing_game.app.config import AppConfig
from horse_racing_game.app.track_editor import load_available_tracks
from horse_racing_game.app.training import apply_training_boost
from horse_racing_game.audio.audio_engine import AudioEngine
from horse_racing_game.audio.event_router import AudioEventRouter
from horse_racing_game.audio.fake_backend import FakeAudioBackend
from horse_racing_game.audio.sound_catalog import SoundCatalog
from horse_racing_game.content.loaders import load_horses, load_rivals, load_sound_catalog, load_stables, load_weather
from horse_racing_game.domain.horse import Horse
from horse_racing_game.domain.rival import RivalProfile
from horse_racing_game.domain.stable import Stable, apply_stable_boost
from horse_racing_game.domain.track import Track
from horse_racing_game.domain.weather import Weather
from horse_racing_game.resources.loader import default_provider
from horse_racing_game.simulation.race_engine import RaceEngine


@dataclass(frozen=True)
class GameServices:
    horses: tuple[Horse, ...]
    rivals: tuple[RivalProfile, ...]
    stables: tuple[Stable, ...]
    track: Track
    weather: Weather
    sound_catalog: SoundCatalog
    race_engine: RaceEngine
    audio_engine: AudioEngine
    audio_backend: FakeAudioBackend


def build_quick_race_services(config: AppConfig, audio_backend: FakeAudioBackend | None = None) -> GameServices:
    horses = load_horses(config.content_root / "horses.json")
    rivals = load_rivals(config.content_root / "rivals.json")
    tracks = load_available_tracks(config.content_root)
    weather_options = load_weather(config.content_root / "weather.json")
    stables = load_stables(config.content_root / "stables.json")
    sound_catalog = load_sound_catalog(config.content_root / "sound_manifest.json")
    track = _find_track(tracks, config.track_id)
    weather = _find_weather(weather_options, config.weather_id)
    stable = _find_stable(stables, config.stable_id)
    horses = _apply_stable_to_player(horses, config.player_horse_id, stable)
    horses = _apply_stables_to_rivals(horses, stables, config.rival_stable_ids)
    horses = _apply_training_to_player(horses, config.player_horse_id, config.horse_training_level)
    _validate_player_horse(horses, config.player_horse_id)
    _validate_catalog_paths(config, sound_catalog)

    selected_audio_backend = audio_backend if audio_backend is not None else FakeAudioBackend()
    return GameServices(
        horses=horses,
        rivals=rivals,
        stables=stables,
        track=track,
        weather=weather,
        sound_catalog=sound_catalog,
        race_engine=RaceEngine(
            track,
            horses,
            config.player_horse_id,
            config.seed,
            weather,
            opponent_strength=config.opponent_strength,
        ),
        audio_engine=AudioEngine(AudioEventRouter(sound_catalog, selected_audio_backend)),
        audio_backend=selected_audio_backend,
    )


def _find_track(tracks: tuple[Track, ...], track_id: str) -> Track:
    for track in tracks:
        if track.track_id == track_id:
            return track
    raise ValueError(f"Unknown track: {track_id}")


def _find_weather(weather_options: tuple[Weather, ...], weather_id: str) -> Weather:
    for weather in weather_options:
        if weather.weather_id == weather_id:
            return weather
    raise ValueError(f"Unknown weather: {weather_id}")


def _find_stable(stables: tuple[Stable, ...], stable_id: str) -> Stable:
    for stable in stables:
        if stable.stable_id == stable_id:
            return stable
    raise ValueError(f"Unknown stable: {stable_id}")


def _validate_player_horse(horses: tuple[Horse, ...], player_horse_id: str) -> None:
    if any(horse.horse_id == player_horse_id for horse in horses):
        return
    raise ValueError(f"Unknown player horse: {player_horse_id}")


def _apply_training_to_player(horses: tuple[Horse, ...], player_horse_id: str, level: int) -> tuple[Horse, ...]:
    return tuple(apply_training_boost(horse, level) if horse.horse_id == player_horse_id else horse for horse in horses)


def _apply_stable_to_player(horses: tuple[Horse, ...], player_horse_id: str, stable: Stable) -> tuple[Horse, ...]:
    return tuple(apply_stable_boost(horse, stable) if horse.horse_id == player_horse_id else horse for horse in horses)


def _apply_stables_to_rivals(
    horses: tuple[Horse, ...],
    stables: tuple[Stable, ...],
    rival_stable_ids: dict[str, str],
) -> tuple[Horse, ...]:
    stable_by_id = {stable.stable_id: stable for stable in stables}
    boosted: list[Horse] = []
    for horse in horses:
        stable = stable_by_id.get(rival_stable_ids.get(horse.horse_id, ""))
        boosted.append(apply_stable_boost(horse, stable) if stable is not None and horse.role == "opponent" else horse)
    return tuple(boosted)


def _validate_catalog_paths(config: AppConfig, catalog: SoundCatalog) -> None:
    provider = default_provider()
    missing = []
    for asset in catalog.assets():
        if (config.content_root.parent / asset.path).exists():
            continue
        if provider.packed and provider_has_file(asset.path.as_posix()):
            continue
        missing.append(asset.path)
    if missing:
        sample = ", ".join(str(path) for path in missing[:3])
        raise FileNotFoundError(f"Sound manifest references missing files: {sample}")


def provider_has_file(name: str) -> bool:
    try:
        default_provider().get_bytes(name)
    except FileNotFoundError:
        return False
    return True
