import coverage
import pytest
import pybadges

WARN_TEXT_COLOR = "\033[93m"

WARN_PERCENT = 60
IDEAL_PERCENT = 80

def get_coverage_color(percent):
    if percent < WARN_PERCENT:
        return "red"
    elif percent < IDEAL_PERCENT:
        return "yellow"
    return "green"

def save_file(filename, contents):
    f = open(filename, "w")
    f.write(contents)
    f.close()

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

svg_coverage = pybadges.badge(
    left_text="coverage",
    right_text=f"{round(percent)}%",
    right_color=get_coverage_color(percent),
)
save_file("badge_coverage.svg", svg_coverage)

svg_tests = pybadges.badge(
    left_text="tests",
    right_text="passing" if retcode == 0 else "failing",
    right_color="green" if retcode == 0 else "red",
)
save_file("badge_tests.svg", svg_tests)
