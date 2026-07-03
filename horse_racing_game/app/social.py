from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from horse_racing_game.app.file_directories import FileDirectories
from horse_racing_game.app.savedata import atomic_write_json, load_json_object


@dataclass(frozen=True)
class PlayerProfile:
    player_id: str
    display_name: str
    status_note: str = ""

    def __post_init__(self) -> None:
        if not self.player_id:
            raise ValueError("player_id must be non-empty")
        if not self.display_name:
            raise ValueError("display_name must be non-empty")


@dataclass(frozen=True)
class FriendRequest:
    from_player_id: str
    to_player_id: str
    status: str = "pending"

    def __post_init__(self) -> None:
        if not self.from_player_id:
            raise ValueError("from_player_id must be non-empty")
        if not self.to_player_id:
            raise ValueError("to_player_id must be non-empty")
        if self.from_player_id == self.to_player_id:
            raise ValueError("friend request requires two distinct players")
        if self.status not in {"pending", "accepted", "declined", "cancelled"}:
            raise ValueError("invalid friend request status")


@dataclass(frozen=True)
class Presence:
    player_id: str
    state: str = "offline"
    activity: str = ""

    def __post_init__(self) -> None:
        if not self.player_id:
            raise ValueError("player_id must be non-empty")
        if self.state not in {"offline", "online", "in_lobby", "racing"}:
            raise ValueError("invalid presence state")


@dataclass(frozen=True)
class SocialSnapshot:
    profiles: tuple[PlayerProfile, ...]
    friends: tuple[tuple[str, str], ...]
    pending_requests: tuple[FriendRequest, ...]
    blocked: tuple[tuple[str, str], ...]
    muted: tuple[tuple[str, str], ...]
    presence: tuple[Presence, ...]


