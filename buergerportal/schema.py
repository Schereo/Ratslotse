"""Gemeinsame SQLite-Schemahelfer des Bürgerportals."""


def sql_enum(values: tuple[str, ...]) -> str:
    """Render trusted domain constants for a SQLite CHECK expression."""
    return ", ".join(f"'{value}'" for value in values)
