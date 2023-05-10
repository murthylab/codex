DELIMS = [
    "=",
    "-",
    ",",
    "?",
    "!",
    ";",
    ":",
    "//",
    "/",
    "(",
    ")",
    "[",
    "]",
    '"',
    "&",
    "' ",
    " '",
    ". ",
]
HIGHLIGHTING_DELIMS = [
    "=",
    "-",
    ".",
    ",",
    "?",
    "!",
    ";",
    ":",
    "//",
    "/",
    "(",
    ")",
    "[",
    "]",
    '"',
    "&",
    "*",
]


def tokenize(s):
    for d in DELIMS:
        s = s.replace(d, " ")

    def clean(tk):
        if any([tk.endswith(c) for c in [".", "'"]]):
            tk = tk[:-1]
        if any([tk.startswith(c) for c in [".", "'"]]):
            tk = tk[1:]
        return tk

    res = [clean(t) for t in s.split() if t]
    return [t for t in res if t]


def tokenize_and_fold_for_highlight(s):
    tokens = []

    for d in HIGHLIGHTING_DELIMS:
        s = s.replace(d, " ")

    i = 0
    length = len(s)
    while i < length:
        c = s[i]
        if c == " ":
            i += 1
            continue
        start = i
        while i < length and s[i] != " ":
            i += 1
        end = i
        token = s[start:end].lower()
        if token:
            tokens.append((token, start, end))

    return tokens
