from pathlib import Path
import argparse
import sys
import tempfile
import traceback

from horse_racing_game.app.career import CAREER_LENGTH, career_energy_modifier, career_title, points_for_rank
from horse_racing_game.app.bootstrap import build_quick_race_services
from horse_racing_game.app.championship import championship_title, load_championship_calendar, next_championship_race
from horse_racing_game.app.chat import ChatModerationPolicy, ChatSession, load_chat_session, save_chat_session
from horse_racing_game.app.config import AppConfig, default_config
from horse_racing_game.app.community import (
    CommunityHub,
    ModerationAction,
    ProfanityControl,
    RateLimitRule,
    load_community_hub,
    save_community_hub,
)
from horse_racing_game.app.career_result_feedback import career_result_summary_text
from horse_racing_game.app.diagnostics import build_diagnostic_report
from horse_racing_game.app.difficulty import career_difficulty, difficulty_by_id
from horse_racing_game.app.integrity import verify_integrity_manifest
from horse_racing_game.app.live_ops import (
    AnalyticsEvent,
    RemoteConfig,
    TelemetryStore,
    crash_report_from_exception,
    load_telemetry_store,
    save_telemetry_store,
)
from horse_racing_game.app.progress import (
    GameProgress,
    load_progress,
    record_career_rest,
    record_ghost_race_result,
    record_race_result,
    record_rival_championship_result,
    record_rival_encounter,
    record_time_trial_result,
    record_user_settings,
)
from horse_racing_game.app.profile import (
    claim_profile_starter_reward,
    equip_profile_badge,
    equip_profile_cosmetic,
    equip_profile_title,
    load_player_profile,
)
from horse_racing_game.app.replay import build_replay, build_replay_lines, reconstruct_race, replay_from_dict, replay_to_dict
from horse_racing_game.app.replay_exports import build_last_replay_share_bundle, load_replay_share_index, save_replay_share_bundle
from horse_racing_game.app.runtime_log import write_runtime_log
from horse_racing_game.app.social import (
    PlayerProfile as SocialPlayerProfile,
    Presence,
    SocialGraph,
    load_social_graph,
    save_social_graph,
)
from horse_racing_game.app.track_ecosystem import (
    EventRuleset,
    TrackCatalog,
    TrackRating,
    TrackShare,
    WeatherPreset,
    load_track_catalog,
    save_track_catalog,
)
from horse_racing_game.app.training import training_intro
from horse_racing_game.audio.speech import NullSpeaker, create_speaker
from horse_racing_game.ui.menu_models import MenuSelection
from horse_racing_game.ui.pygame_multiplayer import PygameMultiplayerRaceGame
from horse_racing_game.ui.pygame_game import PygameRaceGame, build_pygame_services
from horse_racing_game.ui.pygame_career_result import PygameCareerResultScreen
from horse_racing_game.ui.pygame_career_hub import PygameCareerHubScreen
from horse_racing_game.ui.pygame_menu import PygameMainMenu
from horse_racing_game.ui.pygame_online_lobby import PygameOnlineLobbyScreen
from horse_racing_game.ui.pygame_profile import PygameProfileScreen
from horse_racing_game.ui.pygame_replay import PygameReplayScreen
from horse_racing_game.ui.pygame_special_events import PygameSpecialEventScreen
from horse_racing_game.ui.pygame_stats import PygameStatsScreen
from horse_racing_game.ui.pygame_track_editor import PygameTrackEditorScreen


