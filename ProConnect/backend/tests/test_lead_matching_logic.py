"""
tests/test_lead_matching_logic.py

Offline unit tests for the lead-matching pipeline in tasks/lead_tasks.py.

These tests verify the pure-logic pieces of `_distribute_leads`:
  - specificity scoring (Problem 1, Layer 2)
  - radius expansion at 1.5x / 2.0x (Problem 2, Fix 1)
  - rank order: highest specificity first, distance is the tie-breaker

They do NOT need a live Postgres/Redis; we feed the helpers fake DB rows
through small stand-in objects. This complements the end-to-end pytest
suite (which needs the docker compose stack to run).
"""

import asyncio
from types import SimpleNamespace

from tasks.lead_tasks import (
    SCORE_EXACT_OR_DEEPER,
    SCORE_GRANDPARENT,
    SCORE_PARENT,
    _build_category_score_map,
    _radius_filter,
)


class FakeResult:
    def __init__(self, rows):
        self._rows = rows
    def all(self):
        return [(r,) for r in self._rows]
    def first(self):
        if not self._rows:
            return None
        return (self._rows[0],)


class FakeDB:
    def __init__(self, queue):
        self._queue = list(queue)
    async def execute(self, _stmt):
        if not self._queue:
            raise AssertionError("FakeDB ran out of canned responses")
        return self._queue.pop(0)


# ---- _build_category_score_map -------------------------------------------

def test_score_map_assigns_exact_three_for_job_category():
    JOB = "cat-cleaning"
    db = FakeDB([
        FakeResult([]),
        FakeResult([None]),
    ])
    score_map, taxonomy = asyncio.run(_build_category_score_map(db, JOB))
    assert score_map[JOB] == SCORE_EXACT_OR_DEEPER
    assert taxonomy["parent"] is None


def test_score_map_assigns_deeper_specificity_to_children():
    JOB = "cleaning"
    POOL = "pool-cleaning"
    POOL_CHEMICALS = "pool-chemicals"
    db = FakeDB([
        FakeResult([POOL]),
        FakeResult([POOL_CHEMICALS]),
        FakeResult([None]),
    ])
    score_map, _ = asyncio.run(_build_category_score_map(db, JOB))
    assert score_map[POOL] == SCORE_EXACT_OR_DEEPER
    assert score_map[POOL_CHEMICALS] == SCORE_EXACT_OR_DEEPER


def test_score_map_assigns_parent_one_and_grandparent_half():
    JOB = "pool-cleaning"
    PARENT = "cleaning"
    GP = "home-services"
    db = FakeDB([
        FakeResult([]),
        FakeResult([PARENT]),
        FakeResult([GP]),
    ])
    score_map, taxonomy = asyncio.run(_build_category_score_map(db, JOB))
    assert score_map[JOB] == SCORE_EXACT_OR_DEEPER
    assert score_map[PARENT] == SCORE_PARENT
    assert score_map[GP] == SCORE_GRANDPARENT
    assert taxonomy["parent"] == PARENT
    assert taxonomy["grandparent"] == GP


def test_score_map_exact_beats_parent_when_same_node_appears_in_both_directions():
    JOB = "cleaning"
    AMBIG = "pool-cleaning"
    db = FakeDB([
        FakeResult([AMBIG]),
        FakeResult([]),
        FakeResult([AMBIG]),
        FakeResult([None]),
    ])
    score_map, _ = asyncio.run(_build_category_score_map(db, JOB))
    assert score_map[AMBIG] == SCORE_EXACT_OR_DEEPER


# ---- _radius_filter -------------------------------------------------------

def _profile(lat=None, lng=None, radius_km=25, business_name="T"):
    return SimpleNamespace(lat=lat, lng=lng, radius_km=radius_km,
                           business_name=business_name, id=business_name)


def _pref(suburbs_json=None):
    return SimpleNamespace(service_suburbs=suburbs_json)


def test_radius_filter_base_radius_includes_only_in_range():
    rows = [
        (_profile(-33.87, 151.21, 25, "In"),  None, _pref(), 3.0),
        (_profile(-37.81, 144.96, 25, "Out"), None, _pref(), 3.0),
    ]
    in_range = _radius_filter(rows, -33.87, 151.21, "Sydney", 1.0)
    names = sorted(r[2].business_name for r in in_range)
    assert names == ["In"]


