SKELETON_FOLDERS = {
    "gif": "skeleton_thumbnail_gifs",
    "png": "skeleton_thumbnails",
    "swc": "skeleton_swcs",
}

# 'cell_or_neuropil' is either a root id, or neuropil abbreviation (upper case, e.g. GNG)
def url_for_skeleton(cell_or_neuropil, file_type="png"):
    def build_url(folder, file, ext):
        return (
            f"https://storage.googleapis.com/flywire-data/codex/{folder}/{file}.{ext}"
        )

    return build_url(
        SKELETON_FOLDERS[file_type],
        cell_or_neuropil,
        file_type,
    )
