"""Companies House + Gazette client tests (mocked transport; live gated)."""

import json
import os

import httpx
import pytest

from diligence.dataroom.build import companies_house_fixture
from diligence.external import (
    CompaniesHouseClient,
    CompaniesHouseFixture,
    GazetteClient,
)
from diligence.ledger.models import CafeConfig

CH_PROFILE = {
    "company_name": "EXAMPLE TRADING LTD",
    "company_number": "01234567",
    "company_status": "active",
    "type": "ltd",
    "date_of_creation": "2015-03-02",
    "registered_office_address": {
        "address_line_1": "1 High Street", "locality": "London",
        "postal_code": "EC1A 1AA",
    },
    "sic_codes": ["56102"],
}
CH_CHARGES = {
    "items": [
        {"charge_code": "012345670001", "status": "outstanding",
         "created_on": "2022-05-10",
         "persons_entitled": [{"name": "Big Bank plc"}],
         "particulars": {"description": "Fixed and floating charge."}},
        {"charge_code": "012345670002", "status": "fully-satisfied",
         "created_on": "2018-01-01",
         "persons_entitled": [{"name": "Old Lender Ltd"}],
         "particulars": {"description": "Legal charge."}},
    ]
}
CH_OFFICERS = {"items": [
    {"name": "SMITH, Jane", "officer_role": "director",
     "appointed_on": "2015-03-02"},
]}


def _ch_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/company/01234567":
            return httpx.Response(200, json=CH_PROFILE)
        if path == "/company/01234567/charges":
            return httpx.Response(200, json=CH_CHARGES)
        if path == "/company/01234567/officers":
            return httpx.Response(200, json=CH_OFFICERS)
        return httpx.Response(404, json={})

    return httpx.MockTransport(handler)


def test_companies_house_parses_profile_officers_charges():
    ch = CompaniesHouseClient(api_key="test", transport=_ch_transport())
    profile = ch.profile("01234567")
    assert profile.company_name == "EXAMPLE TRADING LTD"
    assert profile.registered_office == "1 High Street, London, EC1A 1AA"
    assert profile.sic_codes == ("56102",)

    officers = ch.officers("01234567")
    assert officers[0].name == "SMITH, Jane"

    charges = ch.charges("01234567")
    assert len(charges) == 2
    outstanding = [c for c in charges if c.outstanding]
    assert len(outstanding) == 1
    assert outstanding[0].persons_entitled == ("Big Bank plc",)


def test_companies_house_missing_company_returns_none():
    ch = CompaniesHouseClient(api_key="test", transport=_ch_transport())
    assert ch.profile("99999999") is None
    assert ch.charges("99999999") == []


def test_companies_house_caches_responses(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json=CH_PROFILE)

    ch = CompaniesHouseClient(api_key="test",
                              transport=httpx.MockTransport(handler),
                              cache_dir=tmp_path)
    ch.profile("01234567")
    ch.profile("01234567")
    assert calls["n"] == 1
    # A fresh client hits the disk cache, not the network
    ch2 = CompaniesHouseClient(api_key="test",
                               transport=httpx.MockTransport(handler),
                               cache_dir=tmp_path)
    ch2.profile("01234567")
    assert calls["n"] == 1


def test_fixture_matches_client_interface(tmp_path):
    cfg = CafeConfig()
    f = tmp_path / "ch.json"
    f.write_text(json.dumps(companies_house_fixture(cfg)))
    ch = CompaniesHouseFixture(f)

    profile = ch.profile(cfg.company_number)
    assert profile.company_name == cfg.company_name
    assert ch.profile("00000000") is None

    charges = ch.charges(cfg.company_number)
    assert len(charges) == 1
    assert charges[0].outstanding
    assert charges[0].persons_entitled == (cfg.loan.lender,)
    assert charges[0].charge_code == cfg.loan.charge_id


def test_gazette_parses_entries():
    payload = {"entry": [
        {"id": "https://www.thegazette.co.uk/id/notice/12345",
         "title": "EXAMPLE TRADING LTD — Winding-Up Petition",
         "f:notice-code": "4510", "published": "2024-02-01",
         "link": [{"@href": "https://www.thegazette.co.uk/notice/12345"}]},
    ]}
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json=payload))
    gz = GazetteClient(transport=transport)
    notices = gz.insolvency_notices("Example Trading Ltd")
    assert len(notices) == 1
    assert notices[0].notice_code == "4510"
    assert "Winding-Up" in notices[0].title


def test_gazette_single_entry_object():
    payload = {"entry": {"id": "n1", "title": "T", "f:notice-code": "2450",
                         "published": "2024-01-01", "link": []}}
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json=payload))
    gz = GazetteClient(transport=transport)
    assert len(gz.insolvency_notices("X")) == 1


# --- Live smoke tests (instant demo credibility; skipped without creds) ------

live = pytest.mark.skipif(
    not os.environ.get("COMPANIES_HOUSE_API_KEY"),
    reason="COMPANIES_HOUSE_API_KEY not set")


@live
def test_live_companies_house_real_company():
    ch = CompaniesHouseClient()
    profile = ch.profile("00445790")  # TESCO PLC
    assert profile is not None
    assert "TESCO" in profile.company_name.upper()
    charges = ch.charges("00445790")
    assert isinstance(charges, list)


@live
def test_live_gazette_search():
    gz = GazetteClient()
    notices = gz.insolvency_notices("Limited")
    assert isinstance(notices, list)
