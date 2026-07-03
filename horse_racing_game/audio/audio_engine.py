from horse_racing_game.audio.event_policy import AudioEventPolicy
from horse_racing_game.audio.event_router import AudioEventRouter
from horse_racing_game.simulation.race_events import RaceEvent


class AudioEngine:
    def __init__(self, router: AudioEventRouter) -> None:
        self._router = router
        self._policy = AudioEventPolicy()

    def render_events(self, events: tuple[RaceEvent, ...]) -> None:
        ordered_events = sorted(events, key=lambda event: event.priority, reverse=True)
        for event in ordered_events:
            if self._policy.should_route(event):
                self._router.route(event)