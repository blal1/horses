from dataclasses import dataclass

from horse_racing_game.audio.sound_catalog import SoundCatalog


@dataclass(frozen=True)
class SoundCue:
    sound_id: str
    volume: float


@dataclass(frozen=True)
class _CueRule:
    preferred_sound_id: str
    fallback_category: str
    volume: float
    fallback_token: str | None = None


_CUE_RULES = {
    "race_started": _CueRule("race_start_gate_snap", "countdown", 0.78),
    "turn_incoming": _CueRule("turn_warning_left_rail", "wind", 0.62),
    "opponent_approaching": _CueRule("opponent_approach_left", "horse", 0.66),
    "opponent_passing": _CueRule("opponent_pass_whoosh", "horse", 0.66),
    "opponent_falling_behind": _CueRule("horse_recover_exhale", "horse", 0.44),
    "opponent_blocking_inside": _CueRule("collision_brush_shoulders", "horse", 0.62),
    "low_stamina": _CueRule("horse_breath_low_stamina", "horse", 0.58),
    "critical_stamina": _CueRule("horse_breath_low_stamina", "horse", 0.7),
    "final_stretch": _CueRule("final_stretch_crowd_rise", "crowd", 0.68),
    "finish_line_crossed": _CueRule("finish_line_bell_crowd", "ui", 0.75, "confirmation"),
    "race_finished": _CueRule("ui_confirm_warm_chime", "ui", 0.65, "confirmation"),
    "obstacle_radar": _CueRule("obstacle_warning_diamond", "ui", 0.45, "question"),
    "obstacle_warning": _CueRule("obstacle_warning_diamond", "ui", 0.72, "question"),
    "obstacle_hit": _CueRule("obstacle_hit_rail_marker", "ui", 0.76, "error"),
    "obstacle_avoided": _CueRule("obstacle_avoided_clean_pass", "ui", 0.52, "confirmation"),
}


def cue_sound_requirements() -> dict[str, str]:
    """Preferred cue sound id → its fallback category, deduplicated.

    These are the sounds the router *wants* for the best experience; any not in
    the catalog fall back to a category match. Used by asset-coverage tooling to
    decide what still needs generating."""
    requirements: dict[str, str] = {}
    for rule in _CUE_RULES.values():
        requirements.setdefault(rule.preferred_sound_id, rule.fallback_category)
    return requirements


class SoundCueMap:
    def __init__(self, catalog: SoundCatalog) -> None:
        self._catalog = catalog

    def cue_for(self, event_type: str) -> SoundCue | None:
        rule = _CUE_RULES.get(event_type)
        if rule is None:
            return None
        if self._catalog.get(rule.preferred_sound_id) is not None:
            return SoundCue(rule.preferred_sound_id, rule.volume)
        fallback_id = self._fallback_sound_id(rule)
        if fallback_id is None:
            return None
        return SoundCue(fallback_id, rule.volume)

    def _fallback_sound_id(self, rule: _CueRule) -> str | None:
        if rule.fallback_token is not None:
            return self._catalog.first_matching_id(rule.fallback_category, rule.fallback_token)
        return self._catalog.first_id_by_category(rule.fallback_category)


