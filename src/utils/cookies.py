# Goolge AUTH


def store_user_info(storage, id_info):
    storage["id_info"] = id_info


def is_user_authenticated(storage):
    return "id_info" in storage


def fetch_user_name(storage, default_to=None):
    try:
        return storage["id_info"]["name"]
    except Exception:
        return default_to


def fetch_user_email(storage, default_to=None):
    try:
        return storage["id_info"]["email"]
    except Exception:
        return default_to


def fetch_user_picture(storage):
    try:
        return storage["id_info"]["picture"]
    except Exception:
        return None


# FlyWire ACLs


def store_flywire_data_access(storage, access_token, access_payload):
    storage["data_access_token"] = access_token
    storage["data_access_payload"] = access_payload


def fetch_flywire_token(storage):
    return storage["data_access_token"]


def fetch_flywire_user_id(storage):
    return storage["data_access_payload"]["id"]


def is_granted_data_access(storage):
    return "data_access_token" in storage


# Cleanup for all


def delete_cookies(storage):
    for k in ["id_info", "data_access_payload", "data_access_token"]:
        if k in storage:
            del storage[k]
