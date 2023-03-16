_GOOGLE_ID_KEY = "id_info"
_FLYWIRE_DATA_ACCESS_KEY = "data_access_payload"
_FLYWIRE_TOKEN_KEY = "data_access_token"


def _fetch(storage, group, item, required):
    if required:
        return storage[group][item]
    try:
        return storage.get(group, {}).get(item)
    except Exception:
        return None


"""
Goolge
"""


def store_user_info(storage, id_info):
    storage[_GOOGLE_ID_KEY] = id_info


def is_user_authenticated(storage):
    return _GOOGLE_ID_KEY in storage


def fetch_user_name(storage, default_to=None):
    return _fetch(storage, _GOOGLE_ID_KEY, "name", required=False) or default_to


def fetch_user_email(storage, default_to=None):
    return _fetch(storage, _GOOGLE_ID_KEY, "email", required=False) or default_to


def fetch_user_picture(storage):
    return _fetch(storage, _GOOGLE_ID_KEY, "picture", required=False)


"""
FlyWire
"""


def store_flywire_data_access(storage, access_token, access_payload):
    storage[_FLYWIRE_TOKEN_KEY] = access_token
    storage[_FLYWIRE_DATA_ACCESS_KEY] = access_payload


def fetch_flywire_token(storage):
    return storage[_FLYWIRE_TOKEN_KEY]


def fetch_flywire_user_id(storage, required=False):
    return _fetch(storage, _FLYWIRE_DATA_ACCESS_KEY, "id", required)


def fetch_flywire_user_affiliation(storage):
    return _fetch(storage, _FLYWIRE_DATA_ACCESS_KEY, "pi", required=False) or _fetch(
        storage, _FLYWIRE_DATA_ACCESS_KEY, "affiliations", required=False
    )


def is_granted_data_access(storage):
    return _FLYWIRE_TOKEN_KEY in storage


def is_flywire_lab_member(storage):
    affiliation = fetch_flywire_user_affiliation(storage)
    if not affiliation:
        return False
    return any([pi in affiliation for pi in ["Mala Murthy", "Sebastian Seung"]])


"""
Clear / sign out
"""


def delete_cookies(storage):
    for k in [_GOOGLE_ID_KEY, _FLYWIRE_DATA_ACCESS_KEY, _FLYWIRE_TOKEN_KEY]:
        if k in storage:
            del storage[k]
