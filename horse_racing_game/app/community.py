from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path

from horse_racing_game.app.file_directories import FileDirectories
from horse_racing_game.app.savedata import atomic_write_json, load_json_object


CLUB_ROLES = {"owner", "moderator", "member"}
REPORT_STATUSES = {"open", "reviewed", "dismissed"}
MODERATION_ACTIONS = {"warn", "mute", "kick", "ban"}


@dataclass(frozen=True)
class ClubMember:
    player_id: str
    role: str = "member"

    def __post_init__(self) -> None:
        if not self.player_id:
            raise ValueError("player_id must be non-empty")
        if self.role not in CLUB_ROLES:
            raise ValueError("invalid club role")


@dataclass(frozen=True)
class Club:
    club_id: str
    name: str
    tag: str
    members: tuple[ClubMember, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not self.club_id:
            raise ValueError("club_id must be non-empty")
        if not self.name:
            raise ValueError("name must be non-empty")
        if not (2 <= len(self.tag) <= 5 and self.tag.isalnum() and self.tag.upper() == self.tag):
            raise ValueError("tag must be 2-5 uppercase alphanumeric characters")
        if not self.members:
            raise ValueError("club requires at least one member")
        if sum(1 for member in self.members if member.role == "owner") != 1:
            raise ValueError("club requires exactly one owner")

    def member_ids(self) -> tuple[str, ...]:
        return tuple(member.player_id for member in self.members)

    def role_for(self, player_id: str) -> str | None:
        for member in self.members:
            if member.player_id == player_id:
                return member.role
        return None


@dataclass(frozen=True)
class ClubChatMessage:
    club_id: str
    sender_id: str
    body: str
    timestamp_s: float = 0.0

    def __post_init__(self) -> None:
        if not self.club_id:
            raise ValueError("club_id must be non-empty")
        if not self.sender_id:
            raise ValueError("sender_id must be non-empty")
        if not self.body.strip():
            raise ValueError("body must be non-empty")


@dataclass(frozen=True)
class ScheduledEvent:
    event_id: str
    club_id: str
    title: str
    starts_at_s: float
    host_id: str
    participant_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id must be non-empty")
        if not self.club_id:
            raise ValueError("club_id must be non-empty")
        if not self.title:
            raise ValueError("title must be non-empty")
        if not self.host_id:
            raise ValueError("host_id must be non-empty")


@dataclass(frozen=True)
class MessageReport:
    report_id: str
    club_id: str
    reporter_id: str
    message_sender_id: str
    message_body: str
    reason: str
    status: str = "open"

    def __post_init__(self) -> None:
        if not self.report_id:
            raise ValueError("report_id must be non-empty")
        if not self.club_id:
            raise ValueError("club_id must be non-empty")
        if not self.reporter_id:
            raise ValueError("reporter_id must be non-empty")
        if not self.message_sender_id:
            raise ValueError("message_sender_id must be non-empty")
        if not self.message_body.strip():
            raise ValueError("message_body must be non-empty")
        if not self.reason:
            raise ValueError("reason must be non-empty")
        if self.status not in REPORT_STATUSES:
            raise ValueError("invalid report status")


@dataclass(frozen=True)
class ModerationAction:
    action_id: str
    club_id: str
    moderator_id: str
    target_id: str
    action: str
    reason: str
    duration_s: float | None = None

    def __post_init__(self) -> None:
        if not self.action_id:
            raise ValueError("action_id must be non-empty")
        if not self.club_id:
            raise ValueError("club_id must be non-empty")
        if not self.moderator_id:
            raise ValueError("moderator_id must be non-empty")
        if not self.target_id:
            raise ValueError("target_id must be non-empty")
        if self.action not in MODERATION_ACTIONS:
            raise ValueError("invalid moderation action")
        if not self.reason:
            raise ValueError("reason must be non-empty")
        if self.duration_s is not None and self.duration_s <= 0:
            raise ValueError("duration_s must be positive when provided")


@dataclass(frozen=True)
class ProfanityControl:
    blocked_terms: tuple[str, ...] = ()
    replacement: str = "[filtered]"

    def filter_text(self, text: str) -> str:
        filtered = text
        for term in self.blocked_terms:
            if term:
                filtered = _replace_case_insensitive(filtered, term, self.replacement)
        return filtered


@dataclass(frozen=True)
class RateLimitRule:
    max_messages: int = 5
    window_s: float = 10.0

    def __post_init__(self) -> None:
        if self.max_messages < 1:
            raise ValueError("max_messages must be positive")
        if self.window_s <= 0:
            raise ValueError("window_s must be positive")


class AntiSpamGuard:
    def __init__(self, rule: RateLimitRule = RateLimitRule()) -> None:
        self._rule = rule
        self._message_times: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def allow_message(self, club_id: str, player_id: str, timestamp_s: float) -> bool:
        key = (club_id, player_id)
        times = self._message_times[key]
        while times and timestamp_s - times[0] >= self._rule.window_s:
            times.popleft()
        if len(times) >= self._rule.max_messages:
            return False
        times.append(timestamp_s)
        return True


@dataclass(frozen=True)
class CommunitySnapshot:
    clubs: tuple[Club, ...]
    scheduled_events: tuple[ScheduledEvent, ...]
    open_reports: tuple[MessageReport, ...]
    moderation_actions: tuple[ModerationAction, ...]


class CommunityHub:
    def __init__(
        self,
        profanity: ProfanityControl | None = None,
        rate_limit: RateLimitRule | None = None,
        max_chat_messages: int = 32,
    ) -> None:
        self._clubs: dict[str, Club] = {}
        self._club_chat: dict[str, deque[ClubChatMessage]] = defaultdict(lambda: deque(maxlen=max_chat_messages))
        self._events: dict[str, ScheduledEvent] = {}
        self._reports: dict[str, MessageReport] = {}
        self._actions: dict[str, ModerationAction] = {}
        self._banned: set[tuple[str, str]] = set()
        self._muted_until: dict[tuple[str, str], float] = {}
        self._profanity = profanity or ProfanityControl()
        self._spam = AntiSpamGuard(rate_limit or RateLimitRule())

    def create_club(self, club_id: str, name: str, tag: str, owner_id: str, description: str = "") -> Club:
        if club_id in self._clubs:
            raise ValueError("club already exists")
        club = Club(club_id, name, tag, (ClubMember(owner_id, "owner"),), description)
        self._clubs[club_id] = club
        return club

    def club(self, club_id: str) -> Club:
        try:
            return self._clubs[club_id]
        except KeyError as error:
            raise ValueError(f"unknown club id: {club_id}") from error

    def add_member(self, club_id: str, player_id: str, role: str = "member") -> Club:
        club = self.club(club_id)
        if club.role_for(player_id) is not None:
            raise ValueError("player is already a club member")
        if (club_id, player_id) in self._banned:
            raise ValueError("banned player cannot join club")
        updated = Club(club.club_id, club.name, club.tag, (*club.members, ClubMember(player_id, role)), club.description)
        self._clubs[club_id] = updated
        return updated

    def post_team_message(self, club_id: str, sender_id: str, body: str, timestamp_s: float = 0.0) -> ClubChatMessage:
        club = self.club(club_id)
        if club.role_for(sender_id) is None:
            raise ValueError("sender is not a club member")
        if self.is_banned(club_id, sender_id):
            raise ValueError("banned player cannot post")
        if self.is_muted(club_id, sender_id, timestamp_s):
            raise ValueError("muted player cannot post")
        if not self._spam.allow_message(club_id, sender_id, timestamp_s):
            raise ValueError("rate limit exceeded")
        message = ClubChatMessage(club_id, sender_id, self._profanity.filter_text(body), timestamp_s)
        self._club_chat[club_id].appendleft(message)
        return message

    def team_chat(self, club_id: str) -> tuple[ClubChatMessage, ...]:
        self.club(club_id)
        return tuple(self._club_chat[club_id])

    def schedule_event(
        self,
        event_id: str,
        club_id: str,
        title: str,
        starts_at_s: float,
        host_id: str,
    ) -> ScheduledEvent:
        club = self.club(club_id)
        if club.role_for(host_id) is None:
            raise ValueError("host is not a club member")
        if event_id in self._events:
            raise ValueError("event already exists")
        event = ScheduledEvent(event_id, club_id, title, starts_at_s, host_id, (host_id,))
        self._events[event_id] = event
        return event

    def join_event(self, event_id: str, player_id: str) -> ScheduledEvent:
        event = self._event(event_id)
        club = self.club(event.club_id)
        if club.role_for(player_id) is None:
            raise ValueError("participant is not a club member")
        if player_id in event.participant_ids:
            return event
        updated = ScheduledEvent(
            event.event_id,
            event.club_id,
            event.title,
            event.starts_at_s,
            event.host_id,
            (*event.participant_ids, player_id),
        )
        self._events[event_id] = updated
        return updated

    def report_message(
        self,
        report_id: str,
        message: ClubChatMessage,
        reporter_id: str,
        reason: str,
    ) -> MessageReport:
        club = self.club(message.club_id)
        if club.role_for(reporter_id) is None:
            raise ValueError("reporter is not a club member")
        if report_id in self._reports:
            raise ValueError("report already exists")
        report = MessageReport(report_id, message.club_id, reporter_id, message.sender_id, message.body, reason)
        self._reports[report_id] = report
        return report

    def resolve_report(self, report_id: str, status: str) -> MessageReport:
        report = self._report(report_id)
        resolved = MessageReport(
            report.report_id,
            report.club_id,
            report.reporter_id,
            report.message_sender_id,
            report.message_body,
            report.reason,
            status,
        )
        self._reports[report_id] = resolved
        return resolved

    def apply_moderation_action(self, action: ModerationAction, timestamp_s: float = 0.0) -> ModerationAction:
        club = self.club(action.club_id)
        if club.role_for(action.moderator_id) not in {"owner", "moderator"}:
            raise ValueError("moderator lacks permission")
        if club.role_for(action.target_id) is None:
            raise ValueError("target is not a club member")
        self._actions[action.action_id] = action
        if action.action == "ban":
            self._banned.add((action.club_id, action.target_id))
        elif action.action == "mute":
            self._muted_until[(action.club_id, action.target_id)] = timestamp_s + (action.duration_s or 60.0)
        return action

    def is_banned(self, club_id: str, player_id: str) -> bool:
        return (club_id, player_id) in self._banned

    def is_muted(self, club_id: str, player_id: str, timestamp_s: float) -> bool:
        return self._muted_until.get((club_id, player_id), -1.0) > timestamp_s

    def snapshot(self) -> CommunitySnapshot:
        return CommunitySnapshot(
            clubs=tuple(sorted(self._clubs.values(), key=lambda club: club.club_id)),
            scheduled_events=tuple(sorted(self._events.values(), key=lambda event: (event.starts_at_s, event.event_id))),
            open_reports=tuple(
                sorted(
                    (report for report in self._reports.values() if report.status == "open"),
                    key=lambda report: report.report_id,
                )
            ),
            moderation_actions=tuple(sorted(self._actions.values(), key=lambda action: action.action_id)),
        )

    def chat_snapshot(self) -> tuple[tuple[str, tuple[ClubChatMessage, ...]], ...]:
        return tuple(sorted((club_id, tuple(messages)) for club_id, messages in self._club_chat.items()))

    def reports_snapshot(self) -> tuple[MessageReport, ...]:
        return tuple(sorted(self._reports.values(), key=lambda report: report.report_id))

    def banned_snapshot(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._banned))

    def muted_until_snapshot(self) -> tuple[tuple[str, str, float], ...]:
        return tuple(sorted((club_id, player_id, timestamp) for (club_id, player_id), timestamp in self._muted_until.items()))

    def _event(self, event_id: str) -> ScheduledEvent:
        try:
            return self._events[event_id]
        except KeyError as error:
            raise ValueError(f"unknown event id: {event_id}") from error

    def _report(self, report_id: str) -> MessageReport:
        try:
            return self._reports[report_id]
        except KeyError as error:
            raise ValueError(f"unknown report id: {report_id}") from error


