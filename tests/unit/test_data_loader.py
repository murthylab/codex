from src.data.gcs_data_loader import *
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

    def test_connection_table_loading(self):
        # check that it doesn't explode with bogus rid
        ct = load_connection_table_for_root_ids(root_ids=["deadbeef"])
        self.assertEqual([], ct)

        sample_root_ids = [
            720575940637948288,
            720575940639420800,
            720575940626367625,
            720575940625107352,
        ]

        # check individual loading (one root_id at a time)
        all_individual_connections = []
        for rid in sample_root_ids:
            ct = load_connection_table_for_root_ids([rid])
            self.assertGreater(len(ct), 1)
            for r in ct:
                self.assertTrue(rid == r[0] or rid == r[1])
            all_individual_connections += ct

        # check parallel loading
        parallel_connections = load_connection_table_for_root_ids(sample_root_ids)
        # check that the set of connections equals to individual loading
        self.assertEqual(
            set(tuple(i) for i in parallel_connections),
            set(tuple(i) for i in all_individual_connections),
        )