class SocialGraph:
    def __init__(self) -> None:
        self._profiles: dict[str, PlayerProfile] = {}
        self._friend_requests: dict[tuple[str, str], FriendRequest] = {}
        self._friends: set[frozenset[str]] = set()
        self._blocked: set[tuple[str, str]] = set()
        self._muted: set[tuple[str, str]] = set()
        self._presence: dict[str, Presence] = {}
        self._recent_players: dict[str, list[str]] = {}

    def upsert_profile(self, profile: PlayerProfile) -> PlayerProfile:
        self._profiles[profile.player_id] = profile
        return profile

    def profile(self, player_id: str) -> PlayerProfile:
        try:
            return self._profiles[player_id]
        except KeyError as error:
            raise ValueError(f"unknown player id: {player_id}") from error

    def send_friend_request(self, from_player_id: str, to_player_id: str) -> FriendRequest:
        self._require_profile(from_player_id)
        self._require_profile(to_player_id)
        if self.is_blocked(from_player_id, to_player_id) or self.is_blocked(to_player_id, from_player_id):
            raise ValueError("blocked players cannot send friend requests")
        if self.are_friends(from_player_id, to_player_id):
            raise ValueError("players are already friends")
        request = FriendRequest(from_player_id, to_player_id)
        self._friend_requests[(from_player_id, to_player_id)] = request
        return request

    def accept_friend_request(self, from_player_id: str, to_player_id: str) -> FriendRequest:
        request = self._pending_request(from_player_id, to_player_id)
        accepted = FriendRequest(request.from_player_id, request.to_player_id, "accepted")
        self._friend_requests[(from_player_id, to_player_id)] = accepted
        self._friends.add(frozenset((from_player_id, to_player_id)))
        return accepted

    def decline_friend_request(self, from_player_id: str, to_player_id: str) -> FriendRequest:
        request = self._pending_request(from_player_id, to_player_id)
        declined = FriendRequest(request.from_player_id, request.to_player_id, "declined")
        self._friend_requests[(from_player_id, to_player_id)] = declined
        return declined

    def remove_friend(self, first_player_id: str, second_player_id: str) -> None:
        self._friends.discard(frozenset((first_player_id, second_player_id)))

    def are_friends(self, first_player_id: str, second_player_id: str) -> bool:
        return frozenset((first_player_id, second_player_id)) in self._friends

    def block(self, blocker_id: str, blocked_id: str) -> None:
        self._require_profile(blocker_id)
        self._require_profile(blocked_id)
        if blocker_id == blocked_id:
            raise ValueError("player cannot block themselves")
        self._blocked.add((blocker_id, blocked_id))
        self._friends.discard(frozenset((blocker_id, blocked_id)))

    def mute(self, muter_id: str, muted_id: str) -> None:
        self._require_profile(muter_id)
        self._require_profile(muted_id)
        if muter_id == muted_id:
            raise ValueError("player cannot mute themselves")
        self._muted.add((muter_id, muted_id))

    def is_blocked(self, blocker_id: str, blocked_id: str) -> bool:
        return (blocker_id, blocked_id) in self._blocked

    def is_muted(self, muter_id: str, muted_id: str) -> bool:
        return (muter_id, muted_id) in self._muted

    def set_presence(self, presence: Presence) -> Presence:
        self._require_profile(presence.player_id)
        self._presence[presence.player_id] = presence
        return presence

    def presence(self, player_id: str) -> Presence:
        return self._presence.get(player_id, Presence(player_id))

    def record_recent_player(self, player_id: str, recent_player_id: str, limit: int = 8) -> tuple[str, ...]:
        self._require_profile(player_id)
        self._require_profile(recent_player_id)
        if player_id == recent_player_id:
            return self.recent_players(player_id)
        recent = [item for item in self._recent_players.get(player_id, []) if item != recent_player_id]
        recent.insert(0, recent_player_id)
        self._recent_players[player_id] = recent[:limit]
        return self.recent_players(player_id)

    def recent_players(self, player_id: str) -> tuple[str, ...]:
        return tuple(self._recent_players.get(player_id, ()))

    def visible_friends(self, player_id: str) -> tuple[PlayerProfile, ...]:
        self._require_profile(player_id)
        friend_ids = sorted(
            next(item for item in friendship if item != player_id)
            for friendship in self._friends
            if player_id in friendship
        )
        return tuple(self._profiles[friend_id] for friend_id in friend_ids if not self.is_blocked(player_id, friend_id))

    def snapshot(self) -> SocialSnapshot:
        return SocialSnapshot(
            profiles=tuple(sorted(self._profiles.values(), key=lambda profile: profile.player_id)),
            friends=tuple(sorted(tuple(sorted(friendship)) for friendship in self._friends)),
            pending_requests=tuple(
                sorted(
                    (request for request in self._friend_requests.values() if request.status == "pending"),
                    key=lambda request: (request.from_player_id, request.to_player_id),
                )
            ),
            blocked=tuple(sorted(self._blocked)),
            muted=tuple(sorted(self._muted)),
            presence=tuple(sorted(self._presence.values(), key=lambda item: item.player_id)),
        )

    def recent_snapshot(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        return tuple(sorted((player_id, tuple(recent)) for player_id, recent in self._recent_players.items()))

    def _all_friend_requests(self) -> tuple[FriendRequest, ...]:
        return tuple(sorted(self._friend_requests.values(), key=lambda request: (request.from_player_id, request.to_player_id)))

    def _require_profile(self, player_id: str) -> PlayerProfile:
        return self.profile(player_id)

    def _pending_request(self, from_player_id: str, to_player_id: str) -> FriendRequest:
        request = self._friend_requests.get((from_player_id, to_player_id))
        if request is None or request.status != "pending":
            raise ValueError("friend request is not pending")
        return request


def social_graph_path(project_root: Path) -> Path:
    return FileDirectories(project_root).save_file("social_graph.json")


def save_social_graph(project_root: Path, graph: SocialGraph) -> None:
    snapshot = graph.snapshot()
    atomic_write_json(
        social_graph_path(project_root),
        {
            "profiles": [asdict(profile) for profile in snapshot.profiles],
            "friend_requests": [asdict(request) for request in graph._all_friend_requests()],
            "friends": [list(friendship) for friendship in snapshot.friends],
            "blocked": [list(item) for item in snapshot.blocked],
            "muted": [list(item) for item in snapshot.muted],
            "presence": [asdict(presence) for presence in snapshot.presence],
            "recent_players": [{"player_id": player_id, "recent": list(recent)} for player_id, recent in graph.recent_snapshot()],
        },
    )


def load_social_graph(project_root: Path) -> SocialGraph:
    data = load_json_object(social_graph_path(project_root))
    graph = SocialGraph()
    if data is None:
        return graph
    try:
        for item in _list(data.get("profiles")):
            graph.upsert_profile(PlayerProfile(str(item.get("player_id") or ""), str(item.get("display_name") or ""), str(item.get("status_note") or "")))
        for item in _list(data.get("friend_requests")):
            request = FriendRequest(
                str(item.get("from_player_id") or ""),
                str(item.get("to_player_id") or ""),
                str(item.get("status") or "pending"),
            )
            graph._friend_requests[(request.from_player_id, request.to_player_id)] = request
        for first, second in _pair_list(data.get("friends")):
            graph._require_profile(first)
            graph._require_profile(second)
            graph._friends.add(frozenset((first, second)))
        for first, second in _pair_list(data.get("blocked")):
            graph.block(first, second)
        for first, second in _pair_list(data.get("muted")):
            graph.mute(first, second)
        for item in _list(data.get("presence")):
            graph.set_presence(Presence(str(item.get("player_id") or ""), str(item.get("state") or "offline"), str(item.get("activity") or "")))
        for item in _list(data.get("recent_players")):
            player_id = str(item.get("player_id") or "")
            graph._require_profile(player_id)
            recent = tuple(recent_id for recent_id in _string_tuple(item.get("recent")) if recent_id in graph._profiles and recent_id != player_id)
            graph._recent_players[player_id] = list(dict.fromkeys(recent))[:8]
    except (TypeError, ValueError):
        return SocialGraph()
    return graph


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