def main(argv: list[str] | None = None) -> int | None:
    project_root = Path(__file__).parents[2]
    args = _parse_args(argv)
    if args.smoke_content:
        return _smoke_content(project_root)
    if args.smoke_race:
        return _smoke_race(project_root)
    if args.smoke_save is not None:
        return _smoke_save(project_root, args.smoke_save)
    if args.smoke_replay:
        return _smoke_replay(project_root)
    if args.smoke_replay_share:
        return _smoke_replay_share(project_root)
    if args.smoke_replay_library:
        return _smoke_replay_library(project_root)
    if args.smoke_time_trial:
        return _smoke_time_trial(project_root)
    if args.smoke_ghost:
        return _smoke_ghost(project_root)
    if args.smoke_special_event:
        return _smoke_special_event(project_root)
    if args.smoke_settings:
        return _smoke_settings(project_root)
    if args.smoke_profile:
        return _smoke_profile(project_root)
    if args.smoke_track_catalog:
        return _smoke_track_catalog(project_root)
    if args.smoke_social_graph:
        return _smoke_social_graph(project_root)
    if args.smoke_community:
        return _smoke_community(project_root)
    if args.smoke_chat_session:
        return _smoke_chat_session(project_root)
    if args.smoke_live_ops:
        return _smoke_live_ops(project_root)
    if args.smoke_diagnostics:
        return _smoke_diagnostics(project_root)
    if args.smoke_speech:
        return _smoke_speech(project_root)

    write_runtime_log(project_root, "pygame_main: start")
    _log_integrity_issues(project_root)
    try:
        base_config = default_config(project_root)
        progress = load_progress(project_root)
        write_runtime_log(project_root, f"pygame_main: content_root={base_config.content_root}")
        write_runtime_log(project_root, f"pygame_main: progress={progress}")
        _log_cue_coverage(project_root, base_config.content_root)
        while True:
            selection = PygameMainMenu(
                base_config.content_root,
                project_root,
                initial_horse_id=progress.last_horse_id,
                initial_track_id=progress.last_track_id,
                initial_weather_id=progress.last_weather_id,
                initial_audio_mix_id=progress.last_audio_mix_id,
                initial_stable_id=progress.last_stable_id,
                initial_difficulty_id=progress.last_difficulty_id,
            ).run()
            write_runtime_log(project_root, f"pygame_main: menu returned {selection}")
            if selection is None:
                write_runtime_log(project_root, "pygame_main: closed from menu")
                return 0
            if selection.mode == "stats":
                PygameStatsScreen(base_config.content_root, project_root, progress).run()
                progress = load_progress(project_root)
                continue
            if selection.mode == "replay":
                PygameReplayScreen(base_config.content_root, project_root, progress).run()
                progress = load_progress(project_root)
                continue
            if selection.mode == "track_editor":
                PygameTrackEditorScreen(base_config.content_root, project_root, progress).run()
                progress = load_progress(project_root)
                continue
            if selection.mode == "profile":
                PygameProfileScreen(base_config.content_root, project_root).run()
                progress = load_progress(project_root)
                continue
            if selection.mode == "special_event":
                _run_special_event_mode(base_config, project_root, selection)
                progress = load_progress(project_root)
                continue
            if selection.mode in {"career", "career_training", "career_rest"}:
                career_choice = PygameCareerHubScreen(base_config.content_root, project_root, progress, selection).run()
                progress = load_progress(project_root)
                if career_choice is None:
                    continue
                selection = career_choice
            if selection.mode == "career_rest":
                progress = record_career_rest(project_root, progress, selection.stable_id)
                write_runtime_log(project_root, f"pygame_main: career rest progress={progress}")
                continue
            if selection.mode == "multiplayer":
                config = _config_for_selection(base_config, selection)
                lobby_result = PygameOnlineLobbyScreen(base_config.content_root, project_root).run()
                if lobby_result.mode == "menu":
                    continue
                if lobby_result.mode == "quit":
                    return 0
                result = PygameMultiplayerRaceGame(
                    config,
                    build_pygame_services(config),
                    project_root,
                    selection=selection,
                    remote_session=lobby_result.session,
                ).run()
                progress = record_race_result(
                    project_root,
                    progress,
                    selection.player_horse_id,
                    selection.track_id,
                    is_tutorial=False,
                    finished=result.state.is_finished,
                    is_career=False,
                    is_training=False,
                    rank=result.state.player().rank,
                    weather_id=selection.weather_id,
                    audio_mix_id=selection.audio_mix_id,
                    stable_id=selection.stable_id,
                    difficulty_id=selection.difficulty_id,
                    replay_lines=build_replay_lines(result.state, result.events),
                    replay=replay_to_dict(build_replay(config, result.commands)),
                )
                if result.next_action == "restart":
                    continue
                if result.next_action == "menu":
                    continue
                return 0

            while True:
                is_tutorial = selection.mode == "tutorial"
                is_career = selection.mode == "career"
                is_career_training = selection.mode == "career_training"
                is_time_trial = selection.mode == "time_trial"
                is_ghost_race = selection.mode == "ghost_race"
                is_training = selection.mode == "training" or is_career_training
                is_obstacle_lab = selection.mode == "obstacle_lab"
                effective_selection = selection
                rival_stable_ids: dict[str, str] = {}
                facility_training_bonus = 0
                ghost_elapsed_s: float | None = None
                if "training_ring_1" in progress.stable_upgrade_ids:
                    facility_training_bonus += 1
                if "assistant_trainer" in progress.stable_staff_ids:
                    facility_training_bonus += 1
                current_training_level = progress.horse_training_levels.get(selection.player_horse_id, 0) + facility_training_bonus
                opponent_strength = difficulty_by_id(selection.difficulty_id).opponent_strength
                career_length = CAREER_LENGTH
                career_reward_tier_id: str | None = None
                intro_message = None
                if is_career:
                    calendar = load_championship_calendar(base_config.content_root / "championship.json")
                    career_length = len(calendar)
                    championship_race = next_championship_race(calendar, progress.career_races_completed)
                    intro_message = championship_title(calendar, progress.career_races_completed, progress.career_points)
                    if championship_race is not None:
                        tier = career_difficulty(progress.career_races_completed, len(calendar))
                        career_reward_tier_id = tier.tier_id
                        opponent_strength = tier.opponent_strength * career_energy_modifier(progress.career_energy)
                        intro_message = f"{intro_message} Difficulty: {tier.name}. Energy: {progress.career_energy}."
                        rival_stable_ids = championship_race.rival_stables
                        effective_selection = MenuSelection(
                            player_horse_id=selection.player_horse_id,
                            track_id=championship_race.track_id,
                            weather_id=championship_race.weather_id,
                            audio_mix_id=selection.audio_mix_id,
                            stable_id=selection.stable_id,
                            difficulty_id=selection.difficulty_id,
                            mode=selection.mode,
                        )
                    else:
                        intro_message = career_title(progress.career_points, progress.career_races_completed, career_length)
                elif is_training:
                    intro_message = training_intro(selection.player_horse_id.replace("_", " "), current_training_level)
                    if is_career_training:
                        intro_message = f"Career training. Energy: {progress.career_energy}. {intro_message}"
                elif is_time_trial:
                    key = f"{selection.player_horse_id}|{selection.track_id}|{selection.weather_id}"
                    best_time = progress.best_time_trial_times.get(key)
                    if best_time is None:
                        intro_message = "Time trial. Finish cleanly to set a personal best for this horse, track, and weather."
                    else:
                        intro_message = f"Time trial. Personal best is {best_time:.1f} seconds. Race the clock."
                elif is_ghost_race:
                    replay = replay_from_dict(progress.last_replay or {})
                    if replay is not None:
                        ghost = reconstruct_race(replay, base_config.content_root)
                        ghost_elapsed_s = ghost.state.elapsed_s
                        intro_message = f"Ghost race. Last replay ghost finished in {ghost_elapsed_s:.1f} seconds."
                    else:
                        intro_message = "Ghost race. No replay ghost is saved yet; finish this run to save one."
                elif is_obstacle_lab:
                    effective_selection = MenuSelection(
                        player_horse_id=selection.player_horse_id,
                        track_id="audio_obstacle_lab",
                        weather_id="clear",
                        audio_mix_id=selection.audio_mix_id,
                        stable_id=selection.stable_id,
                        difficulty_id=selection.difficulty_id,
                        mode=selection.mode,
                    )
                    intro_message = "Obstacle lab. Three hazards are close together: dodge, jump, then duck."
                config = _config_for_selection(
                    base_config, effective_selection, current_training_level, rival_stable_ids, opponent_strength
                )
                result = PygameRaceGame(
                    config,
                    build_pygame_services(config),
                    project_root,
                    tutorial_mode=is_tutorial,
                    training_mode=is_training,
                    intro_message=intro_message,
                ).run()
                player = result.state.player()
                progress = record_race_result(
                    project_root,
                    progress,
                    effective_selection.player_horse_id,
                    effective_selection.track_id,
                    is_tutorial=is_tutorial,
                    finished=result.state.is_finished,
                    is_career=is_career or is_career_training,
                    is_training=is_training,
                    rank=player.rank,
                    weather_id=effective_selection.weather_id,
                    audio_mix_id=effective_selection.audio_mix_id,
                    stable_id=effective_selection.stable_id,
                    difficulty_id=effective_selection.difficulty_id,
                    career_difficulty_id=career_reward_tier_id,
                    replay_lines=build_replay_lines(result.state, result.events),
                    replay=replay_to_dict(build_replay(config, result.commands)),
                    career_length=career_length,
                    count_quick_race=not (is_time_trial or is_ghost_race),
                )
                if is_time_trial:
                    progress = record_time_trial_result(
                        project_root,
                        progress,
                        horse_id=effective_selection.player_horse_id,
                        track_id=effective_selection.track_id,
                        weather_id=effective_selection.weather_id,
                        elapsed_s=result.state.elapsed_s,
                        finished=result.state.is_finished,
                    )
                    summary = progress.last_time_trial_summary or {}
                    best_text = "new personal best" if summary.get("personal_best") else "no new best"
                    line = f"Time trial complete: {result.state.elapsed_s:.1f} seconds, {best_text}."
                    write_runtime_log(project_root, f"pygame_main: {line}")
                if is_ghost_race:
                    progress = record_ghost_race_result(
                        project_root,
                        progress,
                        horse_id=effective_selection.player_horse_id,
                        track_id=effective_selection.track_id,
                        weather_id=effective_selection.weather_id,
                        elapsed_s=result.state.elapsed_s,
                        finished=result.state.is_finished,
                        ghost_elapsed_s=ghost_elapsed_s,
                    )
                    summary = progress.last_ghost_race_summary or {}
                    if summary.get("ghost_elapsed_s") is None:
                        line = f"Ghost race complete: {result.state.elapsed_s:.1f} seconds. Replay saved for next ghost."
                    elif summary.get("beat_ghost"):
                        line = f"Ghost beaten by {abs(float(summary.get('delta_s', 0.0))):.1f} seconds."
                    else:
                        line = f"Ghost ahead by {abs(float(summary.get('delta_s', 0.0))):.1f} seconds."
                    write_runtime_log(project_root, f"pygame_main: {line}")
                for event in result.events:
                    if event.event_type in {"opponent_approaching", "opponent_passing"} and event.subject_id:
                        progress = record_rival_encounter(project_root, progress, event.subject_id)
                if is_career and result.state.is_finished:
                    for runner in result.state.runners:
                        if not runner.is_player:
                            progress = record_rival_championship_result(
                                project_root,
                                progress,
                                runner.runner_id,
                                points_for_rank(runner.rank),
                            )
                if is_career and progress.last_career_result_summary is not None:
                    write_runtime_log(
                        project_root,
                        f"pygame_main: career result {career_result_summary_text(progress.last_career_result_summary)}",
                    )
                    PygameCareerResultScreen(base_config.content_root, project_root, progress).run()
                write_runtime_log(
                    project_root,
                    (
                        "pygame_main: closed "
                        f"finished={result.state.is_finished} rank={player.rank} "
                        f"distance={player.distance_m:.1f} next={result.next_action} progress={progress}"
                    ),
                )
                if result.next_action == "restart":
                    continue
                if result.next_action == "menu":
                    break
                return 0
    except Exception:
        write_runtime_log(project_root, "pygame_main: exception\n" + traceback.format_exc())
        raise


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Horse Racing Audio First")
    parser.add_argument("--smoke-content", action="store_true", help="Validate content and service wiring without opening the UI.")
    parser.add_argument("--smoke-race", action="store_true", help="Run a deterministic headless race.")
    parser.add_argument("--smoke-save", nargs="?", const="", default=None, help="Write/read a save in a temporary or provided root.")
    parser.add_argument("--smoke-replay", action="store_true", help="Build and reconstruct a deterministic replay.")
    parser.add_argument("--smoke-replay-share", action="store_true", help="Export deterministic replay share files in a temporary save.")
    parser.add_argument("--smoke-replay-library", action="store_true", help="Export and rediscover deterministic replay share metadata in a temporary save.")
    parser.add_argument("--smoke-time-trial", action="store_true", help="Run a deterministic headless time-trial save loop.")
    parser.add_argument("--smoke-ghost", action="store_true", help="Run a deterministic headless ghost-race save loop.")
    parser.add_argument("--smoke-special-event", action="store_true", help="Run each special-event scenario challenge headlessly and score its objectives.")
    parser.add_argument("--smoke-settings", action="store_true", help="Write/read persistent user settings in a temporary save.")
    parser.add_argument("--smoke-profile", action="store_true", help="Write/read persistent profile identity and economy in a temporary save.")
    parser.add_argument("--smoke-track-catalog", action="store_true", help="Write/read persistent track sharing catalog metadata in a temporary save.")
    parser.add_argument("--smoke-social-graph", action="store_true", help="Write/read persistent social graph metadata in a temporary save.")
    parser.add_argument("--smoke-community", action="store_true", help="Write/read persistent community and moderation metadata in a temporary save.")
    parser.add_argument("--smoke-chat-session", action="store_true", help="Write/read persistent chat session metadata in a temporary save.")
    parser.add_argument("--smoke-live-ops", action="store_true", help="Write/read consent-gated live ops telemetry metadata in a temporary save.")
    parser.add_argument("--smoke-diagnostics", action="store_true", help="Build a headless runtime diagnostics summary in a temporary save.")
    parser.add_argument("--smoke-speech", action="store_true", help="Validate speech fallback construction.")
    return parser.parse_args(sys.argv[1:] if argv is None else argv)


