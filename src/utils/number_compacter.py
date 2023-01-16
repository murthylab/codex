import string

CHARS = string.digits + string.ascii_uppercase + string.ascii_lowercase
CHARSLEN = len(CHARS)


def number_to_compact_repr(num):
    if num < 0:
        return f"-{number_to_compact_repr(-num)}"
    assert isinstance(num, int)
    s = ""
    while num:
        s = CHARS[num % CHARSLEN] + s
        num //= CHARSLEN
    return s or CHARS[0]


def compact_repr_to_number(reprStr):
    if reprStr.startswith("-"):
        return -compact_repr_to_number(reprStr[1:])
    assert isinstance(reprStr, str) and all(c in CHARS for c in reprStr)
    num = 0
    for i, c in enumerate(reversed(reprStr)):
        num += CHARS.index(c) * (CHARSLEN**i)
    return num
