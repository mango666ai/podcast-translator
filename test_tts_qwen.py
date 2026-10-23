import unittest
from pathlib import Path

import tts_qwen


class QwenTTSTests(unittest.TestCase):
    def test_rejects_unreviewed_voice(self):
        with self.assertRaisesRegex(ValueError, "只允许"):
            tts_qwen.synthesize("测试", Path("unused.mp3"), voice="unknown")

    def test_rejects_blank_text_before_api_call(self):
        with self.assertRaisesRegex(ValueError, "文本为空"):
            tts_qwen.synthesize("   ", Path("unused.mp3"), voice="longanlufeng")

    def test_official_voices_are_distinct(self):
        self.assertEqual({"longanlufeng", "longanlingxin"}, set(tts_qwen.SYSTEM_VOICES))


if __name__ == "__main__":
    unittest.main()
