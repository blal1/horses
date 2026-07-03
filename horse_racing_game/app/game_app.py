from collections.abc import Iterable
from dataclasses import dataclass

from horse_racing_game.app.config import AppConfig
from horse_racing_game.app.bootstrap import GameServices
from horse_racing_game.audio.fake_backend import AudioCall
from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.simulation.race_events import RaceEvent
from horse_racing_game.simulation.race_state import RaceState


@dataclass(frozen=True)
class QuickRaceResult:
    state: RaceState
    events: tuple[RaceEvent, ...]
    audio_calls: tuple[AudioCall, ...]
    ticks: int
    commands: tuple[RaceCommand, ...] = ()


class GameApp:
    def __init__(self, config: AppConfig, services: GameServices) -> None:
        self._config = config
        self._services = services

    def run_quick_race(self, commands: Iterable[RaceCommand] | None = None) -> QuickRaceResult:
        command_iterator = iter(commands) if commands is not None else None
        all_events: list[RaceEvent] = []
        used_commands: list[RaceCommand] = []
        state: RaceState | None = None
        max_ticks = int(self._config.max_race_seconds * self._config.tick_hz)

        for tick_index in range(max_ticks):
            command = self._next_command(command_iterator, state)
            used_commands.append(command)
            tick_result = self._services.race_engine.tick(command, self._config.tick_seconds)
            all_events.extend(tick_result.events)
            self._services.audio_engine.render_events(tick_result.events)
            state = tick_result.state
            if state.is_finished:
                return QuickRaceResult(
                    state=state,
                    events=tuple(all_events),
                    audio_calls=tuple(self._services.audio_backend.calls),
                    ticks=tick_index + 1,
                    commands=tuple(used_commands),
                )

        if state is None:
            fallback = RaceCommand(request_status=True)
            used_commands.append(fallback)
            tick_result = self._services.race_engine.tick(fallback, self._config.tick_seconds)
            all_events.extend(tick_result.events)
            self._services.audio_engine.render_events(tick_result.events)
            state = tick_result.state

        return QuickRaceResult(
            state=state,
            events=tuple(all_events),
            audio_calls=tuple(self._services.audio_backend.calls),
            ticks=max_ticks,
            commands=tuple(used_commands),
        )

    def _next_command(
        self,
        command_iterator: Iterable[RaceCommand] | None,
        state: RaceState | None,
    ) -> RaceCommand:
        if command_iterator is None:
            return self._default_command(state)
        command = next(command_iterator, None)
        if command is None:
            return self._default_command(state)
        return command

    def _default_command(self, state: RaceState | None) -> RaceCommand:
        if state is None:
            return RaceCommand(throttle_delta=1.0, request_status=True)

        player = state.player()
        distance_remaining = self._services.track.length_m - player.distance_m
        status_tick = int(state.elapsed_s) % 20 == 0
        return RaceCommand(
            throttle_delta=0.45 if player.stamina > 20.0 else -0.35,
            lateral_delta=0.0,
            push_requested=distance_remaining <= 350.0 and player.stamina > 12.0,
            request_status=status_tick,
        )