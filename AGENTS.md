# Arbeitsablauf für Änderungen

- Nach jedem abgeschlossenen Änderungsauftrag automatisch einen eigenen Branch
  verwenden, die zugehörigen Änderungen committen, pushen und einen Pull
  Request erstellen.
- Den Pull Request anschließend automatisch mergen, sobald die relevanten
  Tests und alle verpflichtenden CI-Checks erfolgreich sind und keine
  Merge-Konflikte bestehen.
- Bei fehlenden Berechtigungen, fehlgeschlagenen Checks oder Konflikten nicht
  mergen, sondern den konkreten Blocker melden.
- Bereits vorhandene, nicht zum Auftrag gehörende Änderungen nicht in den
  Commit oder Pull Request aufnehmen.

# Bürgerportal

- Bei Arbeiten am kommunalen Problemtracker oder an späteren Bürgeranliegen
  zuerst `BUERGERPORTAL-BACKLOG.md` lesen und bestätigte Entscheidungen dort
  als einzige Quelle der Wahrheit pflegen.
