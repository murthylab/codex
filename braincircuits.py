import requests

CAVE_TOKEN = "2b479ecfb87e457f4f863055db38918f"

HEADERS = {
    "Authorization": "Bearer PLrh9E-XqFr9_0XrnE5ljn2XMsAnJTSerwK1nff0y-k",
    "Content-Type": "application/json",
}

BASE_URL = "https://api.braincircuits.io/app/neuron2line"


def neuron2line(segment_ids: list[str]):
    data = {
        "segment_ids": ",".join(segment_ids),
        "email": "rmorey@princeton.edu",
        "template_space": "JRC2018_BRAIN_UNISEX",
        "target_library": "fruitfly_brain_FlyLight_Annotator_Gen1_MCFO",
        "matching_method": "colormip",
        "caveToken": CAVE_TOKEN,
    }
    params = {"project": "fruitfly_fafb_flywire"}
    response = requests.post(BASE_URL, headers=HEADERS, json=data, params=params)
    return response.json()


def get_result(jobid: str):
    url = f"{BASE_URL}/result/matching"
    params = {
        "project": "fruitfly_fafb_flywire",
        "job": jobid,
    }
    response = requests.get(url=url, headers=HEADERS, params=params)
    return response.json()


def check_submission(submission_id: str):
    url = "https://api.braincircuits.io/app/neuron2line/submission"
    params = {
        "project": "fruitfly_fafb_flywire",
        "submission": submission_id,
    }
    response = requests.get(url, headers=HEADERS, params=params)
    return response.json()


if __name__ == "__main__":
    print(neuron2line(segment_ids=["720575940608526601"]))
