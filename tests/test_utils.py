import re

from automail.utils import parse


def test_normalize():
    assert parse.normalize("[X:21] CR/12/14") == "x 21 cr 12 14"


def test_consume_re():
    assert parse.consume_re(re.compile('(42)'), "ab42123") == ("42", "ab123")
