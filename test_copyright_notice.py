import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from backfill_copyright_notice import update_feed, update_feed_text
from notes_to_description import COPYRIGHT_NOTICE, append_copyright_notice, notes_md_to_description


class CopyrightNoticeTests(unittest.TestCase):
    def test_append_is_idempotent(self):
        once = append_copyright_notice("节目介绍")
        self.assertEqual(once, append_copyright_notice(once))
        self.assertEqual(1, once.count(COPYRIGHT_NOTICE))

    def test_notes_include_notice(self):
        result = notes_md_to_description("# title\n\n## 来源\n原节目")
        self.assertTrue(result.endswith(COPYRIGHT_NOTICE))

    def test_backfill_only_updates_items(self):
        feed = """<?xml version="1.0"?><rss><channel>
<description>频道介绍</description>
<item><title>A &amp; B</title><description>第一集 &amp; 说明</description></item>
</channel></rss>"""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "feed.xml"
            path.write_text(feed, encoding="utf-8")
            changed, total = update_feed(path)
            self.assertEqual((1, 1), (changed, total))
            root = ET.parse(path).getroot()
            self.assertEqual("频道介绍", root.find("channel").findtext("description"))
            description = root.find("channel").find("item").findtext("description")
            self.assertIn("第一集 & 说明", description)
            self.assertEqual(1, description.count(COPYRIGHT_NOTICE))
            changed_again, _ = update_feed(path)
            self.assertEqual(0, changed_again)


if __name__ == "__main__":
    unittest.main()
