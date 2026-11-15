"""Playback regressions; audio hardware is mocked so CI remains offline."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import narration


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.wav = Path(self.tmp.name) / "sample.wav"
        # A nonempty preview WAV is enough for the backend launch test.
        import wave
        with wave.open(str(self.wav), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(24000)
            out.writeframes(b"\x00\x00" * 2400)

    def test_missing_audio_is_explained(self):
        player = narration.AudioPlayer()
        with self.assertRaisesRegex(narration.PlaybackError, "Audio file not found"):
            player.play(Path(self.tmp.name) / "missing.wav")

    def test_ffplay_starts_without_shell_and_stops(self):
        player = narration.AudioPlayer()
        process = MagicMock()
        process.poll.return_value = None
        process.stderr = MagicMock()
        with patch.object(narration, "find_ffplay", return_value="/mock/ffplay"), \
             patch.object(narration.subprocess, "Popen", return_value=process) as popen, \
             patch.object(narration.time, "sleep", return_value=None):
            self.assertEqual(player.play(self.wav), "FFplay")
            command = popen.call_args.args[0]
            self.assertEqual(command[0], "/mock/ffplay")
            self.assertIn("-nodisp", command)
            self.assertEqual(command[-1], str(self.wav))
            self.assertEqual(player.current_file, self.wav)
            player.stop()
        process.terminate.assert_called_once()
        self.assertIsNone(player.current_file)

    def test_windows_native_wav_fallback(self):
        import sys
        fake_winsound = MagicMock()
        fake_winsound.SND_FILENAME = 0x20000
        fake_winsound.SND_ASYNC = 1
        fake_winsound.SND_NODEFAULT = 2
        with patch.object(narration, "find_ffplay", return_value=None), \
             patch.object(narration.sys, "platform", "win32"), \
             patch.dict(sys.modules, {"winsound": fake_winsound}):
            player = narration.AudioPlayer()
            self.assertEqual(player.play(self.wav), "Windows WAV")
            player.stop()
            self.assertEqual(fake_winsound.PlaySound.call_count, 2)

    def test_empty_audio_has_actionable_error(self):
        tiny = Path(self.tmp.name) / "tiny.wav"
        tiny.write_bytes(b"123")
        with self.assertRaisesRegex(narration.PlaybackError, "empty or incomplete"):
            narration.AudioPlayer().play(tiny)


if __name__ == "__main__":
    unittest.main()
