"""Companies House API client (free, key required) + fixture variant.

The fixture variant serves the same normalized types from a JSON file so
the pipeline runs identically against synthetic data rooms (whose company
doesn't exist at CH) and real targets. Free tier: 600 requests / 5 min —
throttled and cached.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

BASE_URL = "https://api.company-information.service.gov.uk"
MIN_INTERVAL_S = 0.5


@dataclass(frozen=True)
class CompanyProfile:
    company_name: str
    company_number: str
    status: str
    company_type: str
    incorporated_on: str
    registered_office: str
    sic_codes: tuple[str, ...]

    @classmethod
    def from_api(cls, d: dict) -> CompanyProfile:
        office = d.get("registered_office_address", {}) or {}
        office_str = ", ".join(
            v for k in ("address_line_1", "address_line_2", "locality",
                        "postal_code")
            if (v := office.get(k)))
        return cls(
            company_name=d.get("company_name", ""),
            company_number=d.get("company_number", ""),
            status=d.get("company_status", ""),
            company_type=d.get("type", ""),
            incorporated_on=d.get("date_of_creation", ""),
            registered_office=office_str,
            sic_codes=tuple(d.get("sic_codes", []) or []),
        )


@dataclass(frozen=True)
class Officer:
    name: str
    role: str
    appointed_on: str
    resigned_on: str | None

    @classmethod
    def from_api(cls, d: dict) -> Officer:
        return cls(
            name=d.get("name", ""),
            role=d.get("officer_role", ""),
            appointed_on=d.get("appointed_on", ""),
            resigned_on=d.get("resigned_on"),
        )


@dataclass(frozen=True)
class Charge:
    charge_code: str
    status: str  # outstanding | fully-satisfied | part-satisfied
    created_on: str
    persons_entitled: tuple[str, ...]
    description: str

    @classmethod
    def from_api(cls, d: dict) -> Charge:
        return cls(
            charge_code=d.get("charge_code", d.get("charge_number", "")),
            status=d.get("status", ""),
            created_on=d.get("created_on", ""),
            persons_entitled=tuple(
                p.get("name", "") for p in d.get("persons_entitled", []) or []),
            description=(d.get("particulars", {}) or {}).get("description", ""),
        )

    @property
    def outstanding(self) -> bool:
        return self.status not in ("fully-satisfied", "satisfied")


class CompaniesHouseClient:
    def __init__(self, api_key: str | None = None,
                 transport: httpx.BaseTransport | None = None,
                 cache_dir: Path | None = None):
        self.api_key = api_key or os.environ.get("COMPANIES_HOUSE_API_KEY", "")
        if not self.api_key and transport is None:
            raise ValueError("COMPANIES_HOUSE_API_KEY not set")
        self._client = httpx.Client(
            base_url=BASE_URL, auth=(self.api_key, ""),
            transport=transport, timeout=20.0)
        self._cache_dir = cache_dir
        self._mem_cache: dict[str, dict] = {}
        self._last_request = 0.0

    def _get(self, path: str) -> dict:
        if path in self._mem_cache:
            return self._mem_cache[path]
        if self._cache_dir:
            f = self._cache_dir / (path.strip("/").replace("/", "_") + ".json")
            if f.exists():
                data = json.loads(f.read_text())
                self._mem_cache[path] = data
                return data
        wait = MIN_INTERVAL_S - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()
        resp = self._client.get(path)
        if resp.status_code == 404:
            data = {}
        else:
            resp.raise_for_status()
            data = resp.json()
        self._mem_cache[path] = data
        if self._cache_dir:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            f = self._cache_dir / (path.strip("/").replace("/", "_") + ".json")
            f.write_text(json.dumps(data))
        return data

    def profile(self, company_number: str) -> CompanyProfile | None:
        d = self._get(f"/company/{company_number}")
        return CompanyProfile.from_api(d) if d else None

    def officers(self, company_number: str) -> list[Officer]:
        d = self._get(f"/company/{company_number}/officers")
        return [Officer.from_api(i) for i in d.get("items", [])]

    def charges(self, company_number: str) -> list[Charge]:
        d = self._get(f"/company/{company_number}/charges")
        return [Charge.from_api(i) for i in d.get("items", [])]


class CompaniesHouseFixture:
    """Same interface as CompaniesHouseClient, backed by a JSON fixture.

    Fixture shape: {"profile": {...}, "officers": [...], "charges": [...]}
    using the raw Companies House API field names.
    """

    def __init__(self, source: Path | dict):
        self._data = (json.loads(Path(source).read_text())
                      if isinstance(source, (str, Path)) else source)

    def profile(self, company_number: str) -> CompanyProfile | None:
        d = self._data.get("profile")
        if not d or d.get("company_number") != company_number:
            return None
        return CompanyProfile.from_api(d)

    def officers(self, company_number: str) -> list[Officer]:
        return [Officer.from_api(i) for i in self._data.get("officers", [])]

    def charges(self, company_number: str) -> list[Charge]:
        return [Charge.from_api(i) for i in self._data.get("charges", [])]
