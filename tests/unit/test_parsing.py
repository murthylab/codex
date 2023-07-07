from unittest import TestCase

from src.utils.parsing import tokenize, extract_links


class Test(TestCase):
    def test_tokenize(self):
        self.assertEqual(["1", "2", "3"], tokenize("'1', '2', '3'"))
        self.assertEqual(["hello", "world"], tokenize("hello world'"))
        self.assertEqual(["who's", "home"], tokenize("who's home?"))

    def test_links_extraction(self):
        self.assertEqual(
            {"https://doi.org/10.7554/elife.66039"},
            extract_links(": pfl1; name from doi: 10.7554/elife.66039"),
        )
        self.assertEqual(
            {"https://doi.org/10.7554/ELIFE.66039"},
            extract_links(": pfl1; name from DOI: 10.7554/ELIFE.66039"),
        )
        self.assertEqual(
            {"https://doi.org/10.7554/elife.66039"},
            extract_links(": pfl1; name from doi:10.7554/elife.66039"),
        )
        self.assertEqual(
            {"https://doi.org/10.7554/elife.66039"},
            extract_links(": pfl1; name from doi.org/10.7554/elife.66039"),
        )
        self.assertEqual(
            {"https://doi.org/10.7554/elife.66039"},
            extract_links(": pfl1; name from https://doi.org/10.7554/elife.66039"),
        )

        self.assertEqual(
            {"http://flybase.org/reports/FBbt:01234567"},
            extract_links(" FBbt:01234567"),
        )
        self.assertEqual(
            {"http://flybase.org/reports/FBbt:01234567"},
            extract_links(" FBbt 01234567"),
        )
        self.assertEqual(
            {"http://flybase.org/reports/FBbt:01234567"},
            extract_links(" FBbt_01234567"),
        )
        self.assertEqual(
            {"http://flybase.org/reports/FBbt:01234567"}, extract_links(" FBbt01234567")
        )

        self.assertEqual(
            {"http://flybase.org/reports/FBbt:00003779"},
            extract_links(
                "Medullary intrinsic neuron 4, Mi4, Mi4, [FBbt_00003779] (Fischbach and Dittrich, 1989)"
            ),
        )

        self.assertEqual(
            {"http://flybase.org/reports/FBbt:00047636"},
            extract_links(
                "DNp03_R, descending neuron of the posterior brain, DNp03, FBbt_00047636"
            ),
        )

        self.assertEqual(
            {"http://cnn.com"}, extract_links("http://cnn.com invalid.com")
        )
        self.assertEqual(
            {"http://cnn.com", "http://flybase.org/reports/FBbt:01234567"},
            extract_links("http://cnn.com FBbt:01234567"),
        )
        self.assertEqual(
            {"http://cnn.com", "https://cnn.com"},
            extract_links("http://cnn.com https://cnn.com https://cnn.com"),
        )