def _log_integrity_issues(project_root: Path) -> None:
    issues = verify_integrity_manifest(project_root)
    if not issues:
        return
    summary = "; ".join(f"{issue.path}:{issue.status}" for issue in issues[:10])
    write_runtime_log(project_root, f"install integrity issues: {summary}")


def _log_cue_coverage(project_root: Path, content_root: Path) -> str:
    """Log which preferred cue sounds the shipped catalog covers so missing
    audio (which silently falls back at runtime) is visible at startup."""
    from horse_racing_game.audio.asset_coverage import coverage_report
    from horse_racing_game.content.loaders import load_sound_catalog

    report = coverage_report(load_sound_catalog(content_root / "sound_manifest.json"))
    write_runtime_log(project_root, f"cue coverage: {report}")
    return report


def _smoke_content(project_root: Path) -> int:
    config = default_config(project_root)
    services = build_quick_race_services(config)
    if not services.horses or not services.track.track_id or len(services.sound_catalog) == 0:
        return 1
    from horse_racing_game.audio.asset_coverage import coverage_report

    print(f"content ok: track={services.track.track_id} horses={len(services.horses)} sounds={len(services.sound_catalog)}")
    print(coverage_report(services.sound_catalog))
    return 0


def _smoke_race(project_root: Path) -> int:
    config = AppConfig(content_root=project_root / "content", tick_hz=4)
    from horse_racing_game.app.game_app import GameApp

    result = GameApp(config, build_quick_race_services(config)).run_quick_race()
    print(f"race ok: finished={result.state.is_finished} ticks={result.ticks}")
    return 0 if result.state.is_finished and result.ticks > 0 else 1