def test_radius_filter_expands_at_1_5x():
    rows = [
        (_profile(-34.14, 151.21, 25, "Edge"), None, _pref(), 3.0),
    ]
    base = _radius_filter(rows, -33.87, 151.21, "Sydney", 1.0)
    expanded = _radius_filter(rows, -33.87, 151.21, "Sydney", 1.5)
    assert base == []
    assert len(expanded) == 1


def test_radius_filter_expands_at_2x_for_supply_gap_areas():
    rows = [
        (_profile(-34.27, 151.21, 25, "Far"), None, _pref(), 3.0),
    ]
    base = _radius_filter(rows, -33.87, 151.21, "Sydney", 1.0)
    one_five = _radius_filter(rows, -33.87, 151.21, "Sydney", 1.5)
    two_x = _radius_filter(rows, -33.87, 151.21, "Sydney", 2.0)
    assert base == []
    assert one_five == []
    assert len(two_x) == 1


def test_radius_filter_includes_when_suburb_listed_even_if_geo_out_of_range():
    rows = [
        (_profile(-37.81, 144.96, 25, "Travelling"), None,
         _pref('[{"suburb": "Sydney"}]'), 3.0),
    ]
    in_range = _radius_filter(rows, -33.87, 151.21, "Sydney", 1.0)
    assert len(in_range) == 1


def test_radius_filter_includes_all_when_job_has_no_coords():
    rows = [
        (_profile(-37.81, 144.96, 25, "Anywhere"), None, _pref(), 3.0),
    ]
    in_range = _radius_filter(rows, None, None, "Sydney", 1.0)
    assert len(in_range) == 1


# ---- Sort: specificity beats distance ------------------------------------

def test_specialist_beats_closer_generalist_on_sort():
    rows = [
        (5.0,  SCORE_PARENT,          _profile(business_name="GenericCleaner"), None),
        (20.0, SCORE_EXACT_OR_DEEPER, _profile(business_name="PoolSpecialist"), None),
        (10.0, SCORE_GRANDPARENT,     _profile(business_name="HomeServices"),   None),
    ]
    rows.sort(key=lambda r: (-r[1], r[0]))
    order = [r[2].business_name for r in rows]
    assert order == ["PoolSpecialist", "GenericCleaner", "HomeServices"]


def test_distance_breaks_tie_within_same_specificity():
    rows = [
        (15.0, SCORE_EXACT_OR_DEEPER, _profile(business_name="PoolFar"),  None),
        (3.0,  SCORE_EXACT_OR_DEEPER, _profile(business_name="PoolNear"), None),
    ]
    rows.sort(key=lambda r: (-r[1], r[0]))
    order = [r[2].business_name for r in rows]
    assert order == ["PoolNear", "PoolFar"]


# ---- Same engine, every trade --------------------------------------------
# These tests prove the matcher is fully generic: drop in any trade taxonomy
# and the same specificity rules apply. The taxonomies below mirror the
# 24 canonical trades and the level-2 subcategories actually seeded by
# backend/seeds/seed_categories.py.

import pytest


