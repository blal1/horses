import random
from dataclasses import dataclass

from horse_racing_game.domain.horse import Horse
from horse_racing_game.domain.track import Track, TrackSegment
from horse_racing_game.domain.weather import Weather
from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.simulation.race_events import RaceEvent
from horse_racing_game.simulation.race_state import RaceState, RunnerState
from horse_racing_game.simulation.traits import trait_effect


@dataclass
class _RunnerRuntime:
    horse: Horse
    distance_m: float
    lateral_position: float
    speed_mps: float
    stamina: float
    stability: float
    is_player: bool
    pace: float
    aggression: float


@dataclass(frozen=True)
class RaceTickResult:
    state: RaceState
    events: tuple[RaceEvent, ...]


class RaceEngine:
    def __init__(
        self,
        track: Track,
        horses: tuple[Horse, ...],
        player_horse_id: str,
        seed: int,
        weather: Weather | None = None,
        opponent_strength: float = 1.0,
    ) -> None:
        if not horses:
            raise ValueError("RaceEngine requires at least one horse.")
        if not any(horse.horse_id == player_horse_id for horse in horses):
            raise ValueError(f"Unknown player horse: {player_horse_id}")

        self._track = track
        self._weather = weather or Weather("clear", "Clear", 1.0, 1.0, 1.0, None)
        self._opponent_strength = opponent_strength
        self._elapsed_s = 0.0
        self._is_finished = False
        self._started = False
        self._final_stretch_announced = False
        self._low_stamina_announced: set[str] = set()
        self._critical_stamina_announced: set[str] = set()
        self._last_player_pace_state: str | None = None
        self._last_player_segment = track.segment_at(0.0)
        self._announced_turn_apex_segments: set[tuple[float, float]] = set()
        self._rng = random.Random(seed)
        self._runners = self._create_runners(horses, player_horse_id)

    def tick(self, command: RaceCommand, delta_s: float) -> RaceTickResult:
        if delta_s <= 0.0:
            raise ValueError("delta_s must be positive.")
        if self._is_finished:
            return RaceTickResult(state=self._snapshot(), events=())

        self._elapsed_s += delta_s
        events: list[RaceEvent] = []
        if not self._started:
            self._started = True
            events.append(self._event("race_started", 80, None, {}))

        player_before = self._player_runtime()
        previous_speed = player_before.speed_mps
        previous_stamina = player_before.stamina

        self._update_paces(command)
        for runner in self._runners:
            self._update_runner(runner, delta_s)

        events.extend(self._detect_pace_events(command, previous_speed, previous_stamina))
        events.extend(self._detect_player_events(command))
        events.extend(self._detect_stamina_events())
        events.extend(self._detect_finish_events())

        return RaceTickResult(state=self._snapshot(), events=tuple(events))

    def _create_runners(
        self,
        horses: tuple[Horse, ...],
        player_horse_id: str,
    ) -> list[_RunnerRuntime]:
        runners: list[_RunnerRuntime] = []
        lane_spacing = 1.15
        for index, horse in enumerate(horses):
            is_player = horse.horse_id == player_horse_id
            pace = 0.62 if is_player else self._rng.uniform(0.58, 0.78)
            aggression = 1.0 if is_player else self._rng.uniform(0.82, 1.0)
            runners.append(
                _RunnerRuntime(
                    horse=horse,
                    distance_m=0.0,
                    lateral_position=index * lane_spacing,
                    speed_mps=0.0,
                    stamina=horse.stats.stamina_capacity,
                    stability=1.0,
                    is_player=is_player,
                    pace=pace,
                    aggression=aggression,
                )
            )
        return runners

    def _update_paces(self, command: RaceCommand) -> None:
        rankings = self._rankings()
        player = self._player_runtime()
        for runner in self._runners:
            if runner.is_player:
                sprint = 0.12 if command.push_requested else 0.0
                natural_decay = 0.003 if command.throttle_delta <= 0 else 0.0
                runner.pace = self._clamp(
                    runner.pace + command.throttle_delta * 0.04 + sprint - natural_decay,
                    0.35,
                    1.0,
                )
                runner.lateral_position = self._clamp(
                    runner.lateral_position + command.lateral_delta * 0.08,
                    0.0,
                    max(self._track.lanes - 1, 0) * 1.15,
                )
            else:
                runner.pace = self._opponent_target_pace(runner, rankings[runner.horse.horse_id], player)

    def _opponent_target_pace(self, runner: "_RunnerRuntime", rank: int, player: "_RunnerRuntime") -> float:
        """Keep opponents competitive by shadowing the player's pace (pack
        racing) while still reacting to position, the final stretch and a
        per-horse aggression factor. A little noise keeps the field organic
        while remaining deterministic per seed.
        """
        gap_to_player = player.distance_m - runner.distance_m
        chase_boost = self._clamp(gap_to_player / 170.0, -0.06, 0.15)
        in_final_stretch = runner.distance_m >= self._track.final_stretch_start_m
        final_push = 0.08 if in_final_stretch else 0.0
        back_marker_boost = 0.03 if rank > 4 else 0.0
        # shadow the player so a sprinting leader is pursued instead of escaped
        tracking_multiplier = 0.93 + 0.07 * runner.aggression
        target = self._clamp(
            (player.pace * tracking_multiplier + chase_boost + final_push + back_marker_boost)
            * self._opponent_strength,
            0.5,
            1.0,
        )
        noise = self._rng.uniform(-0.012, 0.012)
        # ease toward the target so pace changes stay smooth, not jittery
        return self._clamp(runner.pace + (target - runner.pace) * 0.1 + noise, 0.5, 1.0)

    def _update_runner(self, runner: _RunnerRuntime, delta_s: float) -> None:
        segment = self._track.segment_at(runner.distance_m)
        surface_modifier = 1.03 if runner.horse.preferred_surface == self._track.surface else 0.97
        fatigue_ratio = runner.stamina / runner.horse.stats.stamina_capacity
        fatigue_modifier = 0.68 + fatigue_ratio * 0.32
        curve_modifier = 1.0 - segment.curve_intensity * 0.08
        slope_modifier = 1.0 - segment.slope * 2.0
        effect = trait_effect(
            runner.horse.traits,
            surface=self._track.surface,
            weather_id=self._weather.weather_id,
            curve_intensity=segment.curve_intensity,
            in_final_stretch=runner.distance_m >= self._track.final_stretch_start_m,
        )
        target_speed = (
            runner.horse.stats.max_speed_mps
            * runner.pace
            * surface_modifier
            * self._weather.speed_modifier
            * fatigue_modifier
            * curve_modifier
            * slope_modifier
            * effect.speed_multiplier
        )
        max_speed_change = runner.horse.stats.acceleration * effect.acceleration_multiplier * delta_s
        speed_delta = self._clamp(target_speed - runner.speed_mps, -max_speed_change, max_speed_change)
        runner.speed_mps = max(0.0, runner.speed_mps + speed_delta)
        runner.distance_m = min(self._track.length_m, runner.distance_m + runner.speed_mps * delta_s)

        stamina_cost = (
            max(0.0, runner.pace - 0.46)
            * (1.32 + segment.curve_intensity * 1.08)
            * self._weather.stamina_cost_multiplier
            * effect.stamina_cost_multiplier
            * delta_s
        )
        stamina_recovery = runner.horse.stats.stamina_recovery * 0.24 * delta_s if runner.pace < 0.55 else 0.0
        runner.stamina = self._clamp(
            runner.stamina - stamina_cost + stamina_recovery,
            0.0,
            runner.horse.stats.stamina_capacity,
        )
        nervousness_penalty = runner.horse.stats.nervousness * 0.015
        runner.stability = self._clamp(
            (0.72 + fatigue_ratio * 0.28 - nervousness_penalty) * self._weather.stability_modifier,
            0.0,
            1.0,
        )

    def _detect_player_events(self, command: RaceCommand) -> list[RaceEvent]:
        events: list[RaceEvent] = []
        player = self._player_runtime()
        current_segment = self._track.segment_at(player.distance_m)
        if current_segment != self._last_player_segment:
            if self._last_player_segment.curve_direction != "none":
                events.append(self._turn_exit_event(self._last_player_segment, player))
            if current_segment.curve_direction != "none":
                events.append(self._turn_entry_event(current_segment, player))
            self._last_player_segment = current_segment

        if not self._final_stretch_announced and player.distance_m >= self._track.final_stretch_start_m:
            self._final_stretch_announced = True
            events.append(
                self._event(
                    "final_stretch",
                    80,
                    player.horse.horse_id,
                    {"distance_remaining_m": round(self._track.length_m - player.distance_m, 1)},
                )
            )

        events.extend(self._turn_feedback_events(player, current_segment))
        if command.request_status:
            events.append(self._status_event(player))
        events.extend(self._opponent_proximity_events(player))
        return events

    def _turn_entry_event(self, segment: TrackSegment, player: _RunnerRuntime) -> RaceEvent:
        return self._event(
            "turn_entry",
            60,
            player.horse.horse_id,
            {
                "direction": segment.curve_direction,
                "intensity": segment.curve_intensity,
                "marker": segment.audio_marker,
                "phase": "entry",
            },
        )

    def _turn_exit_event(self, segment: TrackSegment, player: _RunnerRuntime) -> RaceEvent:
        return self._event(
            "turn_exit",
            55,
            player.horse.horse_id,
            {
                "direction": segment.curve_direction,
                "intensity": segment.curve_intensity,
                "marker": segment.audio_marker,
                "phase": "exit",
            },
        )

    def _turn_feedback_events(self, player: _RunnerRuntime, segment: TrackSegment) -> list[RaceEvent]:
        if segment.curve_direction == "none":
            return []
        events: list[RaceEvent] = []
        key = (segment.start_m, segment.end_m)
        midpoint = (segment.start_m + segment.end_m) * 0.5
        if key not in self._announced_turn_apex_segments and player.distance_m >= midpoint:
            self._announced_turn_apex_segments.add(key)
            events.append(
                self._event(
                    "turn_apex",
                    58,
                    player.horse.horse_id,
                    {
                        "direction": segment.curve_direction,
                        "curve_intensity": segment.curve_intensity,
                        "marker": segment.audio_marker,
                        "apex_m": round(midpoint, 1),
                    },
                )
            )
        turn_feedback = self._turn_line_feedback_event(player, segment)
        if turn_feedback is not None:
            events.append(turn_feedback)
        return events

    def _turn_line_feedback_event(self, player: _RunnerRuntime, segment: TrackSegment) -> RaceEvent | None:
        max_lateral = max(self._track.lanes - 1, 0) * 1.15
        if max_lateral <= 0.0:
            return None
        inner_distance = player.lateral_position if segment.curve_direction == "left" else max_lateral - player.lateral_position
        outer_distance = max_lateral - player.lateral_position if segment.curve_direction == "left" else player.lateral_position
        if inner_distance <= 0.18:
            return self._event(
                "turn_too_tight",
                70,
                player.horse.horse_id,
                {
                    "direction": segment.curve_direction,
                    "clearance_m": round(inner_distance, 2),
                    "rail": "inside",
                    "marker": segment.audio_marker,
                },
            )
        if outer_distance <= 0.18:
            return self._event(
                "turn_too_wide",
                70,
                player.horse.horse_id,
                {
                    "direction": segment.curve_direction,
                    "clearance_m": round(outer_distance, 2),
                    "rail": "outside",
                    "marker": segment.audio_marker,
                },
            )
        if inner_distance <= 0.55:
            return self._event(
                "turn_rail_inside",
                52,
                player.horse.horse_id,
                {
                    "direction": segment.curve_direction,
                    "clearance_m": round(inner_distance, 2),
                    "rail": "inside",
                    "marker": segment.audio_marker,
                },
            )
        if outer_distance <= 0.55:
            return self._event(
                "turn_rail_outside",
                52,
                player.horse.horse_id,
                {
                    "direction": segment.curve_direction,
                    "clearance_m": round(outer_distance, 2),
                    "rail": "outside",
                    "marker": segment.audio_marker,
                },
            )
        return None

    def _status_event(self, player: _RunnerRuntime) -> RaceEvent:
        rank = self._rankings()[player.horse.horse_id]
        return self._event(
            "status_requested",
            40,
            player.horse.horse_id,
            {
                "rank": rank,
                "distance_remaining_m": round(self._track.length_m - player.distance_m, 1),
                "stamina": round(player.stamina, 1),
                "weather": self._weather.name,
            },
        )

    def _opponent_proximity_events(self, player: _RunnerRuntime) -> list[RaceEvent]:
        events: list[RaceEvent] = []
        for runner in self._runners:
            if runner.is_player:
                continue
            forward_gap = runner.distance_m - player.distance_m
            lateral_gap = runner.lateral_position - player.lateral_position
            relative_speed = runner.speed_mps - player.speed_mps
            if abs(forward_gap) <= 12.0 and abs(lateral_gap) <= 1.4:
                event_type = "opponent_passing" if forward_gap > 0 else "opponent_approaching"
                events.append(self._opponent_event(event_type, 60, runner, forward_gap, lateral_gap, relative_speed))
            if -22.0 <= forward_gap < -12.0 and abs(lateral_gap) <= 1.6 and relative_speed < -0.8:
                events.append(self._opponent_event("opponent_falling_behind", 45, runner, forward_gap, lateral_gap, relative_speed))
            if 0.0 <= forward_gap <= 8.0 and -1.4 <= lateral_gap < -0.1 and player.lateral_position > 0.35:
                events.append(self._opponent_event("opponent_blocking_inside", 68, runner, forward_gap, lateral_gap, relative_speed))
        return events

    def _opponent_event(
        self,
        event_type: str,
        priority: int,
        runner: _RunnerRuntime,
        forward_gap: float,
        lateral_gap: float,
        relative_speed: float,
    ) -> RaceEvent:
        side = "right" if lateral_gap > 0.15 else "left" if lateral_gap < -0.15 else "center"
        return self._event(
            event_type,
            priority,
            runner.horse.horse_id,
            {
                "forward_m": round(forward_gap, 2),
                "right_m": round(lateral_gap, 2),
                "relative_speed_mps": round(relative_speed, 2),
                "horse_name": runner.horse.name,
                "signature_sound": runner.horse.signature_sound,
                "side": side,
            },
        )

    def _detect_stamina_events(self) -> list[RaceEvent]:
        events: list[RaceEvent] = []
        for runner in self._runners:
            stamina_ratio = runner.stamina / runner.horse.stats.stamina_capacity
            if stamina_ratio <= 0.18 and runner.horse.horse_id not in self._critical_stamina_announced:
                self._critical_stamina_announced.add(runner.horse.horse_id)
                events.append(self._event("critical_stamina", 80, runner.horse.horse_id, {}))
            elif stamina_ratio <= 0.35 and runner.horse.horse_id not in self._low_stamina_announced:
                self._low_stamina_announced.add(runner.horse.horse_id)
                events.append(self._event("low_stamina", 60, runner.horse.horse_id, {}))
        return events

    def _detect_pace_events(self, command: RaceCommand, previous_speed: float, previous_stamina: float) -> list[RaceEvent]:
        player = self._player_runtime()
        pace_state = self._player_pace_state(command, player, previous_speed, previous_stamina)
        if pace_state is None or pace_state == self._last_player_pace_state:
            return []
        self._last_player_pace_state = pace_state
        stamina_capacity = max(player.horse.stats.stamina_capacity, 1.0)
        return [
            self._event(
                pace_state,
                36,
                player.horse.horse_id,
                {
                    "pace": round(player.pace, 3),
                    "speed": round(player.speed_mps, 3),
                    "stamina": round(player.stamina, 3),
                    "stamina_ratio": round(player.stamina / stamina_capacity, 3),
                },
            )
        ]

    def _player_pace_state(
        self,
        command: RaceCommand,
        player: _RunnerRuntime,
        previous_speed: float,
        previous_stamina: float,
    ) -> str | None:
        stamina_capacity = max(player.horse.stats.stamina_capacity, 1.0)
        stamina_ratio = player.stamina / stamina_capacity
        speed_gain = player.speed_mps - previous_speed
        stamina_delta = player.stamina - previous_stamina
        pushing = command.push_requested or command.throttle_delta >= 0.6
        easing = command.throttle_delta <= -0.15
        cruising = abs(command.throttle_delta) <= 0.25 and not command.push_requested

        if pushing and stamina_ratio <= 0.45 and (speed_gain <= 0.25 or player.speed_mps <= player.horse.stats.max_speed_mps * 0.72):
            return "pace_wasting_stamina"
        if pushing and stamina_ratio <= 0.7:
            return "pace_overpushing"
        if easing or (player.pace < 0.55 and (stamina_delta >= -0.05 or stamina_ratio < 0.8)):
            return "pace_recovering"
        if cruising or (0.58 <= player.pace <= 0.78 and stamina_ratio >= 0.45):
            return "pace_cruising"
        if stamina_ratio < 0.35:
            return "pace_wasting_stamina" if pushing else "pace_recovering"
        return "pace_cruising"

    def _detect_finish_events(self) -> list[RaceEvent]:
        finished = [runner for runner in self._runners if runner.distance_m >= self._track.length_m]
        if not finished:
            return []

        self._is_finished = True
        rankings = self._rankings()
        return [
            self._event(
                "finish_line_crossed",
                80,
                runner.horse.horse_id,
                {"rank": rankings[runner.horse.horse_id], "horse_name": runner.horse.name},
            )
            for runner in finished
        ] + [self._event("race_finished", 80, None, {})]

    def _snapshot(self) -> RaceState:
        rankings = self._rankings()
        runners = tuple(
            RunnerState(
                runner_id=runner.horse.horse_id,
                horse_name=runner.horse.name,
                distance_m=round(runner.distance_m, 3),
                lateral_position=round(runner.lateral_position, 3),
                speed_mps=round(runner.speed_mps, 3),
                stamina=round(runner.stamina, 3),
                stability=round(runner.stability, 3),
                is_player=runner.is_player,
                rank=rankings[runner.horse.horse_id],
            )
            for runner in self._runners
        )
        return RaceState(elapsed_s=round(self._elapsed_s, 3), runners=runners, is_finished=self._is_finished)

    def _rankings(self) -> dict[str, int]:
        ordered = sorted(self._runners, key=lambda runner: runner.distance_m, reverse=True)
        return {runner.horse.horse_id: index + 1 for index, runner in enumerate(ordered)}

    def _player_runtime(self) -> _RunnerRuntime:
        for runner in self._runners:
            if runner.is_player:
                return runner
        raise ValueError("RaceEngine has no player runner.")

    def _event(
        self,
        event_type: str,
        priority: int,
        subject_id: str | None,
        data: dict[str, str | int | float | bool],
    ) -> RaceEvent:
        return RaceEvent(
            event_type=event_type,
            priority=priority,
            timestamp_s=round(self._elapsed_s, 3),
            subject_id=subject_id,
            data=data,
        )

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return min(max(value, minimum), maximum)

