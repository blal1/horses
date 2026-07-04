from dataclasses import dataclass


@dataclass(frozen=True)
class RivalProfile:
    horse_id: str
    display_name: str
    intro_line: str
    approach_line: str
    passing_line: str
    racing_style: str = ""
    rivalry_hook: str = ""
    falling_behind_line: str = ""
    blocking_line: str = ""

    def narrative_intro(self) -> str:
        """Short spoken introduction that gives the rival a clear identity:
        name, racing style, and a rivalry hook, falling back to the intro line."""
        parts = [self.display_name]
        if self.racing_style:
            parts.append(self.racing_style)
        hook = self.rivalry_hook or self.intro_line
        if hook:
            parts.append(hook)
        text = ". ".join(parts)
        if not text.endswith((".", "!", "?")):
            text += "."
        return text

    def line_for_event(self, event_type: str) -> str:
        """Spoken line for a rival race event, empty when the rival has none."""
        if event_type == "opponent_passing":
            return self.passing_line
        if event_type == "opponent_approaching":
            return self.approach_line
        if event_type == "opponent_falling_behind":
            return self.falling_behind_line
        if event_type == "opponent_blocking_inside":
            return self.blocking_line
        return ""
