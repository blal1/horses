from horse_racing_game.audio.audio_backend import AudioBackend, RelativeAudioPosition
from horse_racing_game.audio.event_cues import SoundCue, SoundCueMap
from horse_racing_game.audio.sound_catalog import SoundCatalog
from horse_racing_game.simulation.race_events import RaceEvent


class AudioEventRouter:
    def __init__(self, catalog: SoundCatalog, backend: AudioBackend) -> None:
        self._backend = backend
        self._catalog = catalog
        self._cue_map = SoundCueMap(catalog)

    def route(self, event: RaceEvent) -> None:
        if event.event_type == "race_started":
            self._play_cue(event.event_type)
            self._backend.speak("Start.", event.priority)
        elif event.event_type in {"turn_incoming", "turn_entry"}:
            self._route_turn_entry(event)
        elif event.event_type == "turn_exit":
            self._route_turn_exit(event)
        elif event.event_type == "turn_apex":
            self._route_turn_apex(event)
        elif event.event_type in {"turn_rail_inside", "turn_rail_outside", "turn_too_tight", "turn_too_wide"}:
            self._route_turn_line_event(event)
        elif event.event_type in {"opponent_approaching", "opponent_passing", "opponent_falling_behind", "opponent_blocking_inside"}:
            self._route_positioned_event(event)
        elif event.event_type == "obstacle_radar":
            self._route_obstacle_radar(event)
        elif event.event_type in {"obstacle_warning", "obstacle_hit", "obstacle_avoided", "obstacle_near_miss"}:
            self._route_obstacle_event(event)
        elif event.event_type in {"low_stamina", "critical_stamina"}:
            self._route_stamina_event(event)
        elif event.event_type in {"pace_cruising", "pace_overpushing", "pace_recovering", "pace_wasting_stamina"}:
            self._route_pace_event(event)
        elif event.event_type == "status_requested":
            self._route_status_event(event)
        elif event.event_type == "final_stretch":
            self._play_cue(event.event_type)
            self._backend.speak("Final stretch.", event.priority)
        elif event.event_type == "finish_line_crossed":
            self._play_cue(event.event_type)
            rank = event.data.get("rank", "?")
            self._backend.speak(f"Finished rank {rank}.", event.priority)
        elif event.event_type == "race_finished":
            self._play_cue(event.event_type)

    def _route_positioned_event(self, event: RaceEvent) -> None:
        position = self._position(event)
        cue = self._opponent_cue(event)
        if cue is not None:
            self._backend.play_3d(cue.sound_id, position, cue.volume)
        self._play_opponent_signature(event)
        if event.event_type == "opponent_blocking_inside":
            name = event.data.get("horse_name", "Rival")
            self._backend.speak(f"{name} blocks inside.", event.priority)

    def _opponent_cue(self, event: RaceEvent) -> SoundCue | None:
        if event.event_type == "opponent_approaching":
            sound_id = "opponent_approach_right" if float(event.data.get("right_m", 0.0)) > 0 else "opponent_approach_left"
            return self._cue_for_sound(sound_id, 0.66) or self._cue_map.cue_for(event.event_type)
        return self._cue_map.cue_for(event.event_type)

    def _play_opponent_signature(self, event: RaceEvent) -> None:
        sound_id = event.data.get("signature_sound")
        if not isinstance(sound_id, str) or self._catalog.get(sound_id) is None:
            return
        volume_by_type = {
            "opponent_approaching": 0.34,
            "opponent_passing": 0.4,
            "opponent_falling_behind": 0.28,
            "opponent_blocking_inside": 0.36,
        }
        self._backend.play_3d(sound_id, self._position(event), volume_by_type.get(event.event_type, 0.32))

    def _route_obstacle_event(self, event: RaceEvent) -> None:
        cue = self._cue_map.cue_for(event.event_type)
        if event.event_type == "obstacle_avoided" and event.data.get("resolution") == "jump":
            cue = self._cue_for_sound("horse_jump_landing", 0.66) or cue
        elif event.event_type == "obstacle_avoided" and event.data.get("resolution") == "duck":
            cue = self._cue_for_sound("horse_lane_change_hoof_sweep", 0.5) or cue
        elif event.event_type == "obstacle_hit":
            cue = self._obstacle_hit_cue(event) or cue
        elif event.event_type == "obstacle_near_miss":
            cue = self._cue_for_sound("obstacle_warning_diamond", 0.7) or cue
        if cue is not None:
            self._backend.play_3d(cue.sound_id, self._position(event), cue.volume)
        if event.event_type == "obstacle_hit":
            self._backend.speak(f"Hit {event.data.get('label', 'obstacle')}.", event.priority)
        elif event.event_type == "obstacle_warning":
            action = self._action_text(event.data.get("required_action"))
            self._backend.speak(f"Obstacle {event.data.get('label', 'ahead')}. {action}.", event.priority)
        elif event.event_type == "obstacle_near_miss":
            self._backend.speak(f"Near miss {event.data.get('label', 'obstacle')}.", event.priority)
        elif event.event_type == "obstacle_avoided":
            action = self._action_text(event.data.get("resolution"))
            quality = event.data.get("timing_quality")
            prefix = f"{str(quality).title()} " if quality in {"perfect", "good", "late"} else ""
            self._backend.speak(f"{prefix}{action} confirmed.", event.priority)

    def _route_obstacle_radar(self, event: RaceEvent) -> None:
        sound_id = self._radar_sound_id(event)
        if sound_id is None:
            return
        volume = self._radar_volume(event)
        for index in range(self._radar_repeat_count(event)):
            self._backend.play_3d(sound_id, self._position(event), min(volume + index * 0.08, 0.9))

    def _radar_sound_id(self, event: RaceEvent) -> str | None:
        preferred_by_action = {
            "dodge": "obstacle_warning_diamond",
            "jump": "horse_jump_takeoff",
            "duck": "ui_cancel_low_tap",
        }
        preferred = preferred_by_action.get(str(event.data.get("required_action", "dodge")), "obstacle_warning_diamond")
        if self._catalog.get(preferred) is not None:
            return preferred
        cue = self._cue_map.cue_for(event.event_type)
        return cue.sound_id if cue is not None else None

    def _radar_volume(self, event: RaceEvent) -> float:
        forward_m = max(float(event.data.get("forward_m", 120.0)), 0.0)
        closeness = 1.0 - min(forward_m / 120.0, 1.0)
        return min(0.88, 0.34 + closeness * 0.46)

    def _radar_repeat_count(self, event: RaceEvent) -> int:
        stage = event.data.get("warning_stage")
        if stage == "imminent":
            return 3
        if stage == "urgent":
            return 2
        if float(event.data.get("forward_m", 999.0)) <= 15.0:
            return 2
        return 1

    def _obstacle_hit_cue(self, event: RaceEvent) -> SoundCue | None:
        kind = str(event.data.get("kind", ""))
        if kind in {"mud", "puddle"}:
            return self._cue_for_sound("horse_stumble_light_dirt", 0.58)
        if kind in {"low_branch", "low_banner", "low_gate", "low_rope"}:
            return self._cue_for_sound("horse_lane_change_hoof_sweep", 0.62) or self._cue_for_sound("horse_stumble_light_dirt", 0.62)
        if kind in {"rail", "barrel", "stone", "cone"}:
            return self._cue_for_sound("obstacle_hit_rail_marker", 0.78) or self._cue_for_sound("collision_brush_shoulders", 0.72)
        if event.data.get("required_action") == "jump":
            return self._cue_for_sound("horse_stumble_light_dirt", 0.68)
        return None

    def _action_text(self, action: object) -> str:
        if action == "jump":
            return "jump"
        if action == "duck":
            return "duck"
        return "dodge"

    def _cue_for_sound(self, sound_id: str, volume: float):
        if self._catalog.get(sound_id) is None:
            return None
        return SoundCue(sound_id, volume)

    def _route_stamina_event(self, event: RaceEvent) -> None:
        self._play_cue(event.event_type)
        text = "Critical stamina." if event.event_type == "critical_stamina" else "Low stamina."
        self._backend.speak(text, event.priority)

    def _route_turn_entry(self, event: RaceEvent) -> None:
        direction = str(event.data.get("direction", "ahead"))
        self._backend.speak(f"Turn entry {direction}.", event.priority)
        sound_id = "turn_warning_right_rail" if direction == "right" else "turn_warning_left_rail"
        if self._catalog.get(sound_id) is not None:
            self._backend.play_2d(sound_id, 0.62)
        else:
            self._play_cue("turn_entry")

    def _route_turn_exit(self, event: RaceEvent) -> None:
        direction = str(event.data.get("direction", "ahead"))
        self._backend.speak(f"Turn exit {direction}.", event.priority)
        if self._catalog.get("ui_confirm_warm_chime") is not None:
            self._backend.play_2d("ui_confirm_warm_chime", 0.48)

    def _route_turn_apex(self, event: RaceEvent) -> None:
        direction = str(event.data.get("direction", "ahead"))
        self._backend.speak(f"Apex {direction}.", event.priority)
        if self._catalog.get("ui_confirm_warm_chime") is not None:
            self._backend.play_2d("ui_confirm_warm_chime", 0.42)

    def _route_turn_line_event(self, event: RaceEvent) -> None:
        side = str(event.data.get("rail", "inside"))
        direction = str(event.data.get("direction", "ahead"))
        clearance = event.data.get("clearance_m")
        if event.event_type == "turn_too_tight":
            self._backend.speak(f"Too tight {direction}.", event.priority)
        elif event.event_type == "turn_too_wide":
            self._backend.speak(f"Too wide {direction}.", event.priority)
        elif side == "inside":
            self._backend.speak(f"Inside rail {direction}.", event.priority)
        else:
            self._backend.speak(f"Outside rail {direction}.", event.priority)
        sound_id = "turn_warning_left_rail" if side == "inside" and direction == "left" else "turn_warning_right_rail" if side == "inside" and direction == "right" else "turn_warning_right_rail" if side == "outside" and direction == "left" else "turn_warning_left_rail"
        if self._catalog.get(sound_id) is not None:
            self._backend.play_2d(sound_id, 0.5 if clearance is None else 0.42)

    def _route_pace_event(self, event: RaceEvent) -> None:
        labels = {
            "pace_cruising": "Cruising.",
            "pace_overpushing": "Overpushing.",
            "pace_recovering": "Recovering.",
            "pace_wasting_stamina": "Wasting stamina.",
        }
        self._backend.speak(labels[event.event_type], event.priority)

    def _route_status_event(self, event: RaceEvent) -> None:
        rank = event.data.get("rank", "?")
        distance = event.data.get("distance_remaining_m", "?")
        stamina = event.data.get("stamina", "?")
        weather = event.data.get("weather")
        weather_text = f" Weather {weather}." if weather else ""
        self._backend.speak(f"Rank {rank}. {distance} meters left. Stamina {stamina}.{weather_text}", event.priority)

    def _position(self, event: RaceEvent) -> RelativeAudioPosition:
        return RelativeAudioPosition(
            forward_m=float(event.data.get("forward_m", 0.0)),
            right_m=float(event.data.get("right_m", 0.0)),
        )

    def _play_cue(self, event_type: str) -> None:
        cue = self._cue_map.cue_for(event_type)
        if cue is not None:
            self._backend.play_2d(cue.sound_id, cue.volume)

