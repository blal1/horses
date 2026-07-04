from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from horse_racing_game.app.career import (
    CAREER_LENGTH,
    DEFAULT_CAREER_ENERGY,
    MAX_CAREER_ENERGY,
    career_reward_for_rank,
    clamp_career_energy,
    points_for_rank,
)
from horse_racing_game.app.career_depth import career_contract_by_id
from horse_racing_game.app.career_depth import (
    HorseCondition,
    career_condition_after_event,
    career_condition_after_rest,
)
from horse_racing_game.app.difficulty import difficulty_by_id
from horse_racing_game.app.file_directories import FileDirectories
from horse_racing_game.app.savedata import read_secure_object_migrating_plaintext, write_secure_json
from horse_racing_game.app.stable_management import stable_rest_energy_gain, stable_staff_weekly_cost
from horse_racing_game.app.training import next_training_level


@dataclass(frozen=True)
class GameProgress:
    quick_races_completed: int = 0
    tutorial_completed: bool = False
    last_horse_id: str = "ember_stride"
    last_track_id: str = "ashford_oval"
    last_weather_id: str = "clear"
    last_audio_mix_id: str = "normal"
    last_stable_id: str = "oak_lane"
    last_difficulty_id: str = "pro"
    speech_verbosity: str = "standard"
    language_id: str = "en-US"
    controller_profile_id: str = "controller-default"
    mobile_gesture_profile_id: str = "android-default"
    haptics_enabled: bool = False
    controller_only_navigation: bool = False
    career_races_completed: int = 0
    career_points: int = 0
    career_energy: int = DEFAULT_CAREER_ENERGY
    career_fatigue: int = 0
    career_injury_days: int = 0
    career_rewards: int = 0
    finished_races: int = 0
    wins: int = 0
    podiums: int = 0
    best_rank: int | None = None
    horse_training_levels: dict[str, int] = field(default_factory=dict)
    rival_encounters: dict[str, int] = field(default_factory=dict)
    rival_championship_points: dict[str, int] = field(default_factory=dict)
    rival_championship_races: dict[str, int] = field(default_factory=dict)
    last_replay_lines: tuple[str, ...] = ()
    last_replay: dict | None = None
    best_time_trial_times: dict[str, float] = field(default_factory=dict)
    last_time_trial_summary: dict | None = None
    last_ghost_race_summary: dict | None = None
    last_online_race_summary: dict | None = None
    last_online_room_code: str | None = None
    last_online_host: str | None = None
    last_online_port: int | None = None
    last_online_peer_id: str | None = None
    last_online_ready: bool = False
    active_career_contract_id: str | None = None
    stable_upgrade_ids: tuple[str, ...] = ()
    stable_staff_ids: tuple[str, ...] = ()
    last_career_result_summary: dict | None = None


def progress_path(project_root: Path) -> Path:
    return FileDirectories(project_root).progress_file()


def load_progress(project_root: Path) -> GameProgress:
    path = progress_path(project_root)
    data = read_secure_object_migrating_plaintext(path)
    if data is None:
        return GameProgress()
    return GameProgress(
        quick_races_completed=_non_negative_int(data.get("quick_races_completed"), 0),
        tutorial_completed=bool(data.get("tutorial_completed", False)),
        last_horse_id=str(data.get("last_horse_id") or "ember_stride"),
        last_track_id=str(data.get("last_track_id") or "ashford_oval"),
        last_weather_id=str(data.get("last_weather_id") or "clear"),
        last_audio_mix_id=str(data.get("last_audio_mix_id") or "normal"),
        last_stable_id=str(data.get("last_stable_id") or "oak_lane"),
        last_difficulty_id=str(data.get("last_difficulty_id") or "pro"),
        speech_verbosity=_choice(data.get("speech_verbosity"), {"minimal", "standard", "detailed"}, "standard"),
        language_id=str(data.get("language_id") or "en-US"),
        controller_profile_id=str(data.get("controller_profile_id") or "controller-default"),
        mobile_gesture_profile_id=str(data.get("mobile_gesture_profile_id") or "android-default"),
        haptics_enabled=bool(data.get("haptics_enabled", False)),
        controller_only_navigation=bool(data.get("controller_only_navigation", False)),
        career_races_completed=min(_non_negative_int(data.get("career_races_completed"), 0), _career_cap(project_root)),
        career_points=_non_negative_int(data.get("career_points"), 0),
        career_energy=clamp_career_energy(_non_negative_int(data.get("career_energy"), DEFAULT_CAREER_ENERGY)),
        career_fatigue=min(_non_negative_int(data.get("career_fatigue"), 0), 100),
        career_injury_days=_non_negative_int(data.get("career_injury_days"), 0),
        career_rewards=_non_negative_int(data.get("career_rewards"), 0),
        finished_races=_non_negative_int(data.get("finished_races"), 0),
        wins=_non_negative_int(data.get("wins"), 0),
        podiums=_non_negative_int(data.get("podiums"), 0),
        best_rank=_optional_positive_int(data.get("best_rank")),
        horse_training_levels=_training_levels(data.get("horse_training_levels")),
        rival_encounters=_training_levels(data.get("rival_encounters")),
        rival_championship_points=_training_levels(data.get("rival_championship_points")),
        rival_championship_races=_training_levels(data.get("rival_championship_races")),
        last_replay_lines=_string_tuple(data.get("last_replay_lines")),
        last_replay=_replay_dict(data.get("last_replay")),
        best_time_trial_times=_float_dict(data.get("best_time_trial_times")),
        last_time_trial_summary=_replay_dict(data.get("last_time_trial_summary")),
        last_ghost_race_summary=_replay_dict(data.get("last_ghost_race_summary")),
        last_online_race_summary=_replay_dict(data.get("last_online_race_summary")),
        last_online_room_code=_optional_string(data.get("last_online_room_code")),
        last_online_host=_optional_string(data.get("last_online_host")),
        last_online_port=_optional_positive_int(data.get("last_online_port")),
        last_online_peer_id=_optional_string(data.get("last_online_peer_id")),
        last_online_ready=bool(data.get("last_online_ready", False)),
        active_career_contract_id=_optional_string(data.get("active_career_contract_id")),
        stable_upgrade_ids=_string_tuple(data.get("stable_upgrade_ids")),
        stable_staff_ids=_string_tuple(data.get("stable_staff_ids")),
        last_career_result_summary=_replay_dict(data.get("last_career_result_summary")),
    )


