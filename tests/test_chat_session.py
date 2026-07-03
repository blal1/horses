import unittest
import tempfile
from pathlib import Path

from horse_racing_game.app.chat import (
    ChatMessage,
    ChatModerationPolicy,
    ChatSession,
    chat_session_path,
    load_chat_session,
    save_chat_session,
)


class ChatSessionTests(unittest.TestCase):
    def test_text_message_is_composed_and_recorded(self) -> None:
        chat = ChatSession(("host", "guest"))
        chat.append_text("Good luck")
        message = chat.submit_text()

        self.assertEqual(message.sender_id, "host")
        self.assertEqual(message.body, "Good luck")
        self.assertEqual(chat.messages[0], message)

    def test_voice_message_uses_current_macro_and_sender(self) -> None:
        chat = ChatSession(("host", "guest"))
        chat.cycle_sender(1)
        chat.cycle_voice_macro(3)

        message = chat.submit_voice()

        self.assertEqual(message.sender_id, "guest")
        self.assertEqual(message.kind, "voice")
        self.assertTrue(message.body)
        self.assertEqual(chat.messages[0], message)

    def test_composer_rejects_empty_messages(self) -> None:
        with self.assertRaises(ValueError):
            ChatMessage("", "Host", "hello")
        with self.assertRaises(ValueError):
            ChatMessage("host", "", "hello")
        with self.assertRaises(ValueError):
            ChatMessage("host", "Host", " ")
        with self.assertRaises(ValueError):
            ChatMessage("host", "Host", "hello", recipient_id="")

    def test_private_messages_are_visible_only_to_sender_and_recipient(self) -> None:
        chat = ChatSession(("host", "guest", "spectator"))
        chat.append_text("Private line")
        message = chat.submit_text(recipient_id="guest")

        self.assertTrue(message.is_private)
        self.assertEqual([item.body for item in chat.visible_messages("host")], ["Private line"])
        self.assertEqual([item.body for item in chat.visible_messages("guest")], ["Private line"])
        self.assertEqual(chat.visible_messages("spectator"), ())

    def test_mute_hides_messages_for_one_viewer_only(self) -> None:
        chat = ChatSession(("host", "guest"))
        chat.mute("host", "guest")
        chat.cycle_sender(1)
        chat.append_text("Can you hear me?")
        chat.submit_text()

        self.assertEqual(chat.visible_messages("host"), ())
        self.assertEqual(len(chat.visible_messages("guest")), 1)

    def test_block_rejects_private_messages_to_blocker(self) -> None:
        chat = ChatSession(("host", "guest"))
        chat.block("host", "guest")
        chat.cycle_sender(1)
        chat.append_text("Blocked whisper")

        with self.assertRaises(ValueError):
            chat.submit_text(recipient_id="host")

    def test_moderation_filters_text_and_tts_lines_are_accessible(self) -> None:
        chat = ChatSession(("host", "guest"), moderation=ChatModerationPolicy(("badword",)))
        chat.append_text("That BADWORD move")
        message = chat.submit_text()

        self.assertEqual(message.body, "That [filtered] move")
        self.assertEqual(chat.tts_lines("guest"), ("Host: That [filtered] move",))

    def test_private_voice_tts_includes_private_prefix(self) -> None:
        chat = ChatSession(("host", "guest"))
        message = chat.submit_voice(recipient_id="guest")

        self.assertTrue(message.tts_text().startswith("Private Host voice line:"))

    def test_chat_session_persists_messages_filters_mutes_and_blocks(self) -> None:
        chat = ChatSession(("host", "guest", "spectator"), moderation=ChatModerationPolicy(("badword",)))
        chat.append_text("Public BADWORD line")
        chat.submit_text(timestamp_s=1.0)
        chat.cycle_sender(1)
        chat.cycle_voice_macro(3)
        chat.submit_voice(timestamp_s=2.0, recipient_id="host")
        chat.mute("spectator", "guest")
        chat.block("host", "guest")
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)

            save_chat_session(project_root, chat)
            loaded = load_chat_session(project_root)

            self.assertTrue(chat_session_path(project_root).exists())
            self.assertEqual(loaded.messages, chat.messages)
            self.assertEqual(loaded.muted_snapshot(), chat.muted_snapshot())
            self.assertEqual(loaded.blocked_snapshot(), chat.blocked_snapshot())
            self.assertEqual(loaded.moderation, chat.moderation)
            self.assertEqual(loaded.visible_messages("spectator")[0].body, "Public [filtered] line")
            self.assertEqual(loaded.tts_lines("host")[0], "Private Guest voice line: Push now.")

    def test_corrupt_chat_session_loads_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            path = chat_session_path(project_root)
            path.parent.mkdir(parents=True)
            path.write_text('{"messages": [{"sender_id": "", "sender_label": "Host", "body": "broken"}]}', encoding="utf-8")

            loaded = load_chat_session(project_root)

            self.assertEqual(loaded.messages, ())
            self.assertEqual(loaded.composer.sender_id, "host")


if __name__ == "__main__":
    unittest.main()
