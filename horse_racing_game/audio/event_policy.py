from horse_racing_game.simulation.race_events import RaceEvent


_EVENT_COOLDOWNS = {
    "opponent_approaching": 1.0,
    "opponent_passing": 1.0,
    "opponent_falling_behind": 1.4,
    "opponent_blocking_inside": 1.2,
    "status_requested": 0.75,
    "turn_incoming": 1.5,
    "turn_entry": 1.5,
    "turn_exit": 1.2,
    "turn_apex": 1.0,
    "turn_rail_inside": 0.9,
    "turn_rail_outside": 0.9,
    "turn_too_tight": 1.2,
    "turn_too_wide": 1.2,
    "low_stamina": 5.0,
    "critical_stamina": 5.0,
    "pace_cruising": 1.5,
    "pace_overpushing": 1.5,
    "pace_recovering": 1.5,
    "pace_wasting_stamina": 1.5,
    "obstacle_warning": 1.2,
    "obstacle_hit": 1.0,
    "obstacle_near_miss": 0.8,
}


class AudioEventPolicy:
    def __init__(self) -> None:
        self._last_routed_at: dict[tuple[str, str | None], float] = {}

    def should_route(self, event: RaceEvent) -> bool:
        cooldown_s = _EVENT_COOLDOWNS.get(event.event_type)
        if cooldown_s is None:
            return True

        key = (event.event_type, event.subject_id)
        last_routed_at = self._last_routed_at.get(key)
        if last_routed_at is not None and event.timestamp_s - last_routed_at < cooldown_s:
            return False

        self._last_routed_at[key] = event.timestamp_s
        return True