def save_progress(project_root: Path, progress: GameProgress) -> None:
    path = progress_path(project_root)
    write_secure_json(path, asdict(progress))


def record_race_result(
    project_root: Path,
    progress: GameProgress,
    horse_id: str,
    track_id: str,
    is_tutorial: bool,
    finished: bool,
    is_career: bool = False,
    is_training: bool = False,
    rank: int | None = None,
    weather_id: str = "clear",
    audio_mix_id: str = "normal",
    stable_id: str = "oak_lane",
    difficulty_id: str = "pro",
    career_difficulty_id: str | None = None,
    replay_lines: tuple[str, ...] = (),
    replay: dict | None = None,
    career_length: int = CAREER_LENGTH,
    count_quick_race: bool = True,
) -> GameProgress:
    career_races_completed = progress.career_races_completed
    career_points = progress.career_points
    career_energy = progress.career_energy
    career_fatigue = progress.career_fatigue
    career_injury_days = progress.career_injury_days
    career_rewards = progress.career_rewards
    career_result_summary = progress.last_career_result_summary
    if is_career and not finished:
        career_result_summary = {
            "finished": False,
            "is_training": is_training,
            "rank": rank,
            "base_reward": 0,
            "contract_reward": 0,
            "staff_upkeep": 0,
            "fatigue_before": career_fatigue,
            "fatigue_after": career_fatigue,
            "injury_days": career_injury_days,
            "net_reward": 0,
            "rewards_balance": career_rewards,
        }
    elif finished and is_career and career_races_completed < career_length:
        reward_tier = difficulty_by_id(career_difficulty_id) if career_difficulty_id else None
        reward_multiplier = reward_tier.reward_multiplier if reward_tier else 1.0
        base_reward = max(1, round(career_reward_for_rank(rank or 99) * reward_multiplier))
        contract_reward = 0
        staff_upkeep = 0 if is_training else stable_staff_weekly_cost(progress.stable_staff_ids)
        career_races_completed += 1
        career_points += points_for_rank(rank or 99)
        career_energy = clamp_career_energy(career_energy - 1)
        condition_after = career_condition_after_event(
            HorseCondition(horse_id, fatigue=career_fatigue, injury_days_remaining=career_injury_days),
            energy=progress.career_energy,
            rank=rank,
            is_training=is_training,
            staff_ids=progress.stable_staff_ids,
        )
        fatigue_before = career_fatigue
        career_fatigue = condition_after.fatigue
        career_injury_days = condition_after.injury_days_remaining
        career_rewards += base_reward
        if progress.active_career_contract_id:
            contract = career_contract_by_id(progress.active_career_contract_id)
            if contract is not None:
                contract_reward = contract.prize_for_rank(rank or 99)
                career_rewards += contract_reward
        paid_upkeep = min(career_rewards, staff_upkeep)
        career_rewards -= paid_upkeep
        career_result_summary = {
            "finished": True,
            "is_training": is_training,
            "rank": rank,
            "base_reward": base_reward,
            "contract_reward": contract_reward,
            "staff_upkeep": paid_upkeep,
            "fatigue_before": fatigue_before,
            "fatigue_after": career_fatigue,
            "injury_days": career_injury_days,
            "net_reward": base_reward + contract_reward - paid_upkeep,
            "rewards_balance": career_rewards,
            "difficulty_tier": reward_tier.name if reward_tier else None,
            "reward_multiplier": reward_multiplier,
        }
    training_levels = dict(progress.horse_training_levels or {})
    if is_training:
        training_levels[horse_id] = next_training_level(training_levels.get(horse_id, 0), finished)
        if finished and is_career:
            career_energy = clamp_career_energy(career_energy - 1)
    finished_races = progress.finished_races
    wins = progress.wins
    podiums = progress.podiums
    best_rank = progress.best_rank
    if finished and not is_training:
        finished_races += 1
        if rank == 1:
            wins += 1
        if rank is not None and rank <= 3:
            podiums += 1
        if rank is not None:
            best_rank = rank if best_rank is None else min(best_rank, rank)

    updated = GameProgress(
        quick_races_completed=progress.quick_races_completed
        + (1 if count_quick_race and finished and not is_tutorial and not is_career and not is_training else 0),
        tutorial_completed=progress.tutorial_completed or (finished and is_tutorial),
        last_horse_id=horse_id,
        last_track_id=track_id,
        last_weather_id=weather_id,
        last_audio_mix_id=audio_mix_id,
        last_stable_id=stable_id,
        last_difficulty_id=difficulty_id,
        speech_verbosity=progress.speech_verbosity,
        language_id=progress.language_id,
        controller_profile_id=progress.controller_profile_id,
        mobile_gesture_profile_id=progress.mobile_gesture_profile_id,
        haptics_enabled=progress.haptics_enabled,
        controller_only_navigation=progress.controller_only_navigation,
        career_races_completed=career_races_completed,
        career_points=career_points,
        career_energy=career_energy,
        career_fatigue=career_fatigue,
        career_injury_days=career_injury_days,
        career_rewards=career_rewards,
        finished_races=finished_races,
        wins=wins,
        podiums=podiums,
        best_rank=best_rank,
        horse_training_levels=training_levels,
        rival_encounters=dict(progress.rival_encounters),
        rival_championship_points=dict(progress.rival_championship_points),
        rival_championship_races=dict(progress.rival_championship_races),
        last_replay_lines=replay_lines or progress.last_replay_lines,
        last_replay=replay if replay is not None else progress.last_replay,
        best_time_trial_times=dict(progress.best_time_trial_times),
        last_time_trial_summary=progress.last_time_trial_summary,
        last_ghost_race_summary=progress.last_ghost_race_summary,
        last_online_race_summary=progress.last_online_race_summary,
        last_online_room_code=progress.last_online_room_code,
        last_online_host=progress.last_online_host,
        last_online_port=progress.last_online_port,
        last_online_peer_id=progress.last_online_peer_id,
        last_online_ready=progress.last_online_ready,
        active_career_contract_id=progress.active_career_contract_id,
        stable_upgrade_ids=progress.stable_upgrade_ids,
        stable_staff_ids=progress.stable_staff_ids,
        last_career_result_summary=career_result_summary,
    )
    save_progress(project_root, updated)
    return updated


