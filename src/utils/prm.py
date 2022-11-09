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
    annotation = annotation or ""
    coordinates = coordinates or ""
    if coordinates:
        coordinates = coordinates.replace("[", "")
        coordinates = coordinates.replace("]", "")
        coordinates = ",".join([p for p in coordinates.split() if p])
    return CELL_IDENTIFICATION_SUBMISSION_URL_TEMPLATE.format(
        cell_id=cell_id, user_id=user_id, coordinates=coordinates, annotation=annotation
    )
