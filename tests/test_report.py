"""Report generator tests: sufficiency scoring + HTML output."""

import dataclasses
import json

import pytest

from diligence.checks import FactIndex
from diligence.dataroom.build import build_dataroom
from diligence.dataroom.spec import build_spec
from diligence.evals.ground_truth import expected_facts
from diligence.ledger import generate_ledger
from diligence.mutations import DEFAULT_MUTATIONS
from diligence.report.generate import generate_report
from diligence.report.sufficiency import assess


@pytest.fixture(scope="module")
def gt_facts():
    spec = build_spec(generate_ledger())
    return [dataclasses.replace(f, tier="clean")
            for f in expected_facts(spec, dataroom="t")]


def test_sufficiency_full_room_scores_100(gt_facts):
    report = assess(FactIndex(gt_facts))
    assert report.score == 100
    assert report.gaps == []


def test_sufficiency_flags_missing_documents(gt_facts):
    partial = [f for f in gt_facts
               if not f.source_doc.startswith("vat_return")
               and f.source_doc != "lease.pdf"]
    report = assess(FactIndex(partial), needs_review=3)
    assert report.score < 100
    gaps = " ".join(report.gaps)
    assert "VAT returns" in gaps
    assert "Lease" in gaps
    assert "human verification" in gaps


def test_report_generation_end_to_end(tmp_path):
    # Build a spec-only "room" on disk with just the JSON sidecars
    room = tmp_path / "room_m1"
    room.mkdir()
    spec = build_dataroom(room, mutations=DEFAULT_MUTATIONS, tiers=())
    facts = [dataclasses.replace(f, tier="ground_truth")
             for f in expected_facts(spec, dataroom="room_m1")]

    out = generate_report(facts, room, "clean", tmp_path / "out")
    assert out.exists()
    html = (out if out.suffix == ".html" else out.with_suffix(".html")).read_text()
    assert "The Copper Kettle Café Ltd" in html
    assert "T1.VAT_TRIANGLE" in html
    assert "T3.CHARGES" in html
    assert "companies_house:charges" in html
    assert "Ask the seller" in html
    assert "Document sufficiency" in html


def test_clean_report_has_no_flags(tmp_path):
    room = tmp_path / "room_clean"
    room.mkdir()
    spec = build_dataroom(room, mutations=None, tiers=())
    facts = [dataclasses.replace(f, tier="ground_truth")
             for f in expected_facts(spec, dataroom="room_clean")]
    out = generate_report(facts, room, "clean", tmp_path / "out")
    html = (out if out.suffix == ".html" else out.with_suffix(".html")).read_text()
    assert "No reconciliation discrepancies found" in html
    assert json.loads((room / "mutation_log.json").read_text()) == []
