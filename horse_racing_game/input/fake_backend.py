from horse_racing_game.input.input_backend import InputBackend, PhysicalInput


class FakeInputBackend(InputBackend):
    def __init__(self, frames: tuple[tuple[PhysicalInput, ...], ...]) -> None:
        self._frames = list(frames)

    def poll(self) -> tuple[PhysicalInput, ...]:
        if not self._frames:
            return ()
        return self._frames.pop(0)