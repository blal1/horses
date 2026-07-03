import json
from pathlib import Path

from horse_racing_game.audio.sound_catalog import SoundAsset, SoundCatalog
from horse_racing_game.domain.horse import Horse, HorseStats
from horse_racing_game.domain.rival import RivalProfile
from horse_racing_game.domain.stable import Stable
from horse_racing_game.domain.track import Track, TrackSegment
from horse_racing_game.domain.weather import Weather
from horse_racing_game.content.pack_file import PackFile


JsonObject = dict[str, object]


def load_horses(path: Path) -> tuple[Horse, ...]:
    data = PackFile.from_path(path).read_json_array(path.name)
    return tuple(_parse_horse(item, path) for item in data)


def load_tracks(path: Path) -> tuple[Track, ...]:
    data = PackFile.from_path(path).read_json_array(path.name)
    return tuple(_parse_track(item, path) for item in data)


def load_weather(path: Path) -> tuple[Weather, ...]:
    data = PackFile.from_path(path).read_json_array(path.name)
    return tuple(_parse_weather(item, path) for item in data)


def load_rivals(path: Path) -> tuple[RivalProfile, ...]:
    data = PackFile.from_path(path).read_json_array(path.name)
    return tuple(_parse_rival(item, path) for item in data)


def load_stables(path: Path) -> tuple[Stable, ...]:
    data = PackFile.from_path(path).read_json_array(path.name)
    return tuple(_parse_stable(item, path) for item in data)


def load_sound_catalog(path: Path) -> SoundCatalog:
    data = PackFile.from_path(path).read_json_array(path.name)
    base_assets = tuple(_parse_sound_asset(item, path) for item in data)
    generated_assets = _load_existing_elevenlabs_sound_effects(path.parent / "elevenlabs_audio_prompts.json", path.parent.parent)
    assets = base_assets + generated_assets
    return SoundCatalog(assets)


def _load_existing_elevenlabs_sound_effects(spec_path: Path, project_root: Path) -> tuple[SoundAsset, ...]:
    spec_file = PackFile.from_path(spec_path)
    if not spec_file.exists(spec_path.name):
        return ()
    parsed = spec_file.read_json(spec_path.name)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected a JSON object in {spec_path}")
    output_dir = parsed.get("output_dir")
    raw_assets = parsed.get("assets")
    if not isinstance(output_dir, str) or not isinstance(raw_assets, list):
        raise ValueError(f"Expected output_dir and assets in {spec_path}")
    assets: list[SoundAsset] = []
    project_files = PackFile(project_root)
    for item in raw_assets:
        if not isinstance(item, dict) or item.get("kind") != "sound_effect":
            continue
        file_name = _string(item, "file", spec_path)
        relative_path = Path(output_dir) / file_name
        if not project_files.exists(relative_path):
            continue
        assets.append(
            SoundAsset(
                sound_id=_string(item, "id", spec_path),
                path=relative_path,
                source="ElevenLabs generated audio",
                license="ElevenLabs generated; verify plan terms before distribution",
                category=_string(item, "category", spec_path),
                loop=_boolean_value(item.get("loop", False), "loop", spec_path),
                default_volume=_number_value(item.get("volume", 0.5), "volume", spec_path),
                priority=_integer_value(item.get("priority", 40), "priority", spec_path),
            )
    )
    return tuple(assets)


def _parse_horse(data: JsonObject, path: Path) -> Horse:
    stats_data = _object(data, "stats", path)
    traits = _list(data, "traits", path)
    return Horse(
        horse_id=_string(data, "horse_id", path),
        name=_string(data, "name", path),
        role=_string(data, "role", path),
        preferred_surface=_string(data, "preferred_surface", path),
        signature_sound=_string(data, "signature_sound", path),
        stats=HorseStats(
            max_speed_mps=_number(stats_data, "max_speed_mps", path),
            acceleration=_number(stats_data, "acceleration", path),
            stamina_capacity=_number(stats_data, "stamina_capacity", path),
            stamina_recovery=_number(stats_data, "stamina_recovery", path),
            handling=_number(stats_data, "handling", path),
            nervousness=_number(stats_data, "nervousness", path),
        ),
        traits=tuple(_string_value(item, "trait", path) for item in traits),
    )


def _parse_track(data: JsonObject, path: Path) -> Track:
    segments = _list(data, "segments", path)
    return Track(
        track_id=_string(data, "track_id", path),
        name=_string(data, "name", path),
        length_m=_number(data, "length_m", path),
        surface=_string(data, "surface", path),
        lanes=_integer(data, "lanes", path),
        handedness=_string(data, "handedness", path),
        final_stretch_start_m=_number(data, "final_stretch_start_m", path),
        audio_profile=_string_mapping(_object(data, "audio_profile", path), path),
        segments=tuple(_parse_segment(_object_value(item, "segment", path), path) for item in segments),
    )


