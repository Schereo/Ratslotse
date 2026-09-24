"""Der Abgleich der Fakten-Eval — steht seit 24.09.2026 in ``council/fakten_abgleich.py``.

Umgezogen, weil Lottis Selbstprüfung (``council/self_check.py``) dieselben
Regeln zur Laufzeit braucht: Jede Zahl der Antwort steht im Kontext, unter
ihrem Jahr. Zwei Fassungen derselben Regel liefen auseinander — die Eval
mäße dann etwas anderes als der Betrieb prüft. Die Schichtenregel erlaubt
nur diese Richtung (``eval`` darf ``council`` importieren, nicht umgekehrt),
deshalb liegt das Original dort und hier nur der alte Name.
"""
from council.fakten_abgleich import *  # noqa: F401,F403 — der alte Name bleibt benutzbar
