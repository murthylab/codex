import requests
import os

BRAINCIRCUITS_TOKEN = os.environ.get("BRAINCIRCUITS_TOKEN")


def neuron2line(
    segment_ids: list[str], target_library: str, email: str, cave_token: str
):

    HEADERS = {
        "Authorization": f"Bearer {BRAINCIRCUITS_TOKEN}",
        "Authorization-Cave": f"Bearer {cave_token}",
        "Content-Type": "application/json",
    }

    BASE_URL = "https://api-test.braincircuits.io"

    response = requests.request(
        method="POST",
        url=f"{BASE_URL}/app/neuron2line",
        headers=HEADERS,
        json={
            "segment_ids": ",".join(segment_ids),
            "template_space": "JRC2018_BRAIN_UNISEX",
            "target_library": target_library,
            "matching_method": "colormip",
            "caveToken": "",
            "email": email,
        },
        params={"project": "fruitfly_fafb_flywire"},
    )
    if not response.ok:
        raise Exception(response.text)
    return response.json()

