"""Ten sequential whole-house regression scenarios.

The order is deliberate: S01 must pass Architecture -> Structure -> MEP -> Quote
before S02 starts, and so on. This mirrors the owner's requested workflow and
makes the first broken real workflow the thing we repair before continuing.

The project files are human-openable .archforge fixtures. Engineering output is
still subject to each module's provenance/status; a green software test never
turns ENGINEER_REVIEW or UNVERIFIED rules into certified engineering design.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from archforge.project.persistence import load_project
from archforge.structure.analysis import analyze
from archforge.mep.plumbing import route_plumbing
from archforge.mep.drainage import route_drainage
from archforge.mep.electrical import design_circuits, route_cables
from archforge.mep.project_quote import project_quote

ROOT = Path(__file__).parent / "residential_scenarios"


def _entities(doc, kind):
    return [e for e in doc.entities.values() if e.kind == kind]


def _architecture_stage(doc, spec):
    assert len(_entities(doc, "wall")) >= 6 * spec["storeys"]
    assert len(_entities(doc, "floor") + _entities(doc, "room_floor")) >= spec["storeys"]
    assert len(_entities(doc, "cabinet")) >= 2
    if spec['id'] == 'S01':
        # Owner 17 Oct: inspect a furnished, usable house; named boxes are not
        # proof of furniture. Require actual library instances and a stair.
        assert len(_entities(doc, 'library_object')) >= 4
        assert len(_entities(doc, 'stair')) == 1
    else:
        assert len([e for e in _entities(doc, "box") if e.name]) >= 3 * spec["storeys"]
    roofs = _entities(doc, "pitched_roof")
    assert len(roofs) == 1
    assert roofs[0].params["roof_form"] == spec["roof_form"]
    assert roofs[0].params["tile"] == spec["tile"]
    assert len(_entities(doc, "railing")) >= spec["balconies"]
    if spec["split_level"]:
        assert "Split +1.40" in doc.levels
        assert any(e.name == "Split-level wing floor" for e in _entities(doc, "floor"))


def _structural_stage(doc, spec):
    assert len(_entities(doc, "structural_column")) == 9 * spec["storeys"]
    assert len(_entities(doc, "structural_beam")) == 6 * spec["storeys"]
    result = analyze(doc)
    assert result["error"] is None, result["error"]
    assert result["members"], "structural analysis returned no members"
    assert "provenance" in result
    return result


def _mep_stage(doc, spec):
    plumbing = route_plumbing(doc)
    assert plumbing["cold"], "cold-water routing is empty"
    assert plumbing["hot"], "hot-water routing is empty"
    supply = next(e for e in _entities(doc, "plumbing_point") if e.params["point_type"] == "water_supply")
    assert supply.params.get("pipe_system", "multilayer") == spec["pipe_system"]

    drainage = route_drainage(doc)
    assert drainage["pipes"], "drainage routing is empty"
    assert drainage["nodes"], "drainage produced no nodes"

    circuits = design_circuits(doc)
    assert circuits["circuits"], "electrical design produced no circuits"
    cables = route_cables(doc)
    assert cables["runs"], "electrical cable routing produced no runs"
    return {"plumbing": plumbing, "drainage": drainage, "circuits": circuits, "cables": cables}


def _quote_stage(doc):
    quote = project_quote(doc)
    assert "summary" in quote and "gross_total" in quote
    assert quote["summary"]["subtotal"] >= 0
    assert quote["gross_total"] >= 0
    # Scenario prices are synthetic software-test fixtures, never real market data.
    price = _entities(doc, "price_list")
    assert len(price) == 1 and price[0].name.startswith("TEST_FIXTURE")
    assert quote['pricing_complete'], quote['price_book_audit']
    assert quote['summary']['subtotal'] > 0, 'A zero priced total must not hide a broken price-book path'
    return quote


def test_residential_current_scenario_pipeline():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf8"))
    assert [s["id"] for s in manifest] == [f"S{i:02d}" for i in range(1, 11)]

    # Owner 17 Oct: finish the ENTIRE scenario, including visual review, before
    # advancing. A single pytest loop must not silently approve ten houses.
    scenario = os.environ.get('ARCHFORGE_SCENARIO', 'S01')
    assert scenario in [s['id'] for s in manifest]
    selected = next(s for s in manifest if s['id'] == scenario)
    for previous in manifest[:manifest.index(selected)]:
        evidence = ROOT / 'output' / f"{previous['id']}_EVIDENCE.json"
        assert evidence.exists() and json.loads(evidence.read_text())['status'] == 'PASS', f"STOP: {previous['id']} full gate is incomplete"
    for spec in [selected]:
        project_path = ROOT / spec["file"]
        assert project_path.is_file(), f"missing human-openable fixture: {project_path.name}"
        report = load_project(project_path)
        assert report.ok, report.message()
        doc = report.doc

        # Required sequence: design -> structural -> MEP -> commercial offer.
        _architecture_stage(doc, spec)
        _structural_stage(doc, spec)
        _mep_stage(doc, spec)
        _quote_stage(doc)
