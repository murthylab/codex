from unittest import TestCase
from src.blueprints.base import _extract_access_token


class TestBase(TestCase):
    def test_extract_access_token(self):
        self.assertEqual('aaa333555ccc666999ccc222fffggg89', _extract_access_token(
            "aaa333555ccc666999ccc222fffggg89"))
        self.assertEqual('aaa333555ccc666999ccc222fffggg89', _extract_access_token(
            '"aaa333555ccc666999ccc222fffggg89"'))
        self.assertEqual('aaa333555ccc666999ccc222fffggg89', _extract_access_token(
            "'aaa333555ccc666999ccc222fffggg89'"))

        self.assertEqual('aaa333555ccc666999ccc222fffggg89', _extract_access_token(
            '[{"id":99,"token":"aaa333555ccc666999ccc222fffggg89","user_id":1162}]'))
        self.assertEqual('aaa333555ccc666999ccc222fffggg89', _extract_access_token(
            "[{'id':99,'token':'aaa333555ccc666999ccc222fffggg89','user_id':1162}]"))

        self.assertEqual('', _extract_access_token(''))
        self.assertEqual('[]', _extract_access_token('[]'))
