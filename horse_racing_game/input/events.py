from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from horse_racing_game.input.commands import RaceCommand
from horse_racing_game.input.key_hold import KeyHoldTracker


@dataclass(frozen=True)
class ControlScheme:
    throttle_up: tuple[int, ...]
    throttle_down: tuple[int, ...]
    lateral_left: tuple[int, ...]
    lateral_right: tuple[int, ...]
    push: tuple[int, ...]
    jump: tuple[int, ...]
    duck: tuple[int, ...]
    status: tuple[int, ...]


DEFAULT_CONTROL_SCHEME = ControlScheme(
    throttle_up=(pygame.K_UP, pygame.K_z),
    throttle_down=(pygame.K_DOWN, pygame.K_s),
    lateral_left=(pygame.K_LEFT, pygame.K_q),
    lateral_right=(pygame.K_RIGHT, pygame.K_d),
    push=(pygame.K_j,),
    jump=(pygame.K_SPACE,),
    duck=(pygame.K_LCTRL, pygame.K_RCTRL),
    status=(pygame.K_TAB,),
)

MULTIPLAYER_GUEST_SCHEME = ControlScheme(
    throttle_up=(pygame.K_t,),
    throttle_down=(pygame.K_g,),
    lateral_left=(pygame.K_f,),
    lateral_right=(pygame.K_h,),
    push=(pygame.K_r,),
    jump=(pygame.K_y,),
    duck=(pygame.K_u,),
    status=(pygame.K_o,),
)


@dataclass(frozen=True)
class InputEvent:
    kind: str
    key_code: int
    held_seconds: float = 0.0


@dataclass
class KeyboardControlState:
    """Keyboard input model with hold-duration awareness.

    This keeps the current command stream compatible with `RaceCommand` while
    shaping held keys so sustained input feels less binary.
    """

    ramp_seconds: float = 0.22
    lateral_decay: float = 0.84
    held_keys: set[int] = field(default_factory=set)
    tracker: KeyHoldTracker = field(default_factory=KeyHoldTracker)
    control_scheme: ControlScheme = DEFAULT_CONTROL_SCHEME
    last_lateral: float = 0.0

    def key_down(self, key_code: int) -> InputEvent:
        self.held_keys.add(key_code)
        self.tracker.advance(0.0, self.held_keys)
        return InputEvent("keydown", key_code, self.tracker.held_seconds(key_code))

    def key_up(self, key_code: int) -> InputEvent:
        held_seconds = self.tracker.held_seconds(key_code)
        self.held_keys.discard(key_code)
        self.tracker.release(key_code)
        return InputEvent("keyup", key_code, held_seconds)

    def advance(self, delta_s: float) -> None:
        self.tracker.advance(delta_s, self.held_keys)

    def command(self) -> RaceCommand:
        throttle_delta = self.tracker.axis(
            self.control_scheme.throttle_up,
            self.control_scheme.throttle_down,
            ramp_seconds=self.ramp_seconds,
            floor=0.62,
        )
        lateral_delta = self.tracker.axis(
            self.control_scheme.lateral_right,
            self.control_scheme.lateral_left,
            ramp_seconds=self.ramp_seconds,
            floor=0.58,
        )
        if lateral_delta != 0.0:
            self.last_lateral = lateral_delta
        else:
            self.last_lateral *= self.lateral_decay
            if abs(self.last_lateral) < 0.02:
                self.last_lateral = 0.0
        return RaceCommand(
            throttle_delta=throttle_delta,
            lateral_delta=self.last_lateral if lateral_delta == 0.0 else lateral_delta,
            push_requested=self._any_held(self.control_scheme.push),
            jump_requested=self._any_held(self.control_scheme.jump),
            duck_requested=self._any_held(self.control_scheme.duck),
            request_status=self._any_held(self.control_scheme.status),
        )

    def describe(self) -> str:
        if not self.held_keys:
            return "No input"
        parts: list[str] = []
        if self.tracker.axis(self.control_scheme.throttle_up, self.control_scheme.throttle_down) > 0.0:
            parts.append("accelerate")
        elif self.tracker.axis(self.control_scheme.throttle_down, self.control_scheme.throttle_up) > 0.0:
            parts.append("slow")
        if self.tracker.axis(self.control_scheme.lateral_right, self.control_scheme.lateral_left) > 0.0:
            parts.append("right")
        elif self.tracker.axis(self.control_scheme.lateral_left, self.control_scheme.lateral_right) > 0.0:
            parts.append("left")
        if self._any_held(self.control_scheme.push):
            parts.append("push")
        if self._any_held(self.control_scheme.jump):
            parts.append("jump")
        if self._any_held(self.control_scheme.duck):
            parts.append("duck")
        if self._any_held(self.control_scheme.status):
            parts.append("status")
        return ", ".join(parts) if parts else "Hold"

    def _any_held(self, keys: tuple[int, ...]) -> bool:
        return any(self.tracker.is_held(key_code) for key_code in keys)