def _smoke_save(project_root: Path, save_root: str) -> int:
    root = Path(save_root) if save_root else None
    if root is None:
        with tempfile.TemporaryDirectory() as directory:
            return _smoke_save_at(Path(directory))
    return _smoke_save_at(root)


def _smoke_save_at(root: Path) -> int:
    updated = record_race_result(
        root,
        GameProgress(),
        "ember_stride",
        "ashford_oval",
        is_tutorial=False,
        finished=True,
        rank=1,
    )
    loaded = load_progress(root)
    ok = updated.quick_races_completed == 1 and loaded.quick_races_completed == 1
    print(f"save ok: {ok}")
    return 0 if ok else 1


def _smoke_replay(project_root: Path) -> int:
    config = AppConfig(content_root=project_root / "content", tick_hz=4)
    from horse_racing_game.app.game_app import GameApp

    result = GameApp(config, build_quick_race_services(config)).run_quick_race()
    replay = build_replay(config, result.commands)
    reconstructed = reconstruct_race(replay, project_root / "content")
    ok = reconstructed.state.is_finished and reconstructed.ticks > 0
    print(f"replay ok: {ok} ticks={reconstructed.ticks}")
    return 0 if ok else 1


def _smoke_replay_share(project_root: Path) -> int:
    with tempfile.TemporaryDirectory() as directory:
        save_root = Path(directory)
        config = AppConfig(content_root=project_root / "content", tick_hz=4)
        from horse_racing_game.app.game_app import GameApp

        result = GameApp(config, build_quick_race_services(config)).run_quick_race()
        progress = record_race_result(
            save_root,
            GameProgress(),
            config.player_horse_id,
            config.track_id,
            is_tutorial=False,
            finished=result.state.is_finished,
            rank=result.state.player().rank,
            replay_lines=build_replay_lines(result.state, result.events),
            replay=replay_to_dict(build_replay(config, result.commands)),
        )
        bundle = build_last_replay_share_bundle(project_root / "content", progress)
        saved = save_replay_share_bundle(save_root, bundle) if bundle is not None else None
        ok = saved is not None and all(path.exists() for path in saved.files)
        print(f"replay share ok: {ok} files={0 if saved is None else len(saved.files)}")
        return 0 if ok else 1


