import os
import uuid
import socket

MIN_SYN_COUNT = 5
MIN_NBLAST_SCORE_SIMILARITY = 4
MAX_NEURONS_FOR_DOWNLOAD = 100

GOOGLE_CLIENT_ID = (
    "356707763910-l9ovf7f2at2vc23f3u2j356aokr4eb99.apps.googleusercontent.com"
)

ADMIN_DASHBOARD_URL = (
    "https://lookerstudio.google.com/reporting/980e9b4f-1bd7-41e5-90a1-0e7c443d3fa9"
)

SUPPORT_EMAIL = "arie@princeton.edu"

BUILD_GIT_SHA = os.environ.get("BUILD_GIT_SHA", "na")
BUILD_TIMESTAMP = os.environ.get("BUILD_TIMESTAMP", "na")
APP_ENVIRONMENT = str(os.environ.get("APP_ENVIRONMENT", "PROD"))

proc_id = str(uuid.uuid4())[-4:] + f"-{APP_ENVIRONMENT[:1]}"
host_name = socket.gethostname()
