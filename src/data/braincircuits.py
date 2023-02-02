import requests

HEADERS = {
    "Authorization": "Bearer PLrh9E-XqFr9_0XrnE5ljn2XMsAnJTSerwK1nff0y-k",  # temporary
    "Content-Type": "application/json",
}

BASE_URL = "https://api-test.braincircuits.io/app/neuron2line"


def braincircuits_request(method, data={}, extra_params=None, route=""):
    params = {"project": "fruitfly_fafb_flywire"}

    if extra_params:
        params.update(extra_params)

    response = requests.request(
        method=method,
        url=f"{BASE_URL}/{route}",
        headers=HEADERS,
        json=data,
        params=params,
    )
    return response.json()


def neuron2line(segment_ids: list[str], target_library: str):
    return braincircuits_request(
        method="POST",
        data={
            "segment_ids": ",".join(segment_ids),
            "template_space": "JRC2018_BRAIN_UNISEX",
            "target_library": target_library,
            "matching_method": "colormip",
            "caveToken": "2b479ecfb87e457f4f863055db38918f",  # temporary
        },
    )


def check_submission(submission_id: str):
    return braincircuits_request(
        method="GET",
        extra_params={"submission": submission_id},
        route="submission",
    )


def get_result(jobid: str):
    return braincircuits_request(
        method="GET",
        extra_params={"job": jobid},
        route="result/matching",
    )
