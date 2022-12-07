# proofreading management system links
from src.utils.formatting import nanometer_to_flywire_coordinates

CELL_IDENTIFICATION_SUBMISSION_URL_TEMPLATE = (
    "https://prod.flywire-daf.com/neurons/api/v1/"
    "submit_cell_identification?"
    "valid_id={cell_id}&"
    "user_id={user_id}&"
    "location={coordinates}&"
    "tag={annotation}"
)


def cell_identification_url(cell_id, user_id, coordinates, annotation):
    annotation_safe = None
    if annotation:
        lines = [ln.strip() for ln in annotation.split("\n")]
        lines = [ln for ln in lines if ln]
        annotation_safe = " ; ".join(lines)

    if not annotation_safe:
        raise ValueError(
            f"Provided annotation doesn't look right: '{annotation}'. Please revise and try again."
        )
    else:
        annotation = annotation_safe

    try:
        x, y, z = nanometer_to_flywire_coordinates(coordinates)
        coordinates = f"{x},{y},{z}"
    except Exception as e:
        raise ValueError(
            f"Provided coordinates do not look right: '{coordinates}'. Please specify x,y,z in nanometers and retry.",
            e,
        )

    return CELL_IDENTIFICATION_SUBMISSION_URL_TEMPLATE.format(
        cell_id=cell_id, user_id=user_id, coordinates=coordinates, annotation=annotation
    )
