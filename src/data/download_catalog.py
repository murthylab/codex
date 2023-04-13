import json
from collections import namedtuple

from src.configuration import (
    DOWNLOADABLE_FILES_METADATA_FILE,
    DOWNLOADABLE_PRODUCT_TITLES_AND_DESCRIPTIONS,
    DOWNLOADABLE_FILE_EXTENSION,
    DOWNLOADABLE_FILE_FORMAT,
)

"""
This is pre-computed metadata from all downloadable assets. To regenerate upon change, run:
python3 -m src.etl.update_download_catalog
"""
with open(DOWNLOADABLE_FILES_METADATA_FILE) as f:
    DOWNLOADABLE_FILES_METADATA = json.load(f)
    DOWNLOADABLE_FILE_SIZES = DOWNLOADABLE_FILES_METADATA["file_sizes"]
    DOWNLOADABLE_FILE_CONTENTS = DOWNLOADABLE_FILES_METADATA["file_contents"]

DownloadableProduct = namedtuple(
    "Product", "description file_name file_format file_size file_content"
)

DOWNLOAD_CATALOG = {}
for version, assets in DOWNLOADABLE_FILE_CONTENTS.items():
    DOWNLOAD_CATALOG[version] = {}
    for fname, content in assets.items():
        product = fname.replace(DOWNLOADABLE_FILE_EXTENSION, "")
        DOWNLOAD_CATALOG[version][product] = DownloadableProduct(
            description=DOWNLOADABLE_PRODUCT_TITLES_AND_DESCRIPTIONS[product],
            file_name=fname,
            file_format=DOWNLOADABLE_FILE_FORMAT,
            file_size=DOWNLOADABLE_FILE_SIZES[version][fname],
            file_content=content,
        )
