def url_for_skeleton(root_id, data_version):
    try:  # thumbnails are only available for 447 and on. try to fallback for older versions (some rids might match)
        if int(data_version) < 447:
            data_version = "447"
    except ValueError:
        pass
    return f"https://storage.googleapis.com/flywire-data/{data_version}/skeleton_thumbnails/{root_id}.png"
