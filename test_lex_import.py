import json
import tempfile
import unittest
from pathlib import Path

from lex_import import build_speaker_rules, parse_official_transcript, write_import


HTML = """
<span class="ts-name">Lex Fridman</span>
<span class="ts-timestamp"><a>(00:00:00)</a></span>
<span class="ts-text">Hello &amp; welcome.</span>
<span class="ts-name">Mark Zuckerberg</span>
<span class="ts-timestamp"><a>(00:00:05)</a></span>
<span class="ts-text">Thank you.</span>
<span class="ts-name"></span>
<span class="ts-timestamp"><a>(00:00:08)</a></span>
<span class="ts-text">Good to be here.</span>
"""

EPISODE = {
    "num": 398,
    "title": "#398 – Test",
    "date": "2023-09-28",
    "slug": "mark-zuckerberg-3",
    "ytId": "MVYrJJNdrEg",
    "lexUrl": "https://lexfridman.com/mark-zuckerberg-3/",
    "officialTranscript": "https://lexfridman.com/mark-zuckerberg-3-transcript/",
    "audioUrl": "https://example.com/398.mp3",
    "zhMetadata": {"zh": "#398 测试"},
}


class LexImportTests(unittest.TestCase):
    def test_parse_and_propagate_speaker(self):
        rows = parse_official_transcript(HTML)
        self.assertEqual(3, len(rows))
        self.assertEqual("Hello & welcome.", rows[0]["text"])
        self.assertEqual("Mark Zuckerberg", rows[2]["speaker"])
        self.assertEqual(5.0, rows[0]["end"])
        self.assertEqual("", rows[0]["text_zh"])

    def test_speaker_rules_merge_adjacent_rows(self):
        rules = build_speaker_rules(parse_official_transcript(HTML))
        self.assertEqual(2, len(rules))
        self.assertEqual(0.0, rules[0]["start"])
        self.assertEqual(5.0, rules[0]["end"])
        self.assertGreater(rules[1]["end"], 8.0)

    def test_write_import_records_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            metadata = write_import(
                episode=EPISODE,
                transcript_html=HTML,
                output_dir=output,
                upstream_commit="deadbeef",
                clip_end=6,
            )
            self.assertEqual(2, metadata["selectedSegmentCount"])
            self.assertEqual("deadbeef", metadata["upstreamCommit"])
            rows = json.loads((output / "source_segments.json").read_text())
            self.assertEqual(["Lex Fridman", "Mark Zuckerberg"], [r["speaker"] for r in rows])

    def test_rejects_non_monotonic_timestamps(self):
        bad = HTML.replace("(00:00:05)", "(00:00:09)")
        with self.assertRaisesRegex(ValueError, "timestamps must increase"):
            parse_official_transcript(bad)

    def test_splits_same_second_without_losing_source_time(self):
        same_second = HTML.replace("(00:00:05)", "(00:00:00)")
        rows = parse_official_transcript(same_second)
        self.assertEqual(0.0, rows[0]["source_start"])
        self.assertEqual(0.0, rows[1]["source_start"])
        self.assertGreater(rows[1]["start"], rows[0]["start"])
        self.assertEqual(rows[0]["end"], rows[1]["start"])


if __name__ == "__main__":
    unittest.main()