def _smoke_replay_library(project_root: Path) -> int:
    with tempfile.TemporaryDirectory() as directory:
        save_root = Path(directory)
        config = AppConfig(content_root=project_root / "content", tick_hz=4)
        from horse_racing_game.app.game_app import GameApp

        result = GameApp(config, build_quick_race_services(config)).run_quick_race()
        progress = record_race_result(
            save_root,
            GameProgress(),
            config.player_horse_id,
            config.track_id,
            is_tutorial=False,
            finished=result.state.is_finished,
            rank=result.state.player().rank,
            replay_lines=build_replay_lines(result.state, result.events),
            replay=replay_to_dict(build_replay(config, result.commands)),
        )
        bundle = build_last_replay_share_bundle(project_root / "content", progress)
        if bundle is not None:
            save_replay_share_bundle(save_root, bundle)
        index = load_replay_share_index(save_root)
        ok = len(index) == 1 and index[0].replay_id == "last-replay" and len(index[0].files) == 7
        print(f"replay library ok: {ok} entries={len(index)}")
        return 0 if ok else 1


def _smoke_time_trial(project_root: Path) -> int:
    with tempfile.TemporaryDirectory() as directory:
        save_root = Path(directory)
        config = AppConfig(content_root=project_root / "content", tick_hz=4)
        from horse_racing_game.app.game_app import GameApp

        result = GameApp(config, build_quick_race_services(config)).run_quick_race()
        progress = record_race_result(
            save_root,
            GameProgress(),
            config.player_horse_id,
            config.track_id,
            is_tutorial=False,
            finished=result.state.is_finished,
            rank=result.state.player().rank,
            replay_lines=build_replay_lines(result.state, result.events),
            replay=replay_to_dict(build_replay(config, result.commands)),
            count_quick_race=False,
        )
        progress = record_time_trial_result(
            save_root,
            progress,
            horse_id=config.player_horse_id,
            track_id=config.track_id,
            weather_id=config.weather_id,
            elapsed_s=result.state.elapsed_s,
            finished=result.state.is_finished,
        )
        ok = result.state.is_finished and bool(progress.last_time_trial_summary)
        print(f"time trial ok: {ok} elapsed={result.state.elapsed_s:.1f}")
        return 0 if ok else 1


