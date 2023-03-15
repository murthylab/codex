from src.utils.logging import log_error


# TODO: Get rid of these once data is published
def extract_access_token(raw_text):
    try:
        raw_text = raw_text.replace("'", '"')
        parts = raw_text.split('"')
        longest_part = sorted(parts, key=lambda p: -len(p))[0]
        return longest_part.strip()
    except Exception as e:
        log_error(f"Could not extract access token from {raw_text}: {e}")
        return raw_text.replace('"', "").strip()
