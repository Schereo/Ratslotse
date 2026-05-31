from __future__ import annotations

import os
import time
import json
import random
from dataclasses import dataclass
from typing import Iterable

import requests

DEVICE = "https://device.e-pages.dk"
LOGIN_API = "https://login-api.e-pages.dk"
FRONT = "https://front.e-pages.dk"

APP_ID = "zeitungskiosk.nwzonline.de"
CUSTOMER = "nwz"

# folder_id -> human title (discovered from kiosk config)
TITLES: dict[int, str] = {
    8384: "Ammerländer Nachrichten",
    8385: "Der Gemeinnützige",
    8386: "Der Münsterländer",
    8388: "Oldenburger Kreiszeitung",
    8389: "Oldenburger Nachrichten",
    8390: "Wesermarsch-Zeitung",
    8391: "Zeitung für Ganderkesee",
}


@dataclass
class Edition:
    customer: str
    folder: int
    catalog: int
    title: str
    publication_date: str  # YYYY-MM-DD
    pages: int
    content_version: int


class NWZClient:
    def __init__(self, username: str, password: str, udid: str | None = None):
        self.username = username
        self.password = password
        self.udid = udid or f"{int(time.time())}_{random.randint(10_000_000, 99_999_999)}"
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "Mozilla/5.0"
        self._session.headers["Referer"] = f"https://{APP_ID}/"
        self._session.headers["Origin"] = f"https://{APP_ID}"
        # Per-catalog session key cache: catalog -> (key, acquired_ts)
        self._keys: dict[int, tuple[str, float]] = {}
        self._key_ttl = 60 * 30  # 30 min — well below observed validity

    # ---- public catalog API (no auth) ----
    def available(self, folder: int, limit: int = 10) -> list[Edition]:
        r = self._session.get(
            f"{DEVICE}/content/available5.php",
            params={
                "titles": f"{CUSTOMER}/{folder}",
                "limit": str(limit),
                "include": "content_version,sections",
            },
            timeout=30,
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        return [
            Edition(
                customer=it["customer"],
                folder=it["folder_id"],
                catalog=it["catalog"],
                title=it["title"],
                publication_date=it["publication_date"],
                pages=it["pages"],
                content_version=it.get("content_version", 0),
            )
            for it in items
        ]

    # ---- gated content ----
    def _validate(self, catalog: int) -> str:
        cached = self._keys.get(catalog)
        if cached and time.time() - cached[1] < self._key_ttl:
            return cached[0]
        body = {
            "username": self.username,
            "password": self.password,
            "udid": self.udid,
            "referrer_url": f"https://{APP_ID}/",
            "vl_platform": "desktopwebapp",
        }
        url = (
            f"{LOGIN_API}/v1/{APP_ID}/private/validate/prefix/"
            f"{CUSTOMER}/publication/{catalog}/user"
        )
        r = self._session.post(
            url,
            params={"vl_platform": "desktopwebapp"},
            data=json.dumps(body),
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("success"):
            raise RuntimeError(f"Visiolink validate failed: {data}")
        key = data["key"]
        self._keys[catalog] = (key, time.time())
        return key

    def content_xml(self, catalog: int) -> bytes:
        key = self._validate(catalog)
        r = self._session.get(
            f"{FRONT}/session-cc/{key}/{CUSTOMER}/{catalog}/content/default5.php",
            params={
                "vl_platform": "desktopwebapp",
                "supports": "enrichment_vlinternal_url,external_audio",
            },
            timeout=60,
        )
        r.raise_for_status()
        return r.content


def from_env() -> NWZClient:
    user = os.environ["NWZ_USERNAME"]
    pw = os.environ["NWZ_PASSWORD"]
    return NWZClient(user, pw)
