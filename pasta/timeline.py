"""Choose the nodes and links that exist at a given date, and compare two dates."""

from dataclasses import dataclass
from datetime import date
from enum import Enum

import pandas as pd

from pasta.loader import InputData

# RULE: a row (node or link) exists on a day if
#     Actif is True  AND  DateDebut <= day <= DateFin
# with BOTH bounds included: on the DateDebut day it already exists, on the DateFin day it
# still exists (that is why the old system ends on the day BEFORE the go-live).
# On top of that, a link exists only if BOTH its nodes exist: otherwise Graphviz would draw
# an arrow to a node that is not there (in fact it would create an empty one).
#
# This module works on data that is ALREADY VALIDATED (validation.py): Actif is always
# True/False and dates are never empty, so there is no need to check them again here.


@dataclass
class Snapshot:
    """The nodes and links visible on one day: a 'photo' of the company."""

    day: date
    nodes: pd.DataFrame
    links: pd.DataFrame

    # PROPERTY: a method used LIKE A FIELD, without parentheses: snapshot.subtitle
    # (not snapshot.subtitle()). The value is computed from the fields each time.
    # @property is a decorator, like @dataclass. In C++ it would be a const getter method.
    @property
    def subtitle(self) -> str:
        """Text shown under the title of the drawing."""
        # DATE FORMAT in an f-string: after ":" you write how to format it.
        # %d = day, %m = month, %Y = 4-digit year -> "08.10.2026" (Swiss format).
        # In C++ it would be std::format("{:%d.%m.%Y}", day).
        return f"{self.day:%d.%m.%Y}"


# ---------------------------------------------------------------------------------------
# Comparing two dates
# ---------------------------------------------------------------------------------------
# ALGORITHM (set theory): before = keys existing on the "before" date,
# after = keys existing on the "after" date.
#   unchanged = before & after   (intersection: present in both)
#   added     = after - before   (difference: present only after)
#   removed   = before - after   (present only before)
# KEYS: a node is identified by its Id; a link by the tuple (Source, Cible, TypeFlux)
# (links have no Id in the Excel file).


# ENUM: a CLOSED set of named values, like "enum class" in C++. Compared to plain strings it
# prevents typos: a misspelled Status.ADDED fails immediately, while "addded" would go
# unnoticed. The value ("added") is used when it has to be shown as text.
class Status(Enum):
    UNCHANGED = "unchanged"
    ADDED = "added"
    REMOVED = "removed"


NODE_KEY = ["Id"]
LINK_KEY = ["Source", "Cible", "TypeFlux"]


@dataclass
class Comparison:
    """The union of two snapshots, with a "Status" column on every node and link."""

    before: date
    after: date
    nodes: pd.DataFrame
    links: pd.DataFrame

    @property
    def subtitle(self) -> str:
        """Text shown under the title of the drawing."""
        # "→" is the arrow character; Python 3 strings are Unicode, so it can be written as is.
        return f"Changes {self.before:%d.%m.%Y} → {self.after:%d.%m.%Y}"


def compare(data: InputData, before: date, after: date) -> Comparison:
    """Return what is unchanged, added and removed between two dates."""
    old = take_snapshot(data, before)
    new = take_snapshot(data, after)
    return Comparison(
        before=before,
        after=after,
        nodes=_union_with_status(old.nodes, new.nodes, NODE_KEY),
        links=_union_with_status(old.links, new.links, LINK_KEY),
    )


def _keys(table: pd.DataFrame, key: list[str]) -> list[tuple]:
    """Return the key of every row, as a tuple (one per row, in the same order)."""
    # fillna(""): an empty cell (NaN) in the key becomes "". Needed because NaN != NaN:
    # two links with an empty TypeFlux would not be "equal" in a set.
    # itertuples(index=False, name=None) gives each row as a plain TUPLE of values.
    return list(table[key].fillna("").itertuples(index=False, name=None))


def _union_with_status(old: pd.DataFrame, new: pd.DataFrame, key: list[str]) -> pd.DataFrame:
    """Return the rows of new (unchanged or added) and of old (removed), with a Status."""
    old_keys = set(_keys(old, key))
    new_keys = set(_keys(new, key))

    # Rows of "after": unchanged if the key was there before too, otherwise added.
    # (For unchanged rows we keep the "after" one: it is the most recent state.)
    new_status = [
        Status.UNCHANGED if row_key in old_keys else Status.ADDED for row_key in _keys(new, key)
    ]
    # Rows of "before" whose key is NO longer there after: removed.
    # Mask from a list of booleans: pd.Series(list, index=...) uses the same indexes as the
    # table, so .loc[mask] selects the right rows.
    gone = pd.Series([row_key not in new_keys for row_key in _keys(old, key)], index=old.index)
    removed = old.loc[gone]

    # assign(Column=values) returns a NEW table with the extra column.
    # pd.concat([a, b]) puts the two tables one below the other (like joining two vectors);
    # ignore_index=True renumbers the rows 0, 1, 2... (the original indexes are not needed).
    return pd.concat(
        [new.assign(Status=new_status), removed.assign(Status=Status.REMOVED)],
        ignore_index=True,
    )


def take_snapshot(data: InputData, day: date) -> Snapshot:
    """Return the nodes and links that exist on the given day."""
    # .loc[mask] keeps only the rows where the mask is True (and keeps the indexes).
    nodes = data.nodes.loc[_exists_on(data.nodes, day)]
    links = data.links.loc[_exists_on(data.links, day)]

    # isin(nodes["Id"]): True if Source (or Cible) is among the Ids of the VISIBLE nodes.
    # The link stays only if both are.
    both_ends_visible = links["Source"].isin(nodes["Id"]) & links["Cible"].isin(nodes["Id"])
    links = links.loc[both_ends_visible]

    return Snapshot(day=day, nodes=nodes, links=links)


def _exists_on(table: pd.DataFrame, day: date) -> pd.Series:
    """Return a mask: True for the rows that exist on the given day."""
    # VECTORIZED COMPARISON: "column <= day" compares EVERY cell of the column with the same
    # date and returns a mask of True/False (one per row), without writing a loop.
    # astype(bool): after the loader the Actif column may have dtype "object" (a generic
    # container); to combine it with "&" we want a real bool dtype.
    # The three conditions are combined with "&" (element-wise and). Each one has its own
    # variable, so they read better. Written on a single line, every comparison would need
    # PARENTHESES, because "&" has a higher precedence than "<=" and ">=":
    #     active & (table["DateDebut"] <= day) & (table["DateFin"] >= day)
    active = table["Actif"].astype(bool)
    started = table["DateDebut"] <= day
    not_ended = table["DateFin"] >= day
    return active & started & not_ended
