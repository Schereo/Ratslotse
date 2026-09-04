"""Kontrollierte Begriffe des privaten und öffentlichen Bürgerportal-Modells."""

# Konservative Hülle des Oldenburger Stadtgebiets. Sie verhindert versehentliche
# Meldungen in anderen Städten; die Moderation bestimmt später die genaue Geografie.
OLDENBURG_BOUNDS = {
    "south": 53.05,
    "north": 53.24,
    "west": 8.08,
    "east": 8.33,
}

PROBLEM_CATEGORIES = (
    "mobility",
    "public_space",
    "education",
    "childcare",
    "housing",
    "environment",
    "accessibility",
    "administration",
    "other",
)
SCOPE_KINDS = ("point", "facility", "route", "area", "citywide")
PROBLEM_STATUSES = (
    "new",
    "multiple_reports",
    "verified",
    "persists",
    "apparently_resolved",
)
FREQUENCIES = ("once", "several", "many", "very_many")
