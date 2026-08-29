"""Kontrollierte Begriffe und Zustände des Bürgerportal-Modells."""

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
PUBLIC_SOURCE_KINDS = (
    "Stadtverwaltung",
    "Ratsmitglied",
    "Fraktion",
    "Ratslotse-Prüfung",
)
PROBLEM_STATUSES = (
    "new",
    "multiple_reports",
    "verified",
    "persists",
    "apparently_resolved",
)
AI_ASSESSMENT_VERDICTS = (
    "suitable",
    "needs_human_review",
    "unsuitable",
)
REPORT_STATUSES = (
    "draft",
    "submitted",
    "in_review",
    "needs_information",
    "accepted",
    "rejected",
    "withdrawn",
)
MODERATION_OUTCOMES = (
    "assigned_existing_problem",
    "approved_for_new_problem",
    "needs_information",
    "rejected",
    "corrected_category",
    "corrected_geography",
)
