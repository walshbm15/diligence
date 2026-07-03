"""The Gazette API client (free, no key): insolvency & winding-up notices."""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

BASE_URL = "https://www.thegazette.co.uk"
MIN_INTERVAL_S = 1.0


@dataclass(frozen=True)
class GazetteNotice:
    notice_id: str
    title: str
    notice_code: str
    published: str
    uri: str

    @classmethod
    def from_entry(cls, e: dict) -> GazetteNotice:
        links = e.get("link", [])
        uri = ""
        for link in links if isinstance(links, list) else [links]:
            if isinstance(link, dict) and link.get("@href"):
                uri = link["@href"]
                break
        return cls(
            notice_id=str(e.get("id", "")),
            title=e.get("title", ""),
            notice_code=str(e.get("f:notice-code", "")),
            published=e.get("published", ""),
            uri=uri,
        )


class GazetteClient:
    def __init__(self, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(base_url=BASE_URL, transport=transport,
                                    timeout=20.0,
                                    headers={"Accept": "application/json"})
        self._last_request = 0.0

    def _get(self, path: str, params: dict) -> dict:
        wait = MIN_INTERVAL_S - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()
        resp = self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    def insolvency_notices(self, company_name: str) -> list[GazetteNotice]:
        """Search insolvency notices mentioning the company name."""
        data = self._get("/insolvency/notice/data.json",
                         {"text": f'"{company_name}"'})
        entries = data.get("entry", []) or []
        if isinstance(entries, dict):  # single result comes back as an object
            entries = [entries]
        return [GazetteNotice.from_entry(e) for e in entries]
