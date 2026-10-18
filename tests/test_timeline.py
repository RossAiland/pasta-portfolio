"""Tests for pasta.timeline."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from pasta.loader import InputData, load_excel
from pasta.timeline import Comparison, Snapshot, Status, compare, take_snapshot

SAMPLE_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_pastificio.xlsx"

# Key dates of the sample data ("Online shop" project):
#   SHOP (WebShop) exists from 2027-03-01; SHEETS (spreadsheets) until 2027-03-31;
#   the migration SHEETS -> SHOP runs from 2027-03-01 to 2027-03-31;
#   go-live on 2027-04-01: from that day P_ORDERS uses SHOP.
ALL_NODES = {
    "MP_PROD",
    "MP_SALES",
    "P_PLAN",
    "P_ORDERS",
    "P_INVOICE",
    "MILL",
    "BILLING",
    "SHEETS",
    "SHOP",
    "BANK",
}


@pytest.fixture
def data() -> InputData:
    return load_excel(SAMPLE_FILE)


# SETS: {a, b, c} is a collection WITHOUT order and WITHOUT duplicates, like std::set
# (but hash-based, so closer to std::unordered_set). Two sets are equal if they contain the
# same elements, in any order: perfect for saying "these nodes are there" without caring
# about the order of the rows.
# Useful operations: "x in s" (membership), s1 - s2 (difference), s1 | s2 (union).
# WARNING: {} alone is an empty dictionary; the empty set is written set().
def node_ids(snapshot: Snapshot) -> set[str]:
    return set(snapshot.nodes["Id"])


def link_pairs(snapshot: Snapshot) -> set[tuple[str, str]]:
    # Here a link is identified by the pair (Source, Cible). Tuples can go in a set because
    # they are IMMUTABLE (lists cannot: an element of a set must not change).
    return set(zip(snapshot.links["Source"], snapshot.links["Cible"], strict=True))


def test_before_the_project(data: InputData) -> None:
    snapshot = take_snapshot(data, date(2026, 10, 8))

    # ALL_NODES - {"SHOP"}: all the nodes except the WebShop, which does not exist yet.
    assert node_ids(snapshot) == ALL_NODES - {"SHOP"}
    assert ("P_ORDERS", "SHEETS") in link_pairs(snapshot)
    assert ("P_ORDERS", "SHOP") not in link_pairs(snapshot)


def test_during_the_migration(data: InputData) -> None:
    snapshot = take_snapshot(data, date(2027, 3, 15))

    assert node_ids(snapshot) == ALL_NODES  # old and new system together
    assert ("SHEETS", "SHOP") in link_pairs(snapshot)  # the migration arrow
    assert ("P_ORDERS", "SHOP") not in link_pairs(snapshot)  # no go-live yet


def test_after_the_go_live(data: InputData) -> None:
    snapshot = take_snapshot(data, date(2027, 6, 1))

    assert node_ids(snapshot) == ALL_NODES - {"SHEETS"}
    assert ("P_ORDERS", "SHOP") in link_pairs(snapshot)
    assert ("SHEETS", "SHOP") not in link_pairs(snapshot)


# BOUNDARY TESTS: bugs often hide right on the boundaries (a "<" instead of "<=").
# The first day, the last day, and the days just before and just after are tested.
# CHECK DONE ("mutation testing" = breaking the code on purpose to see whether the tests
# notice): with ">" instead of ">=" in _exists_on, ONLY test_last_day_is_included fails.
# The other tests still passed, because none of their dates falls on a DateFin.
def test_first_day_is_included(data: InputData) -> None:
    assert "SHOP" in node_ids(take_snapshot(data, date(2027, 3, 1)))
    assert "SHOP" not in node_ids(take_snapshot(data, date(2027, 2, 28)))


def test_last_day_is_included(data: InputData) -> None:
    assert "SHEETS" in node_ids(take_snapshot(data, date(2027, 3, 31)))
    assert "SHEETS" not in node_ids(take_snapshot(data, date(2027, 4, 1)))


# PARAMETRIZE: the same test run several times with different values. pytest counts it as
# 3 separate tests, and if one fails it says for which date. It is like a for loop, but each
# iteration is a test of its own.
@pytest.mark.parametrize("day", [date(2026, 10, 8), date(2027, 3, 15), date(2027, 6, 1)])
def test_inactive_link_is_never_shown(data: InputData, day: date) -> None:
    # MILL -> BILLING has Actif = False in the Excel file.
    assert ("MILL", "BILLING") not in link_pairs(take_snapshot(data, day))


def test_link_is_hidden_when_one_of_its_nodes_is_hidden() -> None:
    # Hand-made data: B ends in June 2026, but the link A -> B (by mistake) does not.
    start, end = date(2026, 1, 1), date(2100, 12, 31)
    data = InputData(
        nodes=pd.DataFrame(
            [
                {"Id": "A", "Actif": True, "DateDebut": start, "DateFin": end},
                {"Id": "B", "Actif": True, "DateDebut": start, "DateFin": date(2026, 6, 30)},
            ]
        ),
        links=pd.DataFrame(
            [{"Source": "A", "Cible": "B", "Actif": True, "DateDebut": start, "DateFin": end}]
        ),
        projects=pd.DataFrame(),
        parameters={},
    )

    assert link_pairs(take_snapshot(data, date(2026, 5, 1))) == {("A", "B")}
    assert link_pairs(take_snapshot(data, date(2026, 10, 1))) == set()


# --- Comparing two dates ----------------------------------------------------------------

BEFORE, AFTER = date(2026, 10, 8), date(2027, 6, 1)


def ids_with(comparison: Comparison, status: Status) -> set[str]:
    nodes = comparison.nodes
    return set(nodes.loc[nodes["Status"] == status, "Id"])


def pairs_with(comparison: Comparison, status: Status) -> set[tuple[str, str]]:
    links = comparison.links.loc[comparison.links["Status"] == status]
    return set(zip(links["Source"], links["Cible"], strict=True))


def test_compare_finds_added_and_removed(data: InputData) -> None:
    comparison = compare(data, BEFORE, AFTER)

    assert ids_with(comparison, Status.ADDED) == {"SHOP"}
    assert ids_with(comparison, Status.REMOVED) == {"SHEETS"}
    assert ids_with(comparison, Status.UNCHANGED) == ALL_NODES - {"SHOP", "SHEETS"}
    assert pairs_with(comparison, Status.ADDED) == {("P_ORDERS", "SHOP"), ("SHOP", "MILL")}
    assert pairs_with(comparison, Status.REMOVED) == {("P_ORDERS", "SHEETS")}


def test_compare_contains_each_row_once(data: InputData) -> None:
    comparison = compare(data, BEFORE, AFTER)

    # Union of the two snapshots: each node appears ONCE only, whatever its status.
    # duplicated().any(): True if at least one Id is repeated.
    assert not comparison.nodes["Id"].duplicated().any()
    assert set(comparison.nodes["Id"]) == ALL_NODES


def test_compare_in_the_other_direction_swaps_added_and_removed(data: InputData) -> None:
    comparison = compare(data, AFTER, BEFORE)

    assert ids_with(comparison, Status.ADDED) == {"SHEETS"}
    assert ids_with(comparison, Status.REMOVED) == {"SHOP"}


def test_compare_same_day_changes_nothing(data: InputData) -> None:
    comparison = compare(data, BEFORE, BEFORE)

    # set(column) == {a single value}: all the rows have the same status.
    assert set(comparison.nodes["Status"]) == {Status.UNCHANGED}
    assert set(comparison.links["Status"]) == {Status.UNCHANGED}


def test_link_with_empty_flow_type_is_still_matched() -> None:
    # Empty TypeFlux in the link key: without fillna("") (NaN != NaN) the same link would be
    # "removed" AND "added" instead of "unchanged".
    # WARNING: use float("nan"), i.e. what really comes from an empty Excel cell.
    # The first version used None, but None == None is TRUE: the test passed even without
    # fillna and protected nothing (found out with mutation testing).
    start, end = date(2026, 1, 1), date(2100, 12, 31)
    data = InputData(
        nodes=pd.DataFrame(
            [{"Id": x, "Actif": True, "DateDebut": start, "DateFin": end} for x in ["A", "B"]]
        ),
        links=pd.DataFrame(
            [
                {
                    "Source": "A",
                    "Cible": "B",
                    "TypeFlux": float("nan"),
                    "Actif": True,
                    "DateDebut": start,
                    "DateFin": end,
                }
            ]
        ),
        projects=pd.DataFrame(),
        parameters={},
    )

    comparison = compare(data, BEFORE, AFTER)

    assert list(comparison.links["Status"]) == [Status.UNCHANGED]


def test_subtitles() -> None:
    empty = pd.DataFrame()
    assert Snapshot(BEFORE, empty, empty).subtitle == "08.10.2026"
    assert Comparison(BEFORE, AFTER, empty, empty).subtitle == "Changes 08.10.2026 → 01.06.2027"
