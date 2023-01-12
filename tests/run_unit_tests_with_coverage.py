import coverage
import pytest
import os
import sys

WARN_TEXT_COLOR = "\033[93m"

WARN_PERCENT = 60

cov = coverage.Coverage()
cov.start()

retcode = pytest.main(["tests/unit"])
passing = retcode == 0
if len(sys.argv) > 1 and sys.argv[1] == "i":
    retcode = pytest.main(["tests/integration"])
    passing = passing and retcode == 0

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
        file.write(f"COVERAGE={round(percent)}\n")
        file.write(f"TESTS_MESSAGE={'passing' if passing else 'failing'}\n")
        file.write(f"TESTS_VALUE={'1' if passing else '0'}")
