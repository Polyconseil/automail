""" Various parsing utilities
"""
import re
import unidecode


def variants(*strings):
    """Given input strings, returns a generator yielding unidecoded lower versions of them
    """
    for string in strings:
        if not string:
            continue
        yield unidecode.unidecode(string.lower()).strip()


def re_variants(*strings):
    """Given input strings, returns a regular expression matching any of them with correct escaping
    """
    return '|'.join(
        re.escape(string)
        for string in strings if string
        )
