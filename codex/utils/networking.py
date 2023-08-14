import os

import requests


from codex import logger


def download(url: str, dest_folder: str):
    logger.debug(f"Downloading {url} to {os.path.abspath(dest_folder)}")
    if not os.path.exists(dest_folder):
        logger.debug(f"Creating folder: {dest_folder}")
        os.makedirs(dest_folder)

    filename = url.split("/")[-1].replace(" ", "_")
    file_path = os.path.join(dest_folder, filename)

    r = requests.get(url, stream=True)
    if r.ok:
        logger.debug(f"Saving to {os.path.abspath(file_path)}")
        with open(file_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 8):
                if chunk:
                    f.write(chunk)
                    f.flush()
                    os.fsync(f.fileno())
        return True
    else:
        logger.warning(
            "Download failed: status code {}\n{}".format(r.status_code, r.text)
        )
        return False