def _smoke_ghost(project_root: Path) -> int:
    with tempfile.TemporaryDirectory() as directory:
        save_root = Path(directory)
        config = AppConfig(content_root=project_root / "content", tick_hz=4)
        from horse_racing_game.app.game_app import GameApp

        app = GameApp(config, build_quick_race_services(config))
        ghost_result = app.run_quick_race()
        ghost_replay = build_replay(config, ghost_result.commands)
        ghost_time = reconstruct_race(ghost_replay, project_root / "content").state.elapsed_s
        result = GameApp(config, build_quick_race_services(config)).run_quick_race()
        progress = record_race_result(
            save_root,
            GameProgress(last_replay=replay_to_dict(ghost_replay)),
            config.player_horse_id,
            config.track_id,
            is_tutorial=False,
            finished=result.state.is_finished,
            rank=result.state.player().rank,
            replay_lines=build_replay_lines(result.state, result.events),
            replay=replay_to_dict(build_replay(config, result.commands)),
            count_quick_race=False,
        )
        progress = record_ghost_race_result(
            save_root,
            progress,
            horse_id=config.player_horse_id,
            track_id=config.track_id,
            weather_id=config.weather_id,
            elapsed_s=result.state.elapsed_s,
            finished=result.state.is_finished,
            ghost_elapsed_s=ghost_time,
        )
        ok = result.state.is_finished and bool(progress.last_ghost_race_summary)
        print(f"ghost ok: {ok} elapsed={result.state.elapsed_s:.1f} ghost={ghost_time:.1f}")
        return 0 if ok else 1


def _smoke_special_event(project_root: Path) -> int:
    from horse_racing_game.app.special_events import (
        default_special_events,
        load_special_event_records,
        record_special_event_result,
        run_special_event,
        special_event_summary,
    )

    ok = True
    with tempfile.TemporaryDirectory() as directory:
        save_root = Path(directory)
        for challenge in default_special_events():
            result = run_special_event(project_root, challenge)
            record = record_special_event_result(save_root, result)
            if not result.is_finished:
                ok = False
            met = len(result.progress.completed_objective_ids)
            total = len(challenge.objectives)
            print(
                f"special event {challenge.event_id}: finished={result.is_finished} "
                f"rank={result.rank} elapsed={result.elapsed_s:.1f} objectives={met}/{total} "
                f"best={record.best_objectives_met}/{record.total_objectives} completed={record.completed}"
            )
            print("  " + special_event_summary(challenge, result.progress))
        persisted = load_special_event_records(save_root)
        ok = ok and len(persisted) == len(default_special_events())
    return 0 if ok else 1


def _smoke_settings(project_root: Path) -> int:
    with tempfile.TemporaryDirectory() as directory:
        save_root = Path(directory)
        updated = record_user_settings(
            save_root,
            GameProgress(),
            audio_mix_id="descriptive",
            speech_verbosity="detailed",
            language_id="fr-FR",
            controller_profile_id="controller-accessible",
            mobile_gesture_profile_id="android-large-gestures",
            haptics_enabled=True,
            controller_only_navigation=True,
        )
        loaded = load_progress(save_root)
        ok = (
            updated.last_audio_mix_id == "descriptive"
            and loaded.speech_verbosity == "detailed"
            and loaded.language_id == "fr-FR"
            and loaded.controller_profile_id == "controller-accessible"
            and loaded.mobile_gesture_profile_id == "android-large-gestures"
            and loaded.haptics_enabled
            and loaded.controller_only_navigation
        )
        print(f"settings ok: {ok}")
        return 0 if ok else 1