@pytest.mark.parametrize("job_cat,parent_cat,sibling,unrelated_specialist", [
    # Plumbing: a "Hot Water" specialist beats a generic "Plumbing" tradie.
    ("plumbing-hot-water",       "plumbing",   "plumbing-blocked-drains",  "plumbing-gas"),
    # Electrical: a "Switchboard" specialist beats a generic "Electrical" tradie.
    ("electrical-switchboard",   "electrical", "electrical-power-points",  "electrical-ev-charger"),
    # Roofing: a "Gutters" specialist beats a generic "Roofing" tradie.
    ("roofing-gutters",          "roofing",    "roofing-repairs",          "roofing-skylights"),
    # Landscaping: a "Tree Services" specialist beats a generic landscaper.
    ("landscaping-tree-services", "landscaping", "landscaping-lawn-turf",   "landscaping-irrigation"),
    # HVAC: a "Split System" specialist beats a generic AC tradie.
    ("hvac-split-system",        "hvac",       "hvac-ducted",              "hvac-evaporative"),
    # Kitchen renovation: a "Cabinet" specialist beats a generic kitchen renovator.
    ("kitchen-cabinets",         "kitchen-renovation", "kitchen-splashback", "kitchen-appliance"),
    # Pest control: a "Termite" specialist beats a generic pest controller.
    ("pest-termite",             "pest-control", "pest-general",            "pest-possum"),
    # Fencing: a "Pool Fencing" specialist beats a generic fencer.
    ("fencing-pool",             "fencing",    "fencing-colorbond",        "fencing-timber"),
    # Carpentry: a "Decking" specialist beats a generic carpenter.
    ("carpentry-decking",        "carpentry",  "carpentry-doors",          "carpentry-stairs"),
    # Solar: a "Battery" specialist beats a generic solar tradie.
    ("solar-battery",            "solar",      "solar-panels",             "solar-maintenance"),
])
def test_specificity_scoring_is_generic_across_all_trades(
    job_cat, parent_cat, sibling, unrelated_specialist
):
    """
    For ANY trade, the score map assigns:
      job_cat              -> 3.0 (exact match)
      parent_cat           -> 1.0 (broader trade)
      sibling              -> NOT included (sibling has no relationship to job)
      unrelated_specialist -> NOT included
    """
    db = FakeDB([
        FakeResult([]),               # no children for an L2 subcategory job
        FakeResult([parent_cat]),     # the parent trade
        FakeResult([None]),           # no grandparent (L1 trades sit at the top)
    ])
    score_map, taxonomy = asyncio.run(_build_category_score_map(db, job_cat))
    assert score_map[job_cat] == SCORE_EXACT_OR_DEEPER, f"{job_cat} should be exact match"
    assert score_map[parent_cat] == SCORE_PARENT, f"{parent_cat} should be parent match"
    assert sibling not in score_map, f"sibling {sibling} should not score"
    assert unrelated_specialist not in score_map, f"unrelated {unrelated_specialist} should not score"


@pytest.mark.parametrize("trade,specialist_sub", [
    ("plumbing",          "plumbing-hot-water"),
    ("electrical",        "electrical-ev-charger"),
    ("roofing",           "roofing-skylights"),
    ("hvac",              "hvac-split-system"),
    ("landscaping",       "landscaping-tree-services"),
    ("solar",             "solar-battery"),
    ("kitchen-renovation","kitchen-cabinets"),
    ("bathroom-renovation","bathroom-vanity"),
    ("flooring",          "flooring-timber"),
    ("fencing",           "fencing-pool"),
    ("security",          "security-cctv"),
    ("gas-fitting",       "gas-appliance"),
    ("pest-control",      "pest-termite"),
])
def test_broad_job_routes_to_specialist_in_every_trade(trade, specialist_sub):
    """
    When a homeowner posts at the L1 trade level (e.g. 'Solar'), a tradie
    registered under an L2 specialist row (e.g. 'Battery Storage') still
    scores 3.0 — they get the lead because deeper specificity is treated
    as a perfect match. This was the exact behaviour the categories doc
    described for Cleaning -> Pool Cleaning; we prove it generalises.
    """
    db = FakeDB([
        FakeResult([specialist_sub]),  # the L1 trade has this specialist child
        FakeResult([]),                # no L3 grandchildren in this test
        FakeResult([None]),            # L1 has no parent
    ])
    score_map, _ = asyncio.run(_build_category_score_map(db, trade))
    assert score_map[trade] == SCORE_EXACT_OR_DEEPER
    assert score_map[specialist_sub] == SCORE_EXACT_OR_DEEPER, (
        f"Specialist {specialist_sub} should score as high as exact match "
        f"for broad job in trade {trade}"
    )


def test_radius_expansion_works_for_supply_gap_in_any_trade():
    """
    A roofing job in a regional area (e.g. a Toowoomba homeowner needing
    gutter repairs) should still find a tradie at 2x radius even when the
    base radius is empty. This isn't specific to cleaning — the same
    auto-expansion applies to every trade in the taxonomy.
    """
    # Roofing tradie ~45km away with a 25km base radius.
    rows = [
        (_profile(-34.27, 151.21, 25, "RoofingSpecialist"),
         None, _pref(), SCORE_EXACT_OR_DEEPER),
    ]
    base = _radius_filter(rows, -33.87, 151.21, "Toowoomba", 1.0)
    expanded = _radius_filter(rows, -33.87, 151.21, "Toowoomba", 2.0)
    assert base == []
    assert len(expanded) == 1