def record_online_race_summary(project_root: Path, summary: dict) -> GameProgress:
    progress = load_progress(project_root)
    updated = GameProgress(
        quick_races_completed=progress.quick_races_completed,
        tutorial_completed=progress.tutorial_completed,
        last_horse_id=progress.last_horse_id,
        last_track_id=progress.last_track_id,
        last_weather_id=progress.last_weather_id,
        last_audio_mix_id=progress.last_audio_mix_id,
        last_stable_id=progress.last_stable_id,
        last_difficulty_id=progress.last_difficulty_id,
        speech_verbosity=progress.speech_verbosity,
        language_id=progress.language_id,
        controller_profile_id=progress.controller_profile_id,
        mobile_gesture_profile_id=progress.mobile_gesture_profile_id,
        haptics_enabled=progress.haptics_enabled,
        controller_only_navigation=progress.controller_only_navigation,
        career_races_completed=progress.career_races_completed,
        career_points=progress.career_points,
        career_energy=progress.career_energy,
        career_fatigue=progress.career_fatigue,
        career_injury_days=progress.career_injury_days,
        career_rewards=progress.career_rewards,
        finished_races=progress.finished_races,
        wins=progress.wins,
        podiums=progress.podiums,
        best_rank=progress.best_rank,
        horse_training_levels=dict(progress.horse_training_levels),
        rival_encounters=dict(progress.rival_encounters),
        rival_championship_points=dict(progress.rival_championship_points),
        rival_championship_races=dict(progress.rival_championship_races),
        last_replay_lines=progress.last_replay_lines,
        last_replay=progress.last_replay,
        best_time_trial_times=dict(progress.best_time_trial_times),
        last_time_trial_summary=progress.last_time_trial_summary,
        last_ghost_race_summary=progress.last_ghost_race_summary,
        last_online_race_summary=summary,
        last_online_room_code=progress.last_online_room_code,
        last_online_host=progress.last_online_host,
        last_online_port=progress.last_online_port,
        last_online_peer_id=progress.last_online_peer_id,
        last_online_ready=progress.last_online_ready,
        active_career_contract_id=progress.active_career_contract_id,
        stable_upgrade_ids=progress.stable_upgrade_ids,
        stable_staff_ids=progress.stable_staff_ids,
        last_career_result_summary=progress.last_career_result_summary,
    )
    save_progress(project_root, updated)
    return updated