def _smoke_profile(project_root: Path) -> int:
    with tempfile.TemporaryDirectory() as directory:
        save_root = Path(directory)
        profile = claim_profile_starter_reward(save_root, load_player_profile(save_root))
        profile = equip_profile_title(save_root, profile, "storm_rider")
        profile = equip_profile_badge(save_root, profile, "founder")
        profile = equip_profile_cosmetic(save_root, profile, "red_silks")
        loaded = load_player_profile(save_root)
        ok = (
            loaded.identity.title_id == "storm_rider"
            and loaded.identity.badge_ids == ("founder",)
            and loaded.identity.cosmetic_ids == ("red_silks",)
            and loaded.economy.wallet.soft_currency == 120
            and loaded.economy.xp == 140
        )
        print(f"profile ok: {ok}")
        return 0 if ok else 1


def _smoke_track_catalog(project_root: Path) -> int:
    with tempfile.TemporaryDirectory() as directory:
        save_root = Path(directory)
        catalog = TrackCatalog()
        catalog.publish(TrackShare("custom_turf_loop", "local_player", "public", version=2))
        catalog.rate(TrackRating("custom_turf_loop", "local_player", 5, ("technical",)))
        catalog.add_weather_preset(WeatherPreset("storm_day", "rain", "Storm Day"))
        catalog.add_ruleset(
            EventRuleset(
                "wet_sprint",
                allowed_surface_variants=("mud", "soft_turf"),
                weather_preset_ids=("storm_day",),
                obstacle_density="light",
            )
        )
        save_track_catalog(save_root, catalog)
        loaded = load_track_catalog(save_root)
        ok = (
            loaded.shares() == catalog.shares()
            and loaded.ratings() == catalog.ratings()
            and loaded.weather_presets() == catalog.weather_presets()
            and loaded.rulesets() == catalog.rulesets()
        )
        print(f"track catalog ok: {ok}")
        return 0 if ok else 1


def _smoke_social_graph(project_root: Path) -> int:
    with tempfile.TemporaryDirectory() as directory:
        save_root = Path(directory)
        graph = SocialGraph()
        graph.upsert_profile(SocialPlayerProfile("alice", "Alice"))
        graph.upsert_profile(SocialPlayerProfile("bob", "Bob"))
        graph.upsert_profile(SocialPlayerProfile("carol", "Carol"))
        graph.send_friend_request("alice", "bob")
        graph.accept_friend_request("alice", "bob")
        graph.send_friend_request("carol", "alice")
        graph.block("alice", "carol")
        graph.mute("bob", "alice")
        graph.set_presence(Presence("bob", "online", "Ready"))
        graph.record_recent_player("alice", "bob")
        save_social_graph(save_root, graph)
        loaded = load_social_graph(save_root)
        ok = loaded.snapshot() == graph.snapshot() and loaded.recent_players("alice") == ("bob",)
        print(f"social graph ok: {ok}")
        return 0 if ok else 1


def _smoke_community(project_root: Path) -> int:
    with tempfile.TemporaryDirectory() as directory:
        save_root = Path(directory)
        hub = CommunityHub(
            profanity=ProfanityControl(("badword",)),
            rate_limit=RateLimitRule(max_messages=3, window_s=5.0),
        )
        hub.create_club("club-1", "Rail Riders", "RAIL", "alice")
        hub.add_member("club-1", "bob")
        hub.add_member("club-1", "carol", "moderator")
        hub.schedule_event("event-1", "club-1", "Sunday Cup", 100.0, "alice")
        message = hub.post_team_message("club-1", "bob", "No BADWORD lines", timestamp_s=1.0)
        report = hub.report_message("report-1", message, "alice", "review")
        hub.resolve_report(report.report_id, "reviewed")
        hub.apply_moderation_action(
            ModerationAction("action-1", "club-1", "carol", "bob", "mute", "cooldown", duration_s=10.0),
            timestamp_s=20.0,
        )
        save_community_hub(save_root, hub)
        loaded = load_community_hub(save_root)
        ok = (
            loaded.snapshot() == hub.snapshot()
            and loaded.chat_snapshot() == hub.chat_snapshot()
            and loaded.reports_snapshot() == hub.reports_snapshot()
        )
        print(f"community ok: {ok}")
        return 0 if ok else 1


def _smoke_chat_session(project_root: Path) -> int:
    with tempfile.TemporaryDirectory() as directory:
        save_root = Path(directory)
        chat = ChatSession(("host", "guest", "spectator"), moderation=ChatModerationPolicy(("badword",)))
        chat.append_text("Public BADWORD line")
        chat.submit_text(timestamp_s=1.0)
        chat.cycle_sender(1)
        chat.cycle_voice_macro(3)
        chat.submit_voice(timestamp_s=2.0, recipient_id="host")
        chat.mute("spectator", "guest")
        chat.block("host", "guest")
        save_chat_session(save_root, chat)
        loaded = load_chat_session(save_root)
        ok = (
            loaded.messages == chat.messages
            and loaded.muted_snapshot() == chat.muted_snapshot()
            and loaded.blocked_snapshot() == chat.blocked_snapshot()
            and loaded.moderation == chat.moderation
        )
        print(f"chat session ok: {ok}")
        return 0 if ok else 1


