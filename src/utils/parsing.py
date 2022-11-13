DELIMS = ["=", "-", ". ", ",", "?", "!", ";", ":" "//", "/", "(", ")", '"', "&"]


def tokenize(s):
    for d in DELIMS:
        s = s.replace(d, " ")

    def clean(tk):
        if any([tk.endswith(c) for c in [".", ":"]]):
            tk = tk[:-1]
        return tk

    res = [clean(t) for t in s.split() if t]
    return [t for t in res if t]