def record_time_trial_result(
    project_root: Path,
    progress: GameProgress,
    *,
    horse_id: str,
    track_id: str,
    weather_id: str,
    elapsed_s: float,
    finished: bool,
) -> GameProgress:
    if elapsed_s < 0.0:
        raise ValueError("elapsed_s must be non-negative")
    key = time_trial_key(horse_id, track_id, weather_id)
    best_times = dict(progress.best_time_trial_times)
    previous_best = best_times.get(key)
    is_personal_best = bool(finished and (previous_best is None or elapsed_s < previous_best))
    if is_personal_best:
        best_times[key] = round(elapsed_s, 3)
    summary = {
        "horse_id": horse_id,
        "track_id": track_id,
        "weather_id": weather_id,
        "elapsed_s": round(elapsed_s, 3),
        "finished": finished,
        "previous_best_s": previous_best,
        "best_s": best_times.get(key),
        "personal_best": is_personal_best,
    }
    updated = replace(
        progress,
        best_time_trial_times=best_times,
        last_time_trial_summary=summary,
    )
    save_progress(project_root, updated)
    return updated


def record_ghost_race_result(
    project_root: Path,
    progress: GameProgress,
    *,
    horse_id: str,
    track_id: str,
    weather_id: str,
    elapsed_s: float,
    finished: bool,
    ghost_elapsed_s: float | None,
) -> GameProgress:
    if elapsed_s < 0.0:
        raise ValueError("elapsed_s must be non-negative")
    if ghost_elapsed_s is not None and ghost_elapsed_s < 0.0:
        raise ValueError("ghost_elapsed_s must be non-negative when provided")
    delta_s = None if ghost_elapsed_s is None else round(elapsed_s - ghost_elapsed_s, 3)
    summary = {
        "horse_id": horse_id,
        "track_id": track_id,
        "weather_id": weather_id,
        "elapsed_s": round(elapsed_s, 3),
        "finished": finished,
        "ghost_elapsed_s": None if ghost_elapsed_s is None else round(ghost_elapsed_s, 3),
        "delta_s": delta_s,
        "beat_ghost": bool(finished and ghost_elapsed_s is not None and elapsed_s < ghost_elapsed_s),
    }
    updated = replace(progress, last_ghost_race_summary=summary)
    save_progress(project_root, updated)
    return updated


def record_user_settings(
    project_root: Path,
    progress: GameProgress,
    *,
    audio_mix_id: str | None = None,
    speech_verbosity: str | None = None,
    language_id: str | None = None,
    controller_profile_id: str | None = None,
    mobile_gesture_profile_id: str | None = None,
    haptics_enabled: bool | None = None,
    controller_only_navigation: bool | None = None,
) -> GameProgress:
    if speech_verbosity is not None and speech_verbosity not in {"minimal", "standard", "detailed"}:
        raise ValueError("invalid speech verbosity")
    updated = replace(
        progress,
        last_audio_mix_id=audio_mix_id or progress.last_audio_mix_id,
        speech_verbosity=speech_verbosity or progress.speech_verbosity,
        language_id=language_id or progress.language_id,
        controller_profile_id=controller_profile_id or progress.controller_profile_id,
        mobile_gesture_profile_id=mobile_gesture_profile_id or progress.mobile_gesture_profile_id,
        haptics_enabled=progress.haptics_enabled if haptics_enabled is None else haptics_enabled,
        controller_only_navigation=(
            progress.controller_only_navigation
            if controller_only_navigation is None
            else controller_only_navigation
        ),
    )
    save_progress(project_root, updated)
    return updated


def time_trial_key(horse_id: str, track_id: str, weather_id: str) -> str:
    return f"{horse_id}|{track_id}|{weather_id}"


def record_online_lobby_settings(
    project_root: Path,
    room_code: str,
    host: str,
    port: int,
    peer_id: str,
    ready: bool,
) -> GameProgress:
    progress = load_progress(project_root)
    updated = GameProgress(
        quick_races_completed=progress.quick_races_completed,
        tutorial_completed=progress.tutorial_completed,
        last_horse_id=progress.last_horse_id,
        last_track_id=progress.last_track_id,
        last_weather_id=progress.last_weather_id,
        last_audio_mix_id=progress.last_audio_mix_id,
        last_stable_id=progress.last_stable_id,
        last_difficulty_id=progress.last_difficulty_id,
        speech_verbosity=progress.speech_verbosity,
        language_id=progress.language_id,
        controller_profile_id=progress.controller_profile_id,
        mobile_gesture_profile_id=progress.mobile_gesture_profile_id,
        haptics_enabled=progress.haptics_enabled,
        controller_only_navigation=progress.controller_only_navigation,
        career_races_completed=progress.career_races_completed,
        career_points=progress.career_points,
        career_energy=progress.career_energy,
        career_fatigue=progress.career_fatigue,
        career_injury_days=progress.career_injury_days,
        career_rewards=progress.career_rewards,
        finished_races=progress.finished_races,
        wins=progress.wins,
        podiums=progress.podiums,
        best_rank=progress.best_rank,
        horse_training_levels=dict(progress.horse_training_levels),
        rival_encounters=dict(progress.rival_encounters),
        rival_championship_points=dict(progress.rival_championship_points),
        rival_championship_races=dict(progress.rival_championship_races),
        last_replay_lines=progress.last_replay_lines,
        last_replay=progress.last_replay,
        best_time_trial_times=dict(progress.best_time_trial_times),
        last_time_trial_summary=progress.last_time_trial_summary,
        last_ghost_race_summary=progress.last_ghost_race_summary,
        last_online_race_summary=progress.last_online_race_summary,
        last_online_room_code=room_code,
        last_online_host=host,
        last_online_port=port,
        last_online_peer_id=peer_id,
        last_online_ready=ready,
        active_career_contract_id=progress.active_career_contract_id,
        stable_upgrade_ids=progress.stable_upgrade_ids,
        stable_staff_ids=progress.stable_staff_ids,
        last_career_result_summary=progress.last_career_result_summary,
    )
    save_progress(project_root, updated)
    return updated


