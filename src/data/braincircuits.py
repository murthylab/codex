import requests


BRAINCIRCUITS_TOKEN = "900ac5c2bb32028caa65b98f85b919f9"
CAVE_TOKEN = "2b479ecfb87e457f4f863055db38918f"

HEADERS = {
    "Authorization": f"Bearer {BRAINCIRCUITS_TOKEN}",
    "Authorization-Cave": f"Bearer {CAVE_TOKEN}",
    "Content-Type": "application/json",
}

BASE_URL = "https://api-test.braincircuits.io"


def neuron2line(segment_ids: list[str], target_library: str):
    response = requests.request(
        method="POST",
        url=f"{BASE_URL}/app/neuron2line",
        headers=HEADERS,
        json={
            "segment_ids": ",".join(segment_ids),
            "template_space": "JRC2018_BRAIN_UNISEX",
            "target_library": target_library,
            "matching_method": "colormip",
            "caveToken": CAVE_TOKEN,
        },
        params={"project": "fruitfly_fafb_flywire"},
    )
    return response.json()
