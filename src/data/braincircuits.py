import requests
import os

BRAINCIRCUITS_TOKEN = os.environ.get("BRAINCIRCUITS_TOKEN")
BRAINCIRCUITS_ENDPOINT = "api.braincircuits.io"


def neuron2line(segment_ids: list[str], target_library: str, email: str) -> dict:
    response = requests.post(
        url=f"https://{BRAINCIRCUITS_ENDPOINT}/app/neuron2line",
        headers={
            "Authorization": f"Bearer {BRAINCIRCUITS_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "segment_ids": ",".join(segment_ids),
            "template_space": "JRC2018_BRAIN_UNISEX",
            "target_library": target_library,
            "matching_method": "colormip",
            "caveToken": "",
            "email": email,
        },
        params={"project": "fruitfly_fafb_flywire_public"},
    )
    response.raise_for_status()
    return response.json()
