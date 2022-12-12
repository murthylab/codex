import datetime

from src.data.gcs_data_loader import *
from unittest import TestCase


class Test(TestCase):
    def test_nblast_scores_loading_perf(self):
        sample_root_ids = [
            720575940618089886,
            720575940631937055,
            720575940617874085,
            720575940623717159,
            720575940611733288,
            720575940621390761,
            720575940621199273,
            720575940609942062,
            720575940613357743,
            720575940620510640,
            720575940613068595,
            720575940634614196,
            720575940618027318,
            720575940618199094,
            720575940631345465,
            720575940622727612,
            720575940638670397,
            720575940608494531,
            720575940642354120,
            720575940626909768,
            720575940627547210,
            720575940637941070,
            720575940628028239,
            720575940630395855,
            720575940630579795,
            720575940616313684,
            720575940619297877,
            720575940621056982,
            720575940618987861,
            720575940620579542,
            720575940625199193,
            720575940625950553,
            720575940629489372,
            720575940634319967,
            720575940631774433,
            720575940609778018,
            720575940624409444,
            720575940623949668,
            720575940618680304,
            720575940637803379,
            720575940637326963,
            720575940640463093,
            720575940619914740,
            720575940619925620,
            720575940639031680,
            720575940659476865,
            720575940624721666,
            720575940624992258,
            720575940633715960,
            720575940624813701,
            720575940619642629,
            720575940618988678,
            720575940622450056,
            720575940613587454,
            720575940628210938,
            720575940607648267,
            720575940625008272,
            720575940622907795,
            720575940614178198,
            720575940613024150,
            720575940612899990,
            720575940610077849,
            720575940610271129,
            720575940610913177,
            720575940625038488,
            720575940624016933,
            720575940626228136,
            720575940612423208,
            720575940619868075,
            720575940628635180,
            720575940612071731,
            720575940615320505,
            720575940614126523,
            720575940614281147,
            720575940643062728,
            720575940633378296,
            720575940607126485,
            720575940620871894,
            720575940616102998,
            720575940610985434,
            720575940647784569,
            720575940613251178,
            720575940639441141,
            720575940635077112,
            720575940647413369,
            720575940627777018,
            720575940612975358,
            720575940621222527,
            720575940620767487,
            720575940625672706,
            720575940608665283,
            720575940604019134,
            720575940608028740,
            720575940627739142,
            720575940627239174,
            720575940608356035,
            720575940643039688,
            720575940622227213,
            720575940616002900,
            720575940611503322,
            720575940611090650,
            720575940616392797,
            720575940622003677,
            720575940614781599,
            720575940610279010,
            720575940611302883,
            720575940612411619,
            720575940617109222,
            720575940637450729,
            720575940630098284,
            720575940604024497,
            720575940615426610,
            720575940615302962,
            720575940629025591,
            720575940622865084,
            720575940604191678,
        ]

        # time parallel loading
        start_time = datetime.datetime.now()
        pscores = load_nblast_scores_for_root_ids(sample_root_ids, pool_size=8)
        self.assertEqual(len(sample_root_ids), len(pscores))
        for scores in pscores.values():
            self.assertEqual(49231, len(scores))
        self.assertLess((datetime.datetime.now() - start_time).total_seconds(), 7)
