import coverage
import pytest
import os

WARN_TEXT_COLOR = "\033[93m"

WARN_PERCENT = 60

cov = coverage.Coverage()
cov.start()

retcode = pytest.main(["tests/unit"])

cov.stop()
cov.save()

percent = cov.html_report()

print(f"Total coverage: {round(percent, 2)}%")
if percent < WARN_PERCENT:
    print(
        WARN_TEXT_COLOR
        + "Warning: Low test coverage! See htmlcov/index.html for more details."
    )

env_file = os.getenv("GITHUB_ENV")
if env_file is not None:
    with open(env_file, "a") as file:
        file.write(f"COVERAGE={round(percent)}")
        file.write(f"TESTS_MESSAGE={'passing' if retcode == 0 else 'failing'}")
        file.write(f"TESTS_VALUE={'1' if retcode == 0 else '0'}")
