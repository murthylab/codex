import requests


from src.data.gcs_data_loader import load_jennet_lines_from_gcs
from src.data.brain_regions import REGIONS, REGION_CATEGORIES


def add_neuropils_to_jennet_lines(lines):
    for compartments in lines.values():
        for compartment, data in compartments.items():
            if compartment in REGIONS:
                data["neuropils"] = [compartment]

            elif lr := [
                n for n in [f"{compartment}_L", f"{compartment}_R"] if n in REGIONS
            ]:
                data["neuropils"] = lr

            elif substr := [n for n in REGIONS if compartment in n]:
                data["neuropils"] = substr

            elif compartment == "OL":
                data["neuropils"] = REGION_CATEGORIES["optic lobe"]

            elif compartment == "SEG":  # "subesophageal ganglion" -> “gnathal ganglia”
                data["neuropils"] = ["GNG"]

    return lines


LINES = add_neuropils_to_jennet_lines(load_jennet_lines_from_gcs())


def braincircuits_request(method, data={}, extra_params=None, route=""):

    HEADERS = {
        "Authorization": "Bearer PLrh9E-XqFr9_0XrnE5ljn2XMsAnJTSerwK1nff0y-k",
        "Content-Type": "application/json",
    }

    BASE_URL = "https://api.braincircuits.io/app/neuron2line"

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


def neuron2line(segment_ids: list[str]):

    CAVE_TOKEN = "2b479ecfb87e457f4f863055db38918f"

    return braincircuits_request(
        method="POST",
        data={
            "segment_ids": ",".join(segment_ids),
            "template_space": "JRC2018_BRAIN_UNISEX",
            "target_library": "fruitfly_brain_FlyLight_Annotator_Gen1_MCFO",
            "matching_method": "colormip",
            "caveToken": CAVE_TOKEN,
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
