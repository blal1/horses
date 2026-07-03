from __future__ import annotations

from dataclasses import dataclass

from horse_racing_game.input.commands import RaceCommand


TOUCH_ACTIONS = {"steer", "pace", "push", "jump", "duck", "status", "none"}


@dataclass(frozen=True)
class TouchGesture:
    kind: str
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    duration_s: float
    pointers: int = 1
    tap_count: int = 0

    def __post_init__(self) -> None:
        if self.kind not in {"tap", "drag", "swipe", "long_press"}:
            raise ValueError("unsupported touch gesture kind")
        if self.duration_s < 0.0:
            raise ValueError("duration_s must be non-negative")
        if self.pointers < 1:
            raise ValueError("pointers must be positive")
        if self.tap_count < 0:
            raise ValueError("tap_count must be non-negative")

    @property
    def delta_x(self) -> float:
        return self.end_x - self.start_x

    @property
    def delta_y(self) -> float:
        return self.end_y - self.start_y


@dataclass(frozen=True)
class TouchGestureProfile:
    profile_id: str = "android-accessible-default"
    axis_full_scale_px: float = 160.0
    min_swipe_distance_px: float = 48.0
    long_press_seconds: float = 0.45
    double_tap_max_seconds: float = 0.35
    analog_deadzone: float = 0.12

    def __post_init__(self) -> None:
        if not self.profile_id:
            raise ValueError("profile_id must be non-empty")
        if self.axis_full_scale_px <= 0.0:
            raise ValueError("axis_full_scale_px must be positive")
        if self.min_swipe_distance_px <= 0.0:
            raise ValueError("min_swipe_distance_px must be positive")
        if self.long_press_seconds <= 0.0:
            raise ValueError("long_press_seconds must be positive")
        if self.double_tap_max_seconds <= 0.0:
            raise ValueError("double_tap_max_seconds must be positive")
        if not 0.0 <= self.analog_deadzone < 1.0:
            raise ValueError("analog_deadzone must be in [0, 1)")

    def command_for(self, gesture: TouchGesture) -> RaceCommand:
        if gesture.kind == "drag":
            return RaceCommand(
                throttle_delta=self._axis(-gesture.delta_y),
                lateral_delta=self._axis(gesture.delta_x),
            )
        if gesture.kind == "long_press" and gesture.duration_s >= self.long_press_seconds:
            return RaceCommand(request_status=True)
        if gesture.kind == "tap":
            if gesture.pointers >= 2:
                return RaceCommand(request_status=True)
            if gesture.tap_count >= 2 and gesture.duration_s <= self.double_tap_max_seconds:
                return RaceCommand(push_requested=True)
            return RaceCommand()
        if gesture.kind == "swipe":
            return self._swipe_command(gesture)
        return RaceCommand()

    def action_for(self, gesture: TouchGesture) -> str:
        command = self.command_for(gesture)
        if command.jump_requested:
            return "jump"
        if command.duck_requested:
            return "duck"
        if command.push_requested:
            return "push"
        if command.request_status:
            return "status"
        if command.lateral_delta != 0.0:
            return "steer"
        if command.throttle_delta != 0.0:
            return "pace"
        return "none"

    def _swipe_command(self, gesture: TouchGesture) -> RaceCommand:
        abs_x = abs(gesture.delta_x)
        abs_y = abs(gesture.delta_y)
        if max(abs_x, abs_y) < self.min_swipe_distance_px:
            return RaceCommand()
        if abs_y >= abs_x:
            return RaceCommand(jump_requested=gesture.delta_y < 0.0, duck_requested=gesture.delta_y > 0.0)
        return RaceCommand(lateral_delta=self._axis(gesture.delta_x))

    def _axis(self, distance_px: float) -> float:
        value = max(-1.0, min(1.0, distance_px / self.axis_full_scale_px))
        return 0.0 if abs(value) < self.analog_deadzone else value


def default_android_gesture_profile() -> TouchGestureProfile:
    return TouchGestureProfile()