def record_rival_encounter(project_root: Path, progress: GameProgress, rival_horse_id: str) -> GameProgress:
    encounters = dict(progress.rival_encounters)
    encounters[rival_horse_id] = encounters.get(rival_horse_id, 0) + 1
    updated = GameProgress(
        quick_races_completed=progress.quick_races_completed,
        tutorial_completed=progress.tutorial_completed,
        last_horse_id=progress.last_horse_id,
        last_track_id=progress.last_track_id,
        last_weather_id=progress.last_weather_id,
        last_audio_mix_id=progress.last_audio_mix_id,
        last_stable_id=progress.last_stable_id,
        last_difficulty_id=progress.last_difficulty_id,
        speech_verbosity=progress.speech_verbosity,
        language_id=progress.language_id,
        controller_profile_id=progress.controller_profile_id,
        mobile_gesture_profile_id=progress.mobile_gesture_profile_id,
        haptics_enabled=progress.haptics_enabled,
        controller_only_navigation=progress.controller_only_navigation,
        career_races_completed=progress.career_races_completed,
        career_points=progress.career_points,
        career_energy=progress.career_energy,
        career_fatigue=progress.career_fatigue,
        career_injury_days=progress.career_injury_days,
        career_rewards=progress.career_rewards,
        finished_races=progress.finished_races,
        wins=progress.wins,
        podiums=progress.podiums,
        best_rank=progress.best_rank,
        horse_training_levels=dict(progress.horse_training_levels),
        rival_encounters=encounters,
        rival_championship_points=dict(progress.rival_championship_points),
        rival_championship_races=dict(progress.rival_championship_races),
        last_replay_lines=progress.last_replay_lines,
        last_replay=progress.last_replay,
        best_time_trial_times=dict(progress.best_time_trial_times),
        last_time_trial_summary=progress.last_time_trial_summary,
        last_ghost_race_summary=progress.last_ghost_race_summary,
        last_online_race_summary=progress.last_online_race_summary,
        last_online_room_code=progress.last_online_room_code,
        last_online_host=progress.last_online_host,
        last_online_port=progress.last_online_port,
        last_online_peer_id=progress.last_online_peer_id,
        last_online_ready=progress.last_online_ready,
        active_career_contract_id=progress.active_career_contract_id,
        stable_upgrade_ids=progress.stable_upgrade_ids,
        stable_staff_ids=progress.stable_staff_ids,
        last_career_result_summary=progress.last_career_result_summary,
    )
    save_progress(project_root, updated)
    return updated


def record_rival_championship_result(
    project_root: Path,
    progress: GameProgress,
    rival_horse_id: str,
    points: int,
) -> GameProgress:
    rival_points = dict(progress.rival_championship_points)
    rival_races = dict(progress.rival_championship_races)
    rival_points[rival_horse_id] = rival_points.get(rival_horse_id, 0) + max(points, 0)
    rival_races[rival_horse_id] = rival_races.get(rival_horse_id, 0) + 1
    updated = GameProgress(
        quick_races_completed=progress.quick_races_completed,
        tutorial_completed=progress.tutorial_completed,
        last_horse_id=progress.last_horse_id,
        last_track_id=progress.last_track_id,
        last_weather_id=progress.last_weather_id,
        last_audio_mix_id=progress.last_audio_mix_id,
        last_stable_id=progress.last_stable_id,
        last_difficulty_id=progress.last_difficulty_id,
        speech_verbosity=progress.speech_verbosity,
        language_id=progress.language_id,
        controller_profile_id=progress.controller_profile_id,
        mobile_gesture_profile_id=progress.mobile_gesture_profile_id,
        haptics_enabled=progress.haptics_enabled,
        controller_only_navigation=progress.controller_only_navigation,
        career_races_completed=progress.career_races_completed,
        career_points=progress.career_points,
        career_energy=progress.career_energy,
        career_fatigue=progress.career_fatigue,
        career_injury_days=progress.career_injury_days,
        career_rewards=progress.career_rewards,
        finished_races=progress.finished_races,
        wins=progress.wins,
        podiums=progress.podiums,
        best_rank=progress.best_rank,
        horse_training_levels=dict(progress.horse_training_levels),
        rival_encounters=dict(progress.rival_encounters),
        rival_championship_points=rival_points,
        rival_championship_races=rival_races,
        last_replay_lines=progress.last_replay_lines,
        last_replay=progress.last_replay,
        best_time_trial_times=dict(progress.best_time_trial_times),
        last_time_trial_summary=progress.last_time_trial_summary,
        last_ghost_race_summary=progress.last_ghost_race_summary,
        last_online_race_summary=progress.last_online_race_summary,
        last_online_room_code=progress.last_online_room_code,
        last_online_host=progress.last_online_host,
        last_online_port=progress.last_online_port,
        last_online_peer_id=progress.last_online_peer_id,
        last_online_ready=progress.last_online_ready,
        active_career_contract_id=progress.active_career_contract_id,
        stable_upgrade_ids=progress.stable_upgrade_ids,
        stable_staff_ids=progress.stable_staff_ids,
        last_career_result_summary=progress.last_career_result_summary,
    )
    save_progress(project_root, updated)
    return updated


