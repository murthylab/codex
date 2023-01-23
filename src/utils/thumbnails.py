import requests

# 'cell_or_neuropil' is either a root id, or neuropil abbreviation (upper case, e.g. GNG)
def url_for_skeleton(cell_or_neuropil, animated=True):
    gif_folder = 'skeleton_gifs'
    jpg_folder = 'skeleton_thumbnails'

    def build_url(folder, file, ext):
        return f"https://storage.googleapis.com/flywire-data/codex/{folder}/{file}.{ext}"

    url = build_url(gif_folder, cell_or_neuropil, 'gif')
    r = requests.head(url)
    print(f"+++ {r.headers['Content-Type']}")

    return url if 'image' in r.headers['Content-Type'] else build_url(jpg_folder, cell_or_neuropil, 'png')