def _parse_segment(data: JsonObject, path: Path) -> TrackSegment:
    return TrackSegment(
        start_m=_number(data, "start_m", path),
        end_m=_number(data, "end_m", path),
        curve_direction=_string(data, "curve_direction", path),
        curve_intensity=_number(data, "curve_intensity", path),
        slope=_number(data, "slope", path),
        audio_marker=_string(data, "audio_marker", path),
    )


def _parse_sound_asset(data: JsonObject, path: Path) -> SoundAsset:
    return SoundAsset(
        sound_id=_string(data, "sound_id", path),
        path=Path(_string(data, "path", path)),
        source=_string(data, "source", path),
        license=_string(data, "license", path),
        category=_string(data, "category", path),
        loop=_boolean(data, "loop", path),
        default_volume=_number(data, "default_volume", path),
        priority=_integer(data, "priority", path),
    )


def _parse_weather(data: JsonObject, path: Path) -> Weather:
    return Weather(
        weather_id=_string(data, "weather_id", path),
        name=_string(data, "name", path),
        speed_modifier=_number(data, "speed_modifier", path),
        stamina_cost_multiplier=_number(data, "stamina_cost_multiplier", path),
        stability_modifier=_number(data, "stability_modifier", path),
        ambient_sound_id=_optional_string(data, "ambient_sound_id", path),
    )


def _parse_rival(data: JsonObject, path: Path) -> RivalProfile:
    return RivalProfile(
        horse_id=_string(data, "horse_id", path),
        display_name=_string(data, "display_name", path),
        intro_line=_string(data, "intro_line", path),
        approach_line=_string(data, "approach_line", path),
        passing_line=_string(data, "passing_line", path),
    )


def _parse_stable(data: JsonObject, path: Path) -> Stable:
    return Stable(
        stable_id=_string(data, "stable_id", path),
        name=_string(data, "name", path),
        focus=_string(data, "focus", path),
        description=_string(data, "description", path),
        speed_modifier=_number(data, "speed_modifier", path),
        stamina_modifier=_number(data, "stamina_modifier", path),
        handling_modifier=_number(data, "handling_modifier", path),
        calm_modifier=_number(data, "calm_modifier", path),
    )


def _object(data: JsonObject, key: str, path: Path) -> JsonObject:
    if key not in data:
        raise ValueError(f"Missing '{key}' in {path}")
    return _object_value(data[key], key, path)


def _object_value(value: object, label: str, path: Path) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError(f"Expected object for '{label}' in {path}")
    return value


def _string_mapping(data: JsonObject, path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(value, str):
            raise ValueError(f"Expected string value for '{key}' in {path}")
        result[key] = value
    return result


def _list(data: JsonObject, key: str, path: Path) -> list[object]:
    if key not in data:
        raise ValueError(f"Missing '{key}' in {path}")
    value = data[key]
    if not isinstance(value, list):
        raise ValueError(f"Expected list for '{key}' in {path}")
    return value


def _string(data: JsonObject, key: str, path: Path) -> str:
    if key not in data:
        raise ValueError(f"Missing '{key}' in {path}")
    return _string_value(data[key], key, path)


def _optional_string(data: JsonObject, key: str, path: Path) -> str | None:
    if key not in data:
        raise ValueError(f"Missing '{key}' in {path}")
    value = data[key]
    if value is None:
        return None
    return _string_value(value, key, path)


def _string_value(value: object, label: str, path: Path) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Expected string for '{label}' in {path}")
    return value


def _boolean_value(value: object, label: str, path: Path) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"Expected boolean for '{label}' in {path}")
    return value


def _number_value(value: object, label: str, path: Path) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"Expected number for '{label}' in {path}")
    return float(value)


def _integer_value(value: object, label: str, path: Path) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Expected integer for '{label}' in {path}")
    return value


def _number(data: JsonObject, key: str, path: Path) -> float:
    if key not in data:
        raise ValueError(f"Missing '{key}' in {path}")
    value = data[key]
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"Expected number for '{key}' in {path}")
    return float(value)


def _integer(data: JsonObject, key: str, path: Path) -> int:
    if key not in data:
        raise ValueError(f"Missing '{key}' in {path}")
    value = data[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Expected integer for '{key}' in {path}")
    return value


def _boolean(data: JsonObject, key: str, path: Path) -> bool:
    if key not in data:
        raise ValueError(f"Missing '{key}' in {path}")
    value = data[key]
    if not isinstance(value, bool):
        raise ValueError(f"Expected boolean for '{key}' in {path}")
    return value