def _smoke_live_ops(project_root: Path) -> int:
    with tempfile.TemporaryDirectory() as directory:
        save_root = Path(directory)
        store = TelemetryStore(telemetry_consent_enabled=True)
        store.set_remote_config(RemoteConfig("remote-1", "stable", {"reward_multiplier": 1.2}))
        store.record_analytics(AnalyticsEvent("race_finish", "local_player", 8.0, {"rank": 1}))
        store.record_crash(crash_report_from_exception("crash-1", 9.0, RuntimeError("audio"), "stack", {"screen": "race"}))
        save_telemetry_store(save_root, store)
        loaded = load_telemetry_store(save_root)
        payload = loaded.privacy_safe_analytics_payload()
        ok = (
            loaded.telemetry_consent_enabled
            and loaded.remote_config == store.remote_config
            and loaded.analytics_events == store.analytics_events
            and loaded.crash_reports == store.crash_reports
            and bool(payload)
            and "player_hash" in payload[0]
            and "player_id" not in payload[0]
        )
        print(f"live ops ok: {ok}")
        return 0 if ok else 1


def _smoke_diagnostics(project_root: Path) -> int:
    with tempfile.TemporaryDirectory() as directory:
        save_root = Path(directory)
        write_runtime_log(save_root, "diagnostics smoke")
        record_race_result(save_root, GameProgress(), "ember_stride", "ashford_oval", is_tutorial=False, finished=True, rank=1)
        store = TelemetryStore(telemetry_consent_enabled=True)
        store.set_remote_config(RemoteConfig("remote-1"))
        store.record_analytics(AnalyticsEvent("menu_action", "local_player", 1.0, {"item": "diagnostics"}))
        store.record_crash(crash_report_from_exception("crash-1", 2.0, RuntimeError("diagnostics"), "stack"))
        save_telemetry_store(save_root, store)
        report = build_diagnostic_report(save_root, tail_lines=1)
        ok = (
            report.crash_report_count == 1
            and report.analytics_event_count == 1
            and any(status.label == "progress" and status.exists for status in report.files)
            and any("diagnostics smoke" in line for line in report.runtime_log_tail)
        )
        print(f"diagnostics ok: {ok}")
        return 0 if ok else 1


def _smoke_speech(project_root: Path) -> int:
    speaker = create_speaker(project_root, platform="freebsd")
    speaker.speak("Smoke speech fallback.", priority=50)
    ok = isinstance(speaker, NullSpeaker)
    print(f"speech ok: {ok}")
    return 0 if ok else 1


def _run_special_event_mode(base_config: AppConfig, project_root: Path, selection: MenuSelection) -> None:
    """Special-event flow: pick a challenge, race it on the core loop, score and
    persist the objectives, then return to the challenge list showing the result.
    """
    from horse_racing_game.app.special_events import (
        record_special_event_result,
        special_event_result_from_state,
        special_event_summary,
    )

    last_summary: str | None = None
    while True:
        challenge = PygameSpecialEventScreen(base_config.content_root, project_root, last_summary).run()
        if challenge is None:
            return
        effective = MenuSelection(
            player_horse_id=selection.player_horse_id,
            track_id=challenge.track_id,
            weather_id=challenge.weather_id,
            audio_mix_id=selection.audio_mix_id,
            stable_id=selection.stable_id,
            difficulty_id=selection.difficulty_id,
            mode="special_event",
        )
        config = _config_for_selection(base_config, effective)
        result = PygameRaceGame(
            config,
            build_pygame_services(config),
            project_root,
            intro_message=f"{challenge.name}. {challenge.briefing}",
        ).run()
        event_result = special_event_result_from_state(challenge, result.state)
        record_special_event_result(project_root, event_result)
        last_summary = special_event_summary(challenge, event_result.progress)
        write_runtime_log(project_root, f"pygame_main: special event {challenge.event_id} -> {last_summary}")


def _config_for_selection(
    base_config: AppConfig,
    selection: MenuSelection,
    training_level: int = 0,
    rival_stable_ids: dict[str, str] | None = None,
    opponent_strength: float = 1.0,
) -> AppConfig:
    return AppConfig(
        content_root=base_config.content_root,
        track_id=selection.track_id,
        player_horse_id=selection.player_horse_id,
        weather_id=selection.weather_id,
        audio_mix_id=selection.audio_mix_id,
        stable_id=selection.stable_id,
        rival_stable_ids=dict(rival_stable_ids or {}),
        horse_training_level=training_level,
        opponent_strength=opponent_strength,
        seed=base_config.seed,
        tick_hz=60,
        max_race_seconds=base_config.max_race_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