def record_track_editor_selection(project_root: Path, track_id: str) -> GameProgress:
    progress = load_progress(project_root)
    updated = GameProgress(
        quick_races_completed=progress.quick_races_completed,
        tutorial_completed=progress.tutorial_completed,
        last_horse_id=progress.last_horse_id,
        last_track_id=track_id,
        last_weather_id=progress.last_weather_id,
        last_audio_mix_id=progress.last_audio_mix_id,
        last_stable_id=progress.last_stable_id,
        last_difficulty_id=progress.last_difficulty_id,
        speech_verbosity=progress.speech_verbosity,
        language_id=progress.language_id,
        controller_profile_id=progress.controller_profile_id,
        mobile_gesture_profile_id=progress.mobile_gesture_profile_id,
        haptics_enabled=progress.haptics_enabled,
        controller_only_navigation=progress.controller_only_navigation,
        career_races_completed=progress.career_races_completed,
        career_points=progress.career_points,
        career_energy=progress.career_energy,
        career_fatigue=progress.career_fatigue,
        career_injury_days=progress.career_injury_days,
        career_rewards=progress.career_rewards,
        finished_races=progress.finished_races,
        wins=progress.wins,
        podiums=progress.podiums,
        best_rank=progress.best_rank,
        horse_training_levels=dict(progress.horse_training_levels),
        rival_encounters=dict(progress.rival_encounters),
        rival_championship_points=dict(progress.rival_championship_points),
        rival_championship_races=dict(progress.rival_championship_races),
        last_replay_lines=progress.last_replay_lines,
        last_replay=progress.last_replay,
        best_time_trial_times=dict(progress.best_time_trial_times),
        last_time_trial_summary=progress.last_time_trial_summary,
        last_ghost_race_summary=progress.last_ghost_race_summary,
        last_online_race_summary=progress.last_online_race_summary,
        last_online_room_code=progress.last_online_room_code,
        last_online_host=progress.last_online_host,
        last_online_port=progress.last_online_port,
        last_online_peer_id=progress.last_online_peer_id,
        last_online_ready=progress.last_online_ready,
        active_career_contract_id=progress.active_career_contract_id,
        stable_upgrade_ids=progress.stable_upgrade_ids,
        stable_staff_ids=progress.stable_staff_ids,
        last_career_result_summary=progress.last_career_result_summary,
    )
    save_progress(project_root, updated)
    return updated


def record_career_rest(project_root: Path, progress: GameProgress, stable_id: str) -> GameProgress:
    rest_gain = stable_rest_energy_gain(progress.stable_upgrade_ids, progress.stable_staff_ids)
    condition_after = career_condition_after_rest(
        HorseCondition(
            progress.last_horse_id,
            fatigue=progress.career_fatigue,
            injury_days_remaining=progress.career_injury_days,
        ),
        rest_gain,
    )
    updated = GameProgress(
        quick_races_completed=progress.quick_races_completed,
        tutorial_completed=progress.tutorial_completed,
        last_horse_id=progress.last_horse_id,
        last_track_id=progress.last_track_id,
        last_weather_id=progress.last_weather_id,
        last_audio_mix_id=progress.last_audio_mix_id,
        last_stable_id=stable_id,
        last_difficulty_id=progress.last_difficulty_id,
        speech_verbosity=progress.speech_verbosity,
        language_id=progress.language_id,
        controller_profile_id=progress.controller_profile_id,
        mobile_gesture_profile_id=progress.mobile_gesture_profile_id,
        haptics_enabled=progress.haptics_enabled,
        controller_only_navigation=progress.controller_only_navigation,
        career_races_completed=progress.career_races_completed,
        career_points=progress.career_points,
        career_energy=clamp_career_energy(progress.career_energy + rest_gain),
        career_fatigue=condition_after.fatigue,
        career_injury_days=condition_after.injury_days_remaining,
        career_rewards=progress.career_rewards,
        finished_races=progress.finished_races,
        wins=progress.wins,
        podiums=progress.podiums,
        best_rank=progress.best_rank,
        horse_training_levels=dict(progress.horse_training_levels),
        rival_encounters=dict(progress.rival_encounters),
        rival_championship_points=dict(progress.rival_championship_points),
        rival_championship_races=dict(progress.rival_championship_races),
        last_replay_lines=progress.last_replay_lines,
        last_replay=progress.last_replay,
        best_time_trial_times=dict(progress.best_time_trial_times),
        last_time_trial_summary=progress.last_time_trial_summary,
        last_ghost_race_summary=progress.last_ghost_race_summary,
        last_online_race_summary=progress.last_online_race_summary,
        last_online_room_code=progress.last_online_room_code,
        last_online_host=progress.last_online_host,
        last_online_port=progress.last_online_port,
        last_online_peer_id=progress.last_online_peer_id,
        last_online_ready=progress.last_online_ready,
        active_career_contract_id=progress.active_career_contract_id,
        stable_upgrade_ids=progress.stable_upgrade_ids,
        stable_staff_ids=progress.stable_staff_ids,
        last_career_result_summary=progress.last_career_result_summary,
    )
    save_progress(project_root, updated)
    return updated


