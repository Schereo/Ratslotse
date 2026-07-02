"""FastAPI backend for the NWZ-Bot web frontend.

Ensures the repo root is importable so we can reuse the existing `nwz` and
`council` packages (scrapers, stores, classification, prompts).
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
