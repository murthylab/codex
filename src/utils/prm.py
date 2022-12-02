# proofreading management system links

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

    coordinates = coordinates or ""
    if coordinates:
        coordinates = coordinates.replace("[", "")
        coordinates = coordinates.replace("]", "")
        coordinates = coordinates.replace(",", "")
        coordinates = coordinates.replace(";", "")
        coordinates = [p for p in coordinates.split() if p]
        if len(coordinates) == 3:
            # convert from nm to FlyWire units
            coordinates = f"{int(coordinates[0]) // 4},{int(coordinates[1]) // 4},{int(coordinates[2]) // 40}"
        else:
            coordinates = ""
    return CELL_IDENTIFICATION_SUBMISSION_URL_TEMPLATE.format(
        cell_id=cell_id, user_id=user_id, coordinates=coordinates, annotation=annotation
    )
