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
    s = str(s)
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


def edit_distance(s1, s2):
    if len(s1) > len(s2):
        s1, s2 = s2, s1

    distances = range(len(s1) + 1)
    for i2, c2 in enumerate(s2):
        distances_ = [i2 + 1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                distances_.append(distances[i1])
            else:
                distances_.append(
                    1 + min((distances[i1], distances[i1 + 1], distances_[-1]))
                )
        distances = distances_
    return distances[-1]
