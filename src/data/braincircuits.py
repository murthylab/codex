import requests
import os

BRAINCIRCUITS_TOKEN = os.environ.get("BRAINCIRCUITS_TOKEN")
BRAINCIRCUITS_ENDPOINT = os.environ.get(
    "BRAINCIRCUITS_ENDPOINT", "api-test.braincircuits.io"
)


def neuron2line(
    segment_ids: list[str], target_library: str, email: str, cave_token: str
) -> dict:
    response = requests.post(
        url=f"https://{BRAINCIRCUITS_ENDPOINT}/app/neuron2line",
        headers={
            "Authorization": f"Bearer {BRAINCIRCUITS_TOKEN}",
            "Authorization-Cave": f"Bearer {cave_token}",
            "Content-Type": "application/json",
        },
        json={
            "segment_ids": ",".join(segment_ids),
            "template_space": "JRC2018_BRAIN_UNISEX",
            "target_library": target_library,
            "matching_method": "colormip",
            "caveToken": cave_token,
            "email": email,
        },
        params={"project": "fruitfly_fafb_flywire"},
    )
    response.raise_for_status()
    return response.json()
