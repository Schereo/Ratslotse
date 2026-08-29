"""Kontrollierte Begriffe und Zustände des Bürgerportal-Modells."""

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
    "published_as_new_problem",
    "needs_information",
    "rejected",
    "corrected_category",
    "corrected_geography",
)
