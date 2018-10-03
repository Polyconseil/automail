""" Various parsing utilities
"""
import re
import unidecode


def normalize(string):
    string = unidecode.unidecode(string.lower()).strip()
    string = re.sub(r"[\[\]\(,;:.\|/\\]+", r" ", string)
    string = re.sub(r"([^\s]+)[\s]+", r"\1 ", string)
    return " ".join(s for s in string.split(" ") if s)


def consume_re(regex, string):
    match = regex.search(string)
    if match:
        span = match.span()
        return match.groups()[-1].strip(), string[: span[0]] + string[span[1] :]
    return None, string
