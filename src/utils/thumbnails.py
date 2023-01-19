# 'cell_or_neuropil' is either a root id, or neuropil abbreviation (upper case, e.g. GNG)
def url_for_skeleton(cell_or_neuropil, data_version):
    return f"https://storage.googleapis.com/flywire-data/codex/data/{data_version}/skeleton_thumbnails/{cell_or_neuropil}.png"