def community_hub_path(project_root: Path) -> Path:
    return FileDirectories(project_root).save_file("community_hub.json")


def save_community_hub(project_root: Path, hub: CommunityHub) -> None:
    snapshot = hub.snapshot()
    atomic_write_json(
        community_hub_path(project_root),
        {
            "clubs": [_club_to_dict(club) for club in snapshot.clubs],
            "club_chat": [
                {"club_id": club_id, "messages": [asdict(message) for message in messages]}
                for club_id, messages in hub.chat_snapshot()
            ],
            "scheduled_events": [asdict(event) for event in snapshot.scheduled_events],
            "reports": [asdict(report) for report in hub.reports_snapshot()],
            "moderation_actions": [asdict(action) for action in snapshot.moderation_actions],
            "banned": [list(item) for item in hub.banned_snapshot()],
            "muted_until": [
                {"club_id": club_id, "player_id": player_id, "until_s": until_s}
                for club_id, player_id, until_s in hub.muted_until_snapshot()
            ],
        },
    )


def load_community_hub(project_root: Path) -> CommunityHub:
    data = load_json_object(community_hub_path(project_root))
    hub = CommunityHub()
    if data is None:
        return hub
    try:
        for item in _list(data.get("clubs")):
            members = tuple(
                ClubMember(str(member.get("player_id") or ""), str(member.get("role") or "member"))
                for member in _list(item.get("members"))
            )
            club = Club(
                str(item.get("club_id") or ""),
                str(item.get("name") or ""),
                str(item.get("tag") or ""),
                members,
                str(item.get("description") or ""),
            )
            hub._clubs[club.club_id] = club
        for item in _list(data.get("club_chat")):
            club_id = str(item.get("club_id") or "")
            hub.club(club_id)
            messages = deque(maxlen=32)
            for message in _list(item.get("messages")):
                messages.append(
                    ClubChatMessage(
                        str(message.get("club_id") or ""),
                        str(message.get("sender_id") or ""),
                        str(message.get("body") or ""),
                        float(message.get("timestamp_s") or 0.0),
                    )
                )
            hub._club_chat[club_id] = messages
        for item in _list(data.get("scheduled_events")):
            event = ScheduledEvent(
                str(item.get("event_id") or ""),
                str(item.get("club_id") or ""),
                str(item.get("title") or ""),
                float(item.get("starts_at_s") or 0.0),
                str(item.get("host_id") or ""),
                _string_tuple(item.get("participant_ids")),
            )
            hub.club(event.club_id)
            hub._events[event.event_id] = event
        for item in _list(data.get("reports")):
            report = MessageReport(
                str(item.get("report_id") or ""),
                str(item.get("club_id") or ""),
                str(item.get("reporter_id") or ""),
                str(item.get("message_sender_id") or ""),
                str(item.get("message_body") or ""),
                str(item.get("reason") or ""),
                str(item.get("status") or "open"),
            )
            hub.club(report.club_id)
            hub._reports[report.report_id] = report
        for item in _list(data.get("moderation_actions")):
            duration_value = item.get("duration_s")
            action = ModerationAction(
                str(item.get("action_id") or ""),
                str(item.get("club_id") or ""),
                str(item.get("moderator_id") or ""),
                str(item.get("target_id") or ""),
                str(item.get("action") or ""),
                str(item.get("reason") or ""),
                None if duration_value is None else float(duration_value),
            )
            hub.club(action.club_id)
            hub._actions[action.action_id] = action
        for first, second in _pair_list(data.get("banned")):
            hub.club(first)
            hub._banned.add((first, second))
        for item in _list(data.get("muted_until")):
            club_id = str(item.get("club_id") or "")
            player_id = str(item.get("player_id") or "")
            hub.club(club_id)
            if not player_id:
                raise ValueError("muted player id must be non-empty")
            hub._muted_until[(club_id, player_id)] = float(item.get("until_s") or 0.0)
    except (TypeError, ValueError):
        return CommunityHub()
    return hub


def _club_to_dict(club: Club) -> dict[str, object]:
    return {
        "club_id": club.club_id,
        "name": club.name,
        "tag": club.tag,
        "members": [asdict(member) for member in club.members],
        "description": club.description,
    }


def _list(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _pair_list(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        return ()
    pairs: list[tuple[str, str]] = []
    for item in value:
        if isinstance(item, list) and len(item) == 2 and isinstance(item[0], str) and isinstance(item[1], str):
            pairs.append((item[0], item[1]))
    return tuple(pairs)


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _replace_case_insensitive(text: str, term: str, replacement: str) -> str:
    lowered = text.lower()
    needle = term.lower()
    output = []
    index = 0
    while True:
        match_index = lowered.find(needle, index)
        if match_index < 0:
            output.append(text[index:])
            return "".join(output)
        output.append(text[index:match_index])
        output.append(replacement)
        index = match_index + len(term)
