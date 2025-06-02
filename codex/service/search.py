import math

DEFAULT_PAGE_SIZE = 10
PAGE_SIZE_OPTIONS = [
    1 * DEFAULT_PAGE_SIZE,
    2 * DEFAULT_PAGE_SIZE,
    5 * DEFAULT_PAGE_SIZE,
    10 * DEFAULT_PAGE_SIZE,
]
PAGE_LINKS_RANGE = [-3, -2, -1, 0, 1, 2, 3]


def pagination_data(items_list, page_number, page_size):
    if page_size not in PAGE_SIZE_OPTIONS:
        page_size = DEFAULT_PAGE_SIZE
    if len(items_list) > page_size:
        num_pages = math.ceil(len(items_list) / page_size)
        page_number = max(page_number, 1)
        page_number = min(page_number, num_pages)
        pagination_info = []
        if page_number > max(PAGE_LINKS_RANGE) + 1:
            pagination_info.append(
                {
                    "label": "1 .." if page_number > 5 else 1,
                    "number": 1,
                    "status": "",
                }
            )
        for i in PAGE_LINKS_RANGE:
            page_idx = page_number + i
            if 1 <= page_idx <= num_pages:
                pagination_info.append(
                    {
                        "label": page_idx,
                        "number": page_idx,
                        "status": ("active" if page_number == page_idx else ""),
                    }
                )
        if page_number < num_pages - max(PAGE_LINKS_RANGE):
            pagination_info.append(
                {
                    "label": (
                        f".. {num_pages}" if page_number < num_pages - 4 else num_pages
                    ),
                    "number": num_pages,
                    "status": "",
                }
            )

        page_items = items_list[(page_number - 1) * page_size : page_number * page_size]
    else:
        pagination_info = []
        page_items = items_list

    return pagination_info, page_items, page_size, list(PAGE_SIZE_OPTIONS)