def record_career_contract(project_root: Path, progress: GameProgress, contract_id: str) -> GameProgress:
    if not contract_id:
        raise ValueError("contract_id must be non-empty")
    updated = GameProgress(
        quick_races_completed=progress.quick_races_completed,
        tutorial_completed=progress.tutorial_completed,
        last_horse_id=progress.last_horse_id,
        last_track_id=progress.last_track_id,
        last_weather_id=progress.last_weather_id,
        last_audio_mix_id=progress.last_audio_mix_id,
        last_stable_id=progress.last_stable_id,
        last_difficulty_id=progress.last_difficulty_id,
        speech_verbosity=progress.speech_verbosity,
        language_id=progress.language_id,
        controller_profile_id=progress.controller_profile_id,
        mobile_gesture_profile_id=progress.mobile_gesture_profile_id,
        haptics_enabled=progress.haptics_enabled,
        controller_only_navigation=progress.controller_only_navigation,
        career_races_completed=progress.career_races_completed,
        career_points=progress.career_points,
        career_energy=progress.career_energy,
        career_fatigue=progress.career_fatigue,
        career_injury_days=progress.career_injury_days,
        career_rewards=progress.career_rewards,
        finished_races=progress.finished_races,
        wins=progress.wins,
        podiums=progress.podiums,
        best_rank=progress.best_rank,
        horse_training_levels=dict(progress.horse_training_levels),
        rival_encounters=dict(progress.rival_encounters),
        rival_championship_points=dict(progress.rival_championship_points),
        rival_championship_races=dict(progress.rival_championship_races),
        last_replay_lines=progress.last_replay_lines,
        last_replay=progress.last_replay,
        best_time_trial_times=dict(progress.best_time_trial_times),
        last_time_trial_summary=progress.last_time_trial_summary,
        last_ghost_race_summary=progress.last_ghost_race_summary,
        last_online_race_summary=progress.last_online_race_summary,
        last_online_room_code=progress.last_online_room_code,
        last_online_host=progress.last_online_host,
        last_online_port=progress.last_online_port,
        last_online_peer_id=progress.last_online_peer_id,
        last_online_ready=progress.last_online_ready,
        active_career_contract_id=contract_id,
        stable_upgrade_ids=progress.stable_upgrade_ids,
        stable_staff_ids=progress.stable_staff_ids,
        last_career_result_summary=progress.last_career_result_summary,
    )
    save_progress(project_root, updated)
    return updated


def record_stable_upgrade_purchase(
    project_root: Path,
    progress: GameProgress,
    upgrade_id: str,
    cost: int,
) -> GameProgress:
    if not upgrade_id:
        raise ValueError("upgrade_id must be non-empty")
    if cost < 0:
        raise ValueError("cost must be non-negative")
    if upgrade_id in progress.stable_upgrade_ids:
        return progress
    if cost > progress.career_rewards:
        raise ValueError("not enough career rewards")
    updated = GameProgress(
        quick_races_completed=progress.quick_races_completed,
        tutorial_completed=progress.tutorial_completed,
        last_horse_id=progress.last_horse_id,
        last_track_id=progress.last_track_id,
        last_weather_id=progress.last_weather_id,
        last_audio_mix_id=progress.last_audio_mix_id,
        last_stable_id=progress.last_stable_id,
        last_difficulty_id=progress.last_difficulty_id,
        speech_verbosity=progress.speech_verbosity,
        language_id=progress.language_id,
        controller_profile_id=progress.controller_profile_id,
        mobile_gesture_profile_id=progress.mobile_gesture_profile_id,
        haptics_enabled=progress.haptics_enabled,
        controller_only_navigation=progress.controller_only_navigation,
        career_races_completed=progress.career_races_completed,
        career_points=progress.career_points,
        career_energy=progress.career_energy,
        career_fatigue=progress.career_fatigue,
        career_injury_days=progress.career_injury_days,
        career_rewards=progress.career_rewards - cost,
        finished_races=progress.finished_races,
        wins=progress.wins,
        podiums=progress.podiums,
        best_rank=progress.best_rank,
        horse_training_levels=dict(progress.horse_training_levels),
        rival_encounters=dict(progress.rival_encounters),
        rival_championship_points=dict(progress.rival_championship_points),
        rival_championship_races=dict(progress.rival_championship_races),
        last_replay_lines=progress.last_replay_lines,
        last_replay=progress.last_replay,
        best_time_trial_times=dict(progress.best_time_trial_times),
        last_time_trial_summary=progress.last_time_trial_summary,
        last_ghost_race_summary=progress.last_ghost_race_summary,
        last_online_race_summary=progress.last_online_race_summary,
        last_online_room_code=progress.last_online_room_code,
        last_online_host=progress.last_online_host,
        last_online_port=progress.last_online_port,
        last_online_peer_id=progress.last_online_peer_id,
        last_online_ready=progress.last_online_ready,
        active_career_contract_id=progress.active_career_contract_id,
        stable_upgrade_ids=tuple(sorted(progress.stable_upgrade_ids + (upgrade_id,))),
        stable_staff_ids=progress.stable_staff_ids,
        last_career_result_summary=progress.last_career_result_summary,
    )
    save_progress(project_root, updated)
    return updated


