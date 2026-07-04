import unittest
import tempfile
from pathlib import Path

from horse_racing_game.app.community import (
    Club,
    ClubMember,
    CommunityHub,
    ModerationAppeal,
    ModerationAction,
    ProfanityControl,
    RateLimitRule,
    community_hub_path,
    load_community_hub,
    save_community_hub,
)


class CommunityHubTests(unittest.TestCase):
    def setUp(self) -> None:
        self.hub = CommunityHub(
            profanity=ProfanityControl(("badword",)),
            rate_limit=RateLimitRule(max_messages=2, window_s=5.0),
        )
        self.hub.create_club("club-1", "Rail Riders", "RAIL", "alice")
        self.hub.add_member("club-1", "bob")
        self.hub.add_member("club-1", "carol", "moderator")

    def test_club_creation_and_membership_roles(self) -> None:
        club = self.hub.club("club-1")

        self.assertEqual(club.tag, "RAIL")
        self.assertEqual(club.member_ids(), ("alice", "bob", "carol"))
        self.assertEqual(club.role_for("alice"), "owner")
        self.assertEqual(club.role_for("bob"), "member")

    def test_team_chat_filters_profanity_and_keeps_newest_first(self) -> None:
        first = self.hub.post_team_message("club-1", "alice", "Ready up", timestamp_s=1.0)
        second = self.hub.post_team_message("club-1", "bob", "No BADWORD lines", timestamp_s=2.0)

        self.assertEqual(first.body, "Ready up")
        self.assertEqual(second.body, "No [filtered] lines")
        self.assertEqual([message.sender_id for message in self.hub.team_chat("club-1")], ["bob", "alice"])

    def test_rate_limit_blocks_spam_until_window_expires(self) -> None:
        self.hub.post_team_message("club-1", "alice", "one", timestamp_s=10.0)
        self.hub.post_team_message("club-1", "alice", "two", timestamp_s=12.0)

        with self.assertRaises(ValueError):
            self.hub.post_team_message("club-1", "alice", "three", timestamp_s=14.0)

        allowed = self.hub.post_team_message("club-1", "alice", "after window", timestamp_s=16.0)
        self.assertEqual(allowed.body, "after window")

    def test_event_scheduling_and_joining_requires_membership(self) -> None:
        event = self.hub.schedule_event("event-1", "club-1", "Sunday Cup", 100.0, "alice")
        joined = self.hub.join_event("event-1", "bob")

        self.assertEqual(event.participant_ids, ("alice",))
        self.assertEqual(joined.participant_ids, ("alice", "bob"))
        with self.assertRaises(ValueError):
            self.hub.join_event("event-1", "outsider")

    def test_message_reporting_and_resolution(self) -> None:
        message = self.hub.post_team_message("club-1", "bob", "rough line", timestamp_s=1.0)

        report = self.hub.report_message("report-1", message, "alice", "unsporting")
        self.assertEqual(report.status, "open")
        self.assertEqual(self.hub.snapshot().open_reports, (report,))

        resolved = self.hub.resolve_report("report-1", "reviewed")
        self.assertEqual(resolved.status, "reviewed")
        self.assertEqual(self.hub.snapshot().open_reports, ())

    def test_moderation_permissions_mute_and_ban_targets(self) -> None:
        with self.assertRaises(ValueError):
            self.hub.apply_moderation_action(
                ModerationAction("action-0", "club-1", "bob", "alice", "warn", "not allowed")
            )

        mute = self.hub.apply_moderation_action(
            ModerationAction("action-1", "club-1", "carol", "bob", "mute", "cooldown", duration_s=10.0),
            timestamp_s=20.0,
        )
        self.assertTrue(self.hub.is_muted("club-1", "bob", 25.0))
        self.assertEqual(mute.action, "mute")
        with self.assertRaises(ValueError):
            self.hub.post_team_message("club-1", "bob", "muted", timestamp_s=25.0)

        self.hub.apply_moderation_action(ModerationAction("action-2", "club-1", "alice", "bob", "ban", "spam"))
        self.assertTrue(self.hub.is_banned("club-1", "bob"))
        with self.assertRaises(ValueError):
            self.hub.post_team_message("club-1", "bob", "banned", timestamp_s=40.0)

    def test_moderation_appeals_and_audit_state(self) -> None:
        action = self.hub.apply_moderation_action(
            ModerationAction("action-1", "club-1", "carol", "bob", "mute", "cooldown", duration_s=30.0),
            timestamp_s=10.0,
        )

        appeal = self.hub.submit_appeal("appeal-1", action.action_id, "bob", "I understand the rule now")

        self.assertEqual(appeal.status, "open")
        self.assertEqual(self.hub.snapshot().open_appeals, (appeal,))
        self.assertIn("audit-action-action-1", {entry.audit_id for entry in self.hub.audit_snapshot()})
        self.assertIn("audit-appeal-appeal-1", {entry.audit_id for entry in self.hub.audit_snapshot()})
        with self.assertRaises(ValueError):
            self.hub.submit_appeal("appeal-2", action.action_id, "alice", "wrong target")
        with self.assertRaises(ValueError):
            self.hub.resolve_appeal("appeal-1", "bob", "approved", "not a moderator")

        resolved = self.hub.resolve_appeal("appeal-1", "alice", "approved", "mute lifted", timestamp_s=15.0)

        self.assertEqual(resolved.status, "approved")
        self.assertEqual(resolved.reviewer_id, "alice")
        self.assertFalse(self.hub.is_muted("club-1", "bob", 20.0))
        self.assertEqual(self.hub.snapshot().open_appeals, ())
        self.assertIn("audit-appeal-resolution-appeal-1", {entry.audit_id for entry in self.hub.audit_snapshot()})

    def test_snapshot_is_sorted_and_contains_public_moderation_state(self) -> None:
        self.hub.schedule_event("event-late", "club-1", "Late", 200.0, "alice")
        self.hub.schedule_event("event-early", "club-1", "Early", 100.0, "alice")
        message = self.hub.post_team_message("club-1", "bob", "flag this", timestamp_s=1.0)
        report = self.hub.report_message("report-1", message, "alice", "review")
        action = self.hub.apply_moderation_action(
            ModerationAction("action-1", "club-1", "carol", "bob", "warn", "tone")
        )

        snapshot = self.hub.snapshot()

        self.assertEqual([club.club_id for club in snapshot.clubs], ["club-1"])
        self.assertEqual([event.event_id for event in snapshot.scheduled_events], ["event-early", "event-late"])
        self.assertEqual(snapshot.open_reports, (report,))
        self.assertEqual(snapshot.moderation_actions, (action,))

    def test_community_hub_persists_clubs_chat_reports_and_moderation(self) -> None:
        self.hub.schedule_event("event-1", "club-1", "Sunday Cup", 100.0, "alice")
        self.hub.join_event("event-1", "bob")
        message = self.hub.post_team_message("club-1", "bob", "No BADWORD lines", timestamp_s=1.0)
        report = self.hub.report_message("report-1", message, "alice", "review")
        self.hub.resolve_report(report.report_id, "reviewed")
        self.hub.apply_moderation_action(
            ModerationAction("action-1", "club-1", "carol", "bob", "mute", "cooldown", duration_s=10.0),
            timestamp_s=20.0,
        )
        self.hub.apply_moderation_action(ModerationAction("action-2", "club-1", "alice", "bob", "ban", "spam"))
        self.hub.submit_appeal("appeal-1", "action-2", "bob", "false positive")
        self.hub.resolve_appeal("appeal-1", "carol", "denied", "ban stands", timestamp_s=30.0)
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)

            save_community_hub(project_root, self.hub)
            loaded = load_community_hub(project_root)

            self.assertTrue(community_hub_path(project_root).exists())
            self.assertEqual(loaded.snapshot(), self.hub.snapshot())
            self.assertEqual(loaded.chat_snapshot(), self.hub.chat_snapshot())
            self.assertEqual(loaded.reports_snapshot(), self.hub.reports_snapshot())
            self.assertEqual(loaded.appeals_snapshot(), self.hub.appeals_snapshot())
            self.assertEqual(loaded.audit_snapshot(), self.hub.audit_snapshot())
            self.assertEqual(loaded.banned_snapshot(), self.hub.banned_snapshot())
            self.assertEqual(loaded.muted_until_snapshot(), self.hub.muted_until_snapshot())
            self.assertTrue(loaded.is_banned("club-1", "bob"))
            self.assertTrue(loaded.is_muted("club-1", "bob", 25.0))

    def test_corrupt_community_hub_loads_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            path = community_hub_path(project_root)
            path.parent.mkdir(parents=True)
            path.write_text('{"clubs": [{"club_id": "", "name": "Broken", "tag": "BAD", "members": []}]}', encoding="utf-8")

            loaded = load_community_hub(project_root)

            self.assertEqual(loaded.snapshot().clubs, ())

    def test_invalid_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Club("club", "Name", "bad", (ClubMember("owner", "owner"),))
        with self.assertRaises(ValueError):
            Club("club", "Name", "GOOD", (ClubMember("a", "owner"), ClubMember("b", "owner")))
        with self.assertRaises(ValueError):
            RateLimitRule(max_messages=0)
        with self.assertRaises(ValueError):
            ModerationAction("action", "club", "mod", "target", "shadowban", "bad action")
        with self.assertRaises(ValueError):
            ModerationAppeal("appeal", "action", "club", "target", "reason", "unknown")


if __name__ == "__main__":
    unittest.main()
