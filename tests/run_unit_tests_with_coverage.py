import coverage
import pytest

WARN_PERCENT = 60

WARN_COLOR = "\033[93m"

cov = coverage.Coverage()
cov.start()

retcode = pytest.main(["tests/unit"])

cov.stop()
cov.save()

percent = cov.html_report()

print(f"Total coverage: {round(percent, 2)}%")
if percent < WARN_PERCENT:
    print(
        WARN_COLOR
        + "Warning: Low test coverage! See htmlcov/index.html for more details."
    )
