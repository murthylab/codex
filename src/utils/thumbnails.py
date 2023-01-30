# 'cell_or_neuropil' is either a root id, or neuropil abbreviation (upper case, e.g. GNG)
def url_for_skeleton(cell_or_neuropil, animated=False):
    gif_folder = "skeleton_thumbnail_gifs"
    png_folder = "skeleton_thumbnails"

    def build_url(folder, file, ext):
        return (
            f"https://storage.googleapis.com/flywire-data/codex/{folder}/{file}.{ext}"
        )

    return build_url(
        gif_folder if animated else png_folder,
        cell_or_neuropil,
        "gif" if animated else "png",
    )
