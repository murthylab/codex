from unittest import TestCase
from src.faq_qa_kb import FAQ_QA_KB

class FaqQaKbTest(TestCase):

    def test_faq_list(self):
        self.assertGreater(len(FAQ_QA_KB), 0)
        for qa in FAQ_QA_KB.values():
            self.assertGreater(len(qa['q']), 10)
            self.assertGreater(len(qa['a']), 10)