def record_stable_staff_hire(
    project_root: Path,
    progress: GameProgress,
    staff_id: str,
    cost: int,
) -> GameProgress:
    if not staff_id:
        raise ValueError("staff_id must be non-empty")
    if cost < 0:
        raise ValueError("cost must be non-negative")
    if staff_id in progress.stable_staff_ids:
        return progress
    if cost > progress.career_rewards:
        raise ValueError("not enough career rewards")
    updated = GameProgress(
        quick_races_completed=progress.quick_races_completed,
        tutorial_completed=progress.tutorial_completed,
        last_horse_id=progress.last_horse_id,
        last_track_id=progress.last_track_id,
        last_weather_id=progress.last_weather_id,
        last_audio_mix_id=progress.last_audio_mix_id,
        last_stable_id=progress.last_stable_id,
        last_difficulty_id=progress.last_difficulty_id,
        speech_verbosity=progress.speech_verbosity,
        language_id=progress.language_id,
        controller_profile_id=progress.controller_profile_id,
        mobile_gesture_profile_id=progress.mobile_gesture_profile_id,
        haptics_enabled=progress.haptics_enabled,
        controller_only_navigation=progress.controller_only_navigation,
        career_races_completed=progress.career_races_completed,
        career_points=progress.career_points,
        career_energy=progress.career_energy,
        career_fatigue=progress.career_fatigue,
        career_injury_days=progress.career_injury_days,
        career_rewards=progress.career_rewards - cost,
        finished_races=progress.finished_races,
        wins=progress.wins,
        podiums=progress.podiums,
        best_rank=progress.best_rank,
        horse_training_levels=dict(progress.horse_training_levels),
        rival_encounters=dict(progress.rival_encounters),
        rival_championship_points=dict(progress.rival_championship_points),
        rival_championship_races=dict(progress.rival_championship_races),
        last_replay_lines=progress.last_replay_lines,
        last_replay=progress.last_replay,
        best_time_trial_times=dict(progress.best_time_trial_times),
        last_time_trial_summary=progress.last_time_trial_summary,
        last_ghost_race_summary=progress.last_ghost_race_summary,
        last_online_race_summary=progress.last_online_race_summary,
        last_online_room_code=progress.last_online_room_code,
        last_online_host=progress.last_online_host,
        last_online_port=progress.last_online_port,
        last_online_peer_id=progress.last_online_peer_id,
        last_online_ready=progress.last_online_ready,
        active_career_contract_id=progress.active_career_contract_id,
        stable_upgrade_ids=progress.stable_upgrade_ids,
        stable_staff_ids=tuple(sorted(progress.stable_staff_ids + (staff_id,))),
        last_career_result_summary=progress.last_career_result_summary,
    )
    save_progress(project_root, updated)
    return updated


def _non_negative_int(value: object, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(parsed, 0)


def _training_levels(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    levels: dict[str, int] = {}
    for key, item in value.items():
        if isinstance(key, str):
            levels[key] = _non_negative_int(item, 0)
    return levels


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_positive_int(value: object) -> int | None:
    if value is None:
        return None
    parsed = _non_negative_int(value, 0)
    return parsed if parsed > 0 else None


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _replay_dict(value: object) -> dict | None:
    return value if isinstance(value, dict) else None


def _choice(value: object, allowed: set[str], fallback: str) -> str:
    return value if isinstance(value, str) and value in allowed else fallback


def _float_dict(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, float] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            continue
        try:
            parsed = float(item)
        except (TypeError, ValueError):
            continue
        if parsed >= 0.0:
            result[key] = parsed
    return result


def _career_cap(project_root: Path) -> int:
    """Data-driven cap for career progress: the championship calendar length when
    available, else the default. Used to sanitize stored values on load."""
    try:
        from horse_racing_game.app.championship import load_championship_calendar

        calendar = load_championship_calendar(project_root / "content" / "championship.json")
    except (OSError, ValueError):
        return CAREER_LENGTH
    return len(calendar) if calendar else CAREER_LENGTH
