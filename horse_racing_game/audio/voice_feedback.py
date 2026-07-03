from dataclasses import dataclass

from horse_racing_game.audio.audio_backend import AudioBackend
from horse_racing_game.simulation.race_events import RaceEvent
from horse_racing_game.simulation.race_state import RaceState


HELP_TEXT = "Arrows, ZQSD, or WASD control pace and line. Space pushes. J jumps. K or Control ducks. Tab or Enter gives status. R repeats. M opens menu. N restarts. Escape quits."


@dataclass(frozen=True)
class SpokenMessage:
    text: str
    priority: int


class VoiceFeedbackController:
    def __init__(self, backend: AudioBackend) -> None:
        self._backend = backend
        self._last_message: SpokenMessage | None = None

    def observe_events(self, events: tuple[RaceEvent, ...], state: RaceState) -> None:
        for event in events:
            message = self._message_for_event(event, state)
            if message is not None:
                self._last_message = message

    def repeat_last(self) -> None:
        if self._last_message is None:
            self._backend.speak("No message to repeat.", 40)
            return
        self._backend.speak(self._last_message.text, self._last_message.priority)

    def speak_help(self) -> None:
        self._backend.speak(HELP_TEXT, 90)

    def _message_for_event(self, event: RaceEvent, state: RaceState) -> SpokenMessage | None:
        if event.event_type == "race_started":
            return SpokenMessage("Start.", event.priority)
        if event.event_type in {"turn_incoming", "turn_entry"}:
            return SpokenMessage(f"Turn entry {event.data.get('direction', 'ahead')}.", event.priority)
        if event.event_type == "turn_exit":
            return SpokenMessage(f"Turn exit {event.data.get('direction', 'ahead')}.", event.priority)
        if event.event_type == "turn_apex":
            return SpokenMessage(f"Apex {event.data.get('direction', 'ahead')}.", event.priority)
        if event.event_type == "turn_rail_inside":
            return SpokenMessage(f"Inside rail {event.data.get('direction', 'ahead')}.", event.priority)
        if event.event_type == "turn_rail_outside":
            return SpokenMessage(f"Outside rail {event.data.get('direction', 'ahead')}.", event.priority)
        if event.event_type == "turn_too_tight":
            return SpokenMessage(f"Too tight {event.data.get('direction', 'ahead')}.", event.priority)
        if event.event_type == "turn_too_wide":
            return SpokenMessage(f"Too wide {event.data.get('direction', 'ahead')}.", event.priority)
        if event.event_type == "status_requested":
            return self._status_message(event)
        if event.event_type == "low_stamina":
            return SpokenMessage("Low stamina.", event.priority)
        if event.event_type == "critical_stamina":
            return SpokenMessage("Critical stamina.", event.priority)
        if event.event_type == "pace_cruising":
            return SpokenMessage("Cruising.", event.priority)
        if event.event_type == "pace_overpushing":
            return SpokenMessage("Overpushing.", event.priority)
        if event.event_type == "pace_recovering":
            return SpokenMessage("Recovering.", event.priority)
        if event.event_type == "pace_wasting_stamina":
            return SpokenMessage("Wasting stamina.", event.priority)
        if event.event_type == "obstacle_warning":
            return SpokenMessage(
                f"Obstacle {event.data.get('label', 'ahead')}. {self._action_text(event.data.get('required_action'))}.",
                event.priority,
            )
        if event.event_type == "obstacle_hit":
            return SpokenMessage(f"Hit {event.data.get('label', 'obstacle')}.", event.priority)
        if event.event_type == "obstacle_near_miss":
            return SpokenMessage(f"Near miss {event.data.get('label', 'obstacle')}.", event.priority)
        if event.event_type == "obstacle_avoided":
            quality = event.data.get("timing_quality")
            prefix = f"{str(quality).title()} " if quality in {"perfect", "good", "late"} else ""
            return SpokenMessage(
                f"{prefix}{self._action_text(event.data.get('resolution'))} confirmed.",
                event.priority,
            )
        if event.event_type == "final_stretch":
            return SpokenMessage("Final stretch.", event.priority)
        if event.event_type == "finish_line_crossed":
            return SpokenMessage(f"Finished rank {event.data.get('rank', '?')}.", event.priority)
        if event.event_type == "race_finished":
            player = state.player()
            return SpokenMessage(f"Race finished. Rank {player.rank}.", event.priority)
        return None

    def _status_message(self, event: RaceEvent) -> SpokenMessage:
        rank = event.data.get("rank", "?")
        distance = event.data.get("distance_remaining_m", "?")
        stamina = event.data.get("stamina", "?")
        weather = event.data.get("weather")
        weather_text = f" Weather {weather}." if weather else ""
        return SpokenMessage(f"Rank {rank}. {distance} meters left. Stamina {stamina}.{weather_text}", event.priority)

    def _action_text(self, action: object) -> str:
        if action == "jump":
            return "jump"
        if action == "duck":
            return "duck"
        return "dodge"
