from src.data.gcs_data_loader import load_nblast_scores_header, load_nblast_scores_for_root_id
from unittest import TestCase


class Test(TestCase):
    def test_nblast_loading(self):
        sample_root_ids = [
            720575940637509958,
            720575940631472083,
            720575940635547113,
            720575940640850829,
            720575940617611830,
            720575940637287743,
            720575940620300065,
            720575940639928461,
            720575940616824197,
            720575940615557460,
        ]
        header = load_nblast_scores_header()
        self.assertTrue(all([r in header for r in sample_root_ids]))
        for rid in sample_root_ids:
            scores = load_nblast_scores_for_root_id(root_id=rid)
            self.assertEqual(len(scores), len(header))
            for i, r in enumerate(header):
                self.assertEqual(r, scores[i][0])
                self.assertTrue(-1 < scores[i][1] < 1)

        # check that it doesn't explode with bogus rid
        scores = load_nblast_scores_for_root_id(root_id="deadbeef")
        self.assertIsNone(scores)
