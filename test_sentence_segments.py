import unittest

from sentence_segments import mid_sentence_count, regroup_sentences


class RegroupTest(unittest.TestCase):
    def test_moves_cut_to_sentence_end(self):
        segs = [
            {"start": 0, "end": 5, "text": "This is the first sentence. And this one is"},
            {"start": 5, "end": 9, "text": "cut in half by captions. Done."},
        ]
        out = regroup_sentences(segs, soft_chars=20, max_chars=200)
        self.assertEqual(mid_sentence_count(out), 0)
        self.assertEqual(" ".join(s["text"] for s in out), " ".join(s["text"] for s in segs))

    def test_speaker_change_always_splits(self):
        segs = [{"start": 0, "end": 4, "text": "So what is Paper? >> Paper is a design tool."}]
        out = regroup_sentences(segs, soft_chars=500, max_chars=600)
        self.assertEqual([s["text"] for s in out], ["So what is Paper?", ">> Paper is a design tool."])

    def test_lowercase_after_period_is_not_end(self):
        segs = [{"start": 0, "end": 4, "text": "We moved to the U.S. and started over."}]
        out = regroup_sentences(segs, soft_chars=10, max_chars=600)
        self.assertEqual(len(out), 1)

    def test_long_sentence_respects_max(self):
        segs = [{"start": 0, "end": 30, "text": ("word, " * 120).strip()}]
        out = regroup_sentences(segs, soft_chars=150, max_chars=260)
        self.assertTrue(all(len(s["text"]) <= 260 for s in out))


if __name__ == "__main__":
    unittest.main()
