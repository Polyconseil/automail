from automail.utils import parse


def test_variants():
    assert list(parse.variants('Test', ' test', 'TéßT  ')) == ['test', 'test', 'tesst']


def test_re_variants():
    assert parse.re_variants("Please", 'match|(this)') == r"Please|match\|\(this\)"
