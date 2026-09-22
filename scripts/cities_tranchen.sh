#!/bin/bash
# Ein teurer Städte-Lauf in Tranchen — EIN frischer Prozess je Tranche
# (Begründung in scripts/cities_tranche.py).
#
#   scripts/cities_tranchen.sh reason 1000 20 --alle   # Stufe, Tranche, Durchgänge, weitere Schalter
#
# Auf dev in tmux starten, damit er einen getrennten Laptop überlebt:
#   tmux new -d -s reason 'cd ~/app && scripts/cities_tranchen.sh reason 1000 20 2>&1 | tee -a ~/reason.log'
#
# Bricht eine Tranche mit einem Fehlercode ab, hält die Schleife an, statt
# blind weiterzuzahlen — ein Abbruch ist ein Befund, kein Schluckauf.
cd "$(dirname "$0")/.." || exit 1
[ -f .env ] && { set -a; . ./.env; set +a; }
STUFE="${1:?Stufe: fit | reason | idea_fit}"
LIMIT="${2:-1000}"
MAX="${3:-50}"
shift $(( $# < 3 ? $# : 3 ))
for i in $(seq 1 "$MAX"); do
  echo "=== $STUFE Durchgang $i, $(date '+%F %T') ==="
  nice -n 10 .venv/bin/python scripts/cities_tranche.py "$STUFE" --limit "$LIMIT" "$@"
  code=$?
  if [ $code -eq 9 ]; then echo "=== ALLES FERTIG ==="; exit 0; fi
  if [ $code -ne 0 ]; then echo "=== ABGEBROCHEN mit Code $code — Schleife hält an ==="; exit $code; fi
done
echo "=== $MAX Durchgänge erreicht ==="
