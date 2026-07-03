import unittest
from pathlib import Path

from horse_racing_game.audio.playback_codecs import (
    channel_playback_supported,
    codec_usage_report,
    compression_recommendation,
    format_info,
    should_stream_path,
    stream_playback_supported,
)
from horse_racing_game.audio.sound_catalog import SoundAsset, SoundCatalog


def _asset(sound_id: str, path: str, category: str = "horse", loop: bool = False) -> SoundAsset:
    return SoundAsset(sound_id, Path(path), "test", "test", category, loop, 0.5, 40)


class PlaybackCodecsTests(unittest.TestCase):
    def test_channel_formats_include_ogg_opus_mp3_wav_and_flac(self) -> None:
        for path in ("sfx/click.ogg", "loops/gallop.opus", "sfx/jump.mp3", "sfx/hit.wav", "sfx/bell.flac"):
            with self.subTest(path=path):
                self.assertTrue(channel_playback_supported(path))

    def test_stream_formats_include_channels_and_tracker_modules(self) -> None:
        for path in ("music/race.ogg", "music/race.opus", "music/theme.mp3", "music/theme.mod", "music/theme.xm"):
            with self.subTest(path=path):
                self.assertTrue(stream_playback_supported(path))
        self.assertTrue(should_stream_path("music/theme.s3m"))

    def test_unknown_format_is_reported_as_unsupported(self) -> None:
        info = format_info("audio/raw.aac")

        self.assertEqual(info.extension, ".aac")
        self.assertEqual(info.family, "unknown")
        self.assertFalse(info.channel_supported)
        self.assertFalse(info.stream_supported)

    def test_compression_recommendations_prefer_opus_music_and_ogg_loops(self) -> None:
        self.assertEqual(compression_recommendation(_asset("music", "music/race.mp3", "music", True)), ".opus")
        self.assertEqual(compression_recommendation(_asset("wind", "loops/wind.wav", "wind", True)), ".ogg")
        self.assertEqual(compression_recommendation(_asset("ui", "sfx/click.wav", "ui", False)), ".wav")

    def test_codec_usage_report_summarizes_manifest_risk(self) -> None:
        catalog = SoundCatalog(
            (
                _asset("click", "sfx/click.ogg", "ui"),
                _asset("race_music", "music/race.opus", "music", True),
                _asset("legacy", "music/legacy.mod", "music", True),
                _asset("unsupported", "sfx/raw.aac", "ui"),
            )
        )

        report = codec_usage_report(catalog)

        self.assertEqual(report.total_assets, 4)
        self.assertEqual(report.by_extension[".ogg"], 1)
        self.assertEqual(report.unsupported_channel_assets, ("legacy", "unsupported"))
        self.assertEqual(report.stream_preferred_assets, ("race_music", "legacy"))


if __name__ == "__main__":
    unittest.main()
