from dataclasses import dataclass

from horse_racing_game.app.career import CAREER_LENGTH
from horse_racing_game.app.career_result_feedback import career_result_summary_text
from horse_racing_game.app.progress import GameProgress


@dataclass(frozen=True)
class PlayerStats:
    total_races: int
    quick_races: int
    career_races: int
    training_sessions: int
    career_points: int
    career_energy: int
    career_rewards: int
    difficulty_id: str
    audio_mix_id: str
    speech_verbosity: str
    language_id: str
    controller_profile_id: str
    mobile_gesture_profile_id: str
    haptics_enabled: bool
    controller_only_navigation: bool
    best_rank: int | None
    wins: int
    podiums: int
    win_rate_percent: float
    career_complete: bool
    career_title: str
    trained_horses: int
    rivals_encountered: int
    stable_id: str
    last_online_race_summary: dict | None
    last_career_result_summary: dict | None
    last_time_trial_summary: dict | None
    last_ghost_race_summary: dict | None


def compute_player_stats(
    progress: GameProgress,
    best_rank: int | None = None,
    wins: int | None = None,
    podiums: int | None = None,
    total_races: int | None = None,
) -> PlayerStats:
    from horse_racing_game.app.career import career_title

    quick = progress.quick_races_completed
    career = progress.career_races_completed
    training = sum(progress.horse_training_levels.values())
    rivals = len(progress.rival_encounters)

    if total_races is None:
        total_races = progress.finished_races + training
    if wins is None:
        wins = progress.wins
    if podiums is None:
        podiums = progress.podiums
    if best_rank is None:
        best_rank = progress.best_rank

    win_rate = (wins / total_races * 100.0) if total_races > 0 else 0.0

    return PlayerStats(
        total_races=total_races,
        quick_races=quick,
        career_races=career,
        training_sessions=training,
        career_points=progress.career_points,
        career_energy=progress.career_energy,
        career_rewards=progress.career_rewards,
        difficulty_id=progress.last_difficulty_id,
        audio_mix_id=progress.last_audio_mix_id,
        speech_verbosity=progress.speech_verbosity,
        language_id=progress.language_id,
        controller_profile_id=progress.controller_profile_id,
        mobile_gesture_profile_id=progress.mobile_gesture_profile_id,
        haptics_enabled=progress.haptics_enabled,
        controller_only_navigation=progress.controller_only_navigation,
        best_rank=best_rank,
        wins=wins,
        podiums=podiums,
        win_rate_percent=round(win_rate, 1),
        career_complete=career >= CAREER_LENGTH,
        career_title=career_title(progress.career_points, career),
        trained_horses=len([v for v in progress.horse_training_levels.values() if v > 0]),
        rivals_encountered=rivals,
        stable_id=progress.last_stable_id,
        last_online_race_summary=progress.last_online_race_summary,
        last_career_result_summary=progress.last_career_result_summary,
        last_time_trial_summary=progress.last_time_trial_summary,
        last_ghost_race_summary=progress.last_ghost_race_summary,
    )


def stats_summary_text(stats: PlayerStats) -> str:
    lines = [
        f"Total races: {stats.total_races}.",
        f"Quick races: {stats.quick_races}. Career races: {stats.career_races}.",
        f"Training sessions: {stats.training_sessions}.",
    ]
    if stats.best_rank is not None:
        lines.append(f"Best rank: {stats.best_rank}.")
    lines.append(f"Wins: {stats.wins}. Podiums: {stats.podiums}. Win rate: {stats.win_rate_percent} percent.")
    lines.append(stats.career_title)
    lines.append(f"Stable: {stats.stable_id}. Difficulty: {stats.difficulty_id}.")
    lines.append(
        f"Settings: audio {stats.audio_mix_id}. Speech {stats.speech_verbosity}. Language {stats.language_id}."
    )
    lines.append(
        "Controls: "
        f"{stats.controller_profile_id}. Mobile gestures {stats.mobile_gesture_profile_id}. "
        f"Haptics {'on' if stats.haptics_enabled else 'off'}. "
        f"Controller-only navigation {'on' if stats.controller_only_navigation else 'off'}."
    )
    lines.append(f"Career energy: {stats.career_energy}. Rewards: {stats.career_rewards}.")
    lines.append(f"Trained horses: {stats.trained_horses}. Rivals encountered: {stats.rivals_encountered}.")
    if stats.last_career_result_summary is not None:
        lines.append(f"Last career result: {career_result_summary_text(stats.last_career_result_summary)}")
    if stats.last_time_trial_summary is not None:
        summary = stats.last_time_trial_summary
        best = summary.get("best_s", "?")
        result = "personal best" if summary.get("personal_best") else "completed"
        lines.append(
            "Last time trial: "
            f"{summary.get('elapsed_s', '?')} seconds | best {best} | {result}."
        )
    if stats.last_ghost_race_summary is not None:
        summary = stats.last_ghost_race_summary
        ghost_time = summary.get("ghost_elapsed_s")
        if ghost_time is None:
            lines.append(f"Last ghost race: {summary.get('elapsed_s', '?')} seconds | no ghost saved.")
        else:
            result = "beat ghost" if summary.get("beat_ghost") else "ghost ahead"
            lines.append(
                "Last ghost race: "
                f"{summary.get('elapsed_s', '?')} seconds | ghost {ghost_time} | {result}."
            )
    if stats.last_online_race_summary is not None:
        summary = stats.last_online_race_summary
        lines.append(
            "Last online race: "
            f"rank {summary.get('rank', '?')} | "
            f"ticks {summary.get('ticks', '?')} | "
            f"distance {summary.get('distance_m', '?')} m."
        )
    return " ".join(lines)
