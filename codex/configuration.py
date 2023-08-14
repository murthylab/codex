import os

MIN_SYN_THRESHOLD = 5
MIN_NBLAST_SCORE_SIMILARITY = 4
MAX_NEURONS_FOR_DOWNLOAD = 100
MAX_NODES_FOR_PATHWAY_ANALYSIS = 10

APP_ENVIRONMENT = str(os.environ.get("APP_ENVIRONMENT", "DEV"))


class RedirectHomeError(ValueError):
    def __init__(self, msg):
        super().__init__(msg)
