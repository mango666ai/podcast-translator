import tempfile
import unittest
from pathlib import Path

from embed_episode_covers import formal_episodes, update_enclosure_length


class EmbedEpisodeCoversTests(unittest.TestCase):
    def test_feed_selection_and_length_update(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "episodes").mkdir()
            (root / "episodes" / "sample.mp3").write_bytes(b"audio")
            feed = root / "feed.xml"
            url = "https://example.com/episodes/sample.mp3"
            feed.write_text(
                f'''<?xml version="1.0"?><rss><channel><item>
<guid>https://example.com/ep/abc123</guid>
<enclosure url="{url}" length="5" type="audio/mpeg" />
</item></channel></rss>''',
                encoding="utf-8",
            )
            episodes = formal_episodes(feed)
            self.assertEqual(root / "episodes" / "sample.mp3", episodes["abc123"][0])
            update_enclosure_length(feed, url, 1234)
            self.assertIn('length="1234"', feed.read_text())

    def test_missing_episode_file_is_an_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "episodes").mkdir()
            feed = root / "feed.xml"
            feed.write_text(
                '''<?xml version="1.0"?><rss><channel><item>
<guid>https://example.com/ep/abc123</guid>
<enclosure url="https://example.com/episodes/missing.mp3" length="5" type="audio/mpeg" />
</item></channel></rss>''',
                encoding="utf-8",
            )
            with self.assertRaises(FileNotFoundError):
                formal_episodes(feed)


if __name__ == "__main__":
    unittest.main()
