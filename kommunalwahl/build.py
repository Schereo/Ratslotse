"""Setzt data.json in die Vorlage ein und schreibt vergleich.html."""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
daten = open(os.path.join(BASE, "data.json"), encoding="utf-8").read()
vorlage = open(os.path.join(BASE, "vergleich-template.html"), encoding="utf-8").read()

# </script> im JSON würde das umschließende <script>-Tag vorzeitig schließen
daten = daten.replace("</", "<\\/")

if "/*DATEN*/" not in vorlage:
    raise SystemExit("Platzhalter /*DATEN*/ fehlt in der Vorlage")

html = vorlage.replace("/*DATEN*/", daten)
ziel = os.path.join(BASE, "vergleich.html")
open(ziel, "w", encoding="utf-8").write(html)
print(f"-> {ziel}  ({os.path.getsize(ziel)/1024:.0f} KB)")
