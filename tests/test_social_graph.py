import unittest
import tempfile
from pathlib import Path

from horse_racing_game.app.social import (
    FriendRequest,
    PlayerProfile,
    Presence,
    SocialGraph,
    load_social_graph,
    save_social_graph,
    social_graph_path,
)


class SocialGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = SocialGraph()
        self.graph.upsert_profile(PlayerProfile("alice", "Alice"))
        self.graph.upsert_profile(PlayerProfile("bob", "Bob"))
        self.graph.upsert_profile(PlayerProfile("carol", "Carol"))

    def test_friend_request_acceptance_adds_visible_friendship(self) -> None:
        request = self.graph.send_friend_request("alice", "bob")

        self.assertEqual(request.status, "pending")
        accepted = self.graph.accept_friend_request("alice", "bob")

        self.assertEqual(accepted.status, "accepted")
        self.assertTrue(self.graph.are_friends("alice", "bob"))
        self.assertEqual([profile.player_id for profile in self.graph.visible_friends("alice")], ["bob"])

    def test_friend_request_can_be_declined_and_cannot_be_reaccepted(self) -> None:
        self.graph.send_friend_request("alice", "bob")
        declined = self.graph.decline_friend_request("alice", "bob")

        self.assertEqual(declined.status, "declined")
        with self.assertRaises(ValueError):
            self.graph.accept_friend_request("alice", "bob")

    def test_block_removes_friendship_and_blocks_new_requests(self) -> None:
        self.graph.send_friend_request("alice", "bob")
        self.graph.accept_friend_request("alice", "bob")

        self.graph.block("alice", "bob")

        self.assertFalse(self.graph.are_friends("alice", "bob"))
        self.assertTrue(self.graph.is_blocked("alice", "bob"))
        with self.assertRaises(ValueError):
            self.graph.send_friend_request("bob", "alice")

    def test_mute_is_directional_without_removing_friendship(self) -> None:
        self.graph.send_friend_request("alice", "bob")
        self.graph.accept_friend_request("alice", "bob")

        self.graph.mute("alice", "bob")

        self.assertTrue(self.graph.are_friends("alice", "bob"))
        self.assertTrue(self.graph.is_muted("alice", "bob"))
        self.assertFalse(self.graph.is_muted("bob", "alice"))

    def test_presence_and_recent_players_are_tracked(self) -> None:
        self.graph.set_presence(Presence("alice", "in_lobby", "Waiting for duel"))
        self.graph.record_recent_player("alice", "bob")
        self.graph.record_recent_player("alice", "carol")
        self.graph.record_recent_player("alice", "bob")

        self.assertEqual(self.graph.presence("alice").state, "in_lobby")
        self.assertEqual(self.graph.recent_players("alice"), ("bob", "carol"))
        self.assertEqual(self.graph.presence("bob").state, "offline")

    def test_snapshot_contains_sorted_public_state(self) -> None:
        self.graph.send_friend_request("alice", "bob")
        self.graph.send_friend_request("carol", "alice")
        self.graph.accept_friend_request("alice", "bob")
        self.graph.block("alice", "carol")
        self.graph.mute("bob", "alice")
        self.graph.set_presence(Presence("bob", "online"))

        snapshot = self.graph.snapshot()

        self.assertEqual([profile.player_id for profile in snapshot.profiles], ["alice", "bob", "carol"])
        self.assertEqual(snapshot.friends, (("alice", "bob"),))
        self.assertEqual(snapshot.blocked, (("alice", "carol"),))
        self.assertEqual(snapshot.muted, (("bob", "alice"),))
        self.assertEqual([request.from_player_id for request in snapshot.pending_requests], ["carol"])
        self.assertEqual([presence.player_id for presence in snapshot.presence], ["bob"])

    def test_social_graph_persists_snapshot_and_recent_players(self) -> None:
        self.graph.send_friend_request("alice", "bob")
        self.graph.accept_friend_request("alice", "bob")
        self.graph.send_friend_request("carol", "alice")
        self.graph.block("alice", "carol")
        self.graph.mute("bob", "alice")
        self.graph.set_presence(Presence("bob", "online", "Ready"))
        self.graph.record_recent_player("alice", "bob")
        self.graph.record_recent_player("alice", "carol")
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)

            save_social_graph(project_root, self.graph)
            loaded = load_social_graph(project_root)

            self.assertTrue(social_graph_path(project_root).exists())
            self.assertEqual(loaded.snapshot(), self.graph.snapshot())
            self.assertEqual(loaded.recent_players("alice"), ("carol", "bob"))
            self.assertTrue(loaded.are_friends("alice", "bob"))
            self.assertTrue(loaded.is_blocked("alice", "carol"))
            self.assertTrue(loaded.is_muted("bob", "alice"))

    def test_corrupt_social_graph_loads_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            path = social_graph_path(project_root)
            path.parent.mkdir(parents=True)
            path.write_text('{"profiles": [{"player_id": "", "display_name": "Broken"}]}', encoding="utf-8")

            loaded = load_social_graph(project_root)

            self.assertEqual(loaded.snapshot().profiles, ())

    def test_invalid_social_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            PlayerProfile("", "Player")
        with self.assertRaises(ValueError):
            FriendRequest("alice", "alice")
        with self.assertRaises(ValueError):
            Presence("alice", "away")


if __name__ == "__main__":
    unittest.main()
