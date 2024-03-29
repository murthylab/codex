NEURO_TRANSMITTER_NAMES = {
    "DA": "dopamine",
    "SER": "serotonin",
    "GABA": "gabaergic",
    "GLUT": "glutamate",
    "ACH": "acetylcholine",
    "OCT": "octopamine",
}


def lookup_nt_type(txt):
    if txt:
        if txt.upper() in NEURO_TRANSMITTER_NAMES:
            return txt.upper()
        txt_low = txt.lower()
        for k, v in NEURO_TRANSMITTER_NAMES.items():
            if v.startswith(txt_low):
                return k
    return txt


def lookup_nt_type_name(txt):
    nt_type = lookup_nt_type(txt)
    return NEURO_TRANSMITTER_NAMES.get(nt_type, "unknown NT type")
