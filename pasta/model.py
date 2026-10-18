"""Turn a snapshot or a comparison into Node and Edge objects with a resolved style."""

from collections import Counter
from dataclasses import dataclass, replace

import pandas as pd

from pasta.timeline import Comparison, Snapshot, Status

# WHY THIS MODULE: the two "renderers" (render_graphviz.py for the SVG, render_html.py for
# the interactive page) receive the SAME list of Node/Edge and know nothing about pandas,
# NaN or default values. It is the C++ idea of "one interface, two implementations":
# the model is the common interface, the renderers are the implementations.
#
# STYLE RULE, for each cell (e.g. the color of a node):
#   1. the value of the cell, if there is one;
#   2. otherwise the default from the Parametres sheet (e.g. NodeDefaultColor);
#   3. if that is missing too, the fallback value written below (FALLBACK).
# Level 3 matters for other input files (e.g. a real one): if a parameter is missing,
# the program still works.
FALLBACK: dict[str, object] = {
    "GraphLabel": "",
    "Layout": "dot",
    "Rankdir": "LR",
    "Fontname": "Arial",
    "NodeDefaultShape": "box",
    "NodeDefaultStyle": "filled",
    "NodeDefaultColor": "#555555",
    "NodeDefaultFillcolor": "#FFFFFF",
    "NodeDefaultPenwidth": 1,
    "EdgeDefaultStyle": "solid",
    "EdgeDefaultColor": "#555555",
    "EdgeDefaultPenwidth": 1,
    # Colors of the COMPARISON between two dates (they can be changed in the Parametres
    # sheet): green = appeared between the two dates, red = disappeared.
    "AddedColor": "#1A9850",
    "AddedFillcolor": "#D9F0D3",
    "RemovedColor": "#D73027",
    "RemovedFillcolor": "#FDDBC7",
}


# frozen=True: once created, nodes and edges do not change (like const fields in C++).
@dataclass(frozen=True)
class Node:
    id: str
    label: str
    kind: str  # TypeElement: "Macro processus", "Processus", "Système"...
    shape: str
    style: str
    color: str  # border
    fillcolor: str  # fill
    penwidth: float  # border thickness
    domain: str | None = None
    project: str | None = None
    # True if the Color and Fillcolor cells were EMPTY and the colors come from the defaults
    # (e.g. BANK): the legend uses it to write "default style".
    uses_default_colors: bool = False
    # In a comparison between two dates: unchanged / added / removed. In a simple snapshot
    # it is always UNCHANGED.
    status: Status = Status.UNCHANGED


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    label: str | None
    style: str  # "solid", "dashed", "dotted"
    color: str
    penwidth: float
    direction: str = "forward"  # "forward" = arrow from source to target, "both" = two heads
    flow_type: str | None = None
    data: str | None = None  # "Données" column: which data flows (useful as a tooltip)
    status: Status = Status.UNCHANGED


# LEGEND. What it explains (the user's choice): ALL THE COLORS of the nodes, i.e. one entry
# for each "element type + colors" combination shown in the drawing, in Excel order.
# Label = the type (Macro processus, Processus, Système...). If the same type has several
# looks, it gets:
#   - the DOMAIN, if that color belongs to a single domain ("Processus · Production");
#   - "default style", if the elements have no colors of their own ("Système · default style").
# In a COMPARISON between two dates, "Added" (green) and "Removed" (red) are appended at the
# end if at least one node or edge has that status; added/removed nodes are not counted in
# the per-type entries, because their color is the status color.
# It is built FROM THE DATA, not written by hand: it shows only what really appears in the
# graph, so it also works with other files. It is computed here in the model, so both
# renderers (Graphviz and HTML) show the same legend.
# (First version, replaced on request: domain colors + flow types.)
LEGEND_SEPARATOR = " · "
DEFAULT_STYLE_LABEL = "default style"


@dataclass(frozen=True)
class LegendEntry:
    label: str  # e.g. "Processus · Production"
    color: str  # border
    fillcolor: str  # fill


@dataclass(frozen=True)
class Graph:
    title: str
    subtitle: str  # e.g. "08.10.2026" or "Changes 08.10.2026 → 01.06.2027"
    layout: str  # Graphviz engine, e.g. "dot"
    rankdir: str  # direction: "LR" left -> right, "TB" top -> bottom
    fontname: str
    # list[Node]: a list of Node. In C++: std::vector<Node>.
    nodes: list[Node]
    edges: list[Edge]
    legend: list[LegendEntry]  # legend entries (see above)


# "Snapshot | Comparison": the parameter can be EITHER type. The function only uses what
# both have (.nodes, .links, .subtitle), so it does not need to know which one it gets:
# this is Python's "DUCK TYPING" ("if it walks like a duck and quacks like a duck, it's a
# duck"). In C++ you would need a common base class or a template.
def build_graph(source: Snapshot | Comparison, parameters: dict[str, object]) -> Graph:
    """Build the Graph of a snapshot or a comparison, filling empty style cells."""
    # First the two dictionaries are merged: the values from Parametres OVERRIDE those of
    # FALLBACK. "{**a, **b}" creates a new dictionary with the keys of a and then those of b
    # (if a key is in both, b wins). "**" "unpacks" a dictionary, as "*" unpacks a list.
    settings = {**FALLBACK, **parameters}

    # to_dict(orient="records") turns the table into a LIST OF DICTIONARIES, one per row:
    # [{"Id": "MILL", "Shape": "rectangle", ...}, ...]. Each row is then read with
    # row.get("Column"), which returns None if the column does not exist in the file
    # (instead of raising an error): useful if a file does not have all the style columns.
    nodes = [_make_node(row, settings) for row in source.nodes.to_dict(orient="records")]
    edges = [_make_edge(row, settings) for row in source.links.to_dict(orient="records")]

    return Graph(
        title=str(settings["GraphLabel"]),
        subtitle=source.subtitle,
        layout=str(settings["Layout"]),
        rankdir=str(settings["Rankdir"]),
        fontname=str(settings["Fontname"]),
        nodes=nodes,
        edges=edges,
        legend=_legend(nodes, edges, settings),
    )


def _legend(nodes: list[Node], edges: list[Edge], settings: dict[str, object]) -> list[LegendEntry]:
    """Return one legend entry per (element type, colors), then Added/Removed if present."""
    # 1. Nodes are grouped by LOOK: key = (type, border, fill).
    #    setdefault(key, []) returns the list of that key and, if the key is not there yet,
    #    creates it empty: so .append() can be called right away, without an if.
    #    Dictionaries keep INSERTION ORDER (since Python 3.7): the legend lists the entries
    #    in the order they appear in the Excel file. (std::map in C++ sorts by key instead.)
    #    A TUPLE can be a dictionary key because it is immutable (a list cannot).
    #    Added/removed nodes are excluded: their color is the status color (step 4).
    groups: dict[tuple[str, str, str], list[Node]] = {}
    for node in nodes:
        if node.status is Status.UNCHANGED:
            groups.setdefault((node.kind, node.color, node.fillcolor), []).append(node)

    # 2. How many different looks does each type have? Counter (standard library
    #    "collections") COUNTS how many times each value appears:
    #    Counter(["Processus", "Processus", "Système"]) -> {"Processus": 2, "Système": 1}.
    #    "for kind, _, _ in groups": iterating over a dictionary gives its KEYS (the tuples
    #    here), which we unpack; "_" is the conventional name for "a value I don't need".
    looks_per_kind = Counter(kind for kind, _, _ in groups)

    # 3. One entry per group. .items() gives the (key, value) pairs; the key is itself a
    #    tuple, unpacked with parentheses: ((kind, color, fillcolor), members).
    entries = [
        LegendEntry(_legend_label(kind, members, looks_per_kind[kind] > 1), color, fillcolor)
        for (kind, color, fillcolor), members in groups.items()
    ]

    # 4. The status entries, only if at least one node or edge has that status.
    #    any(...) is True if the condition holds for AT LEAST ONE element.
    #    [*nodes, *edges]: a new list with all the nodes and then all the edges.
    for status, label in [(Status.ADDED, "Added"), (Status.REMOVED, "Removed")]:
        if any(item.status is status for item in [*nodes, *edges]):
            color, fillcolor = _status_colors(status, settings)
            entries.append(LegendEntry(label, color, fillcolor))
    return entries


def _legend_label(kind: str, members: list[Node], kind_has_several_looks: bool) -> str:
    """Return the legend text of a group of nodes that look the same."""
    # all(...) is True if the condition holds for ALL the elements (any(...): for at least
    # one). Like std::all_of / std::any_of in C++.
    if all(node.uses_default_colors for node in members):
        return f"{kind}{LEGEND_SEPARATOR}{DEFAULT_STYLE_LABEL}"
    if kind_has_several_looks:
        # SET COMPREHENSION: the set of the group's domains, without duplicates.
        domains = {node.domain for node in members}
        if len(domains) == 1 and None not in domains:
            # next(iter(a_set)) = the only element of the set (a set has no positions [0]).
            return f"{kind}{LEGEND_SEPARATOR}{next(iter(domains))}"
    return kind


def _status_colors(status: Status, settings: dict[str, object]) -> tuple[str, str]:
    """Return (border color, fill color) of an added or removed element."""
    # status.value is the text of the Enum ("added"); .capitalize() makes the first letter
    # uppercase ("Added"), which builds the parameter name: "AddedColor".
    prefix = status.value.capitalize()
    return str(settings[f"{prefix}Color"]), str(settings[f"{prefix}Fillcolor"])


def _make_node(row: dict, settings: dict[str, object]) -> Node:
    # str(...) and float(...) are explicit CONVERSIONS (like static_cast in C++):
    # - they guarantee the type promised by the dataclass (a numeric Id like 12 becomes "12";
    #   the thickness 1 read from Excel becomes 1.0);
    # - they tell VSCode which type comes out, since the dictionary values are "object".
    node = Node(
        id=str(row["Id"]),
        label=str(row["Libelle"]),
        kind=str(row["TypeElement"]),
        shape=str(_cell_or(row.get("Shape"), settings["NodeDefaultShape"])),
        style=str(_cell_or(row.get("Style"), settings["NodeDefaultStyle"])),
        color=str(_cell_or(row.get("Color"), settings["NodeDefaultColor"])),
        fillcolor=str(_cell_or(row.get("Fillcolor"), settings["NodeDefaultFillcolor"])),
        penwidth=float(_cell_or(row.get("Penwidth"), settings["NodeDefaultPenwidth"])),
        domain=_text_or_none(row.get("Domaine")),
        project=_text_or_none(row.get("Projet")),
        # "and" between two booleans: True only if BOTH color cells are empty.
        uses_default_colors=bool(pd.isna(row.get("Color")) and pd.isna(row.get("Fillcolor"))),
        # row.get(key, default): if there is no Status column (simple snapshot), UNCHANGED.
        status=row.get("Status", Status.UNCHANGED),
    )
    if node.status is Status.UNCHANGED:
        return node
    # STATUS STYLE: the status colors replace those of the row, with a thicker border;
    # a removed node also gets a dashed border (Graphviz accepts several styles separated by
    # commas, e.g. "rounded,filled,dashed").
    # dataclasses.REPLACE creates a COPY of the object with some fields changed: it is the
    # way to "modify" a frozen dataclass (the original does not change).
    # "is" to compare Enum values: each value exists only once (like None).
    color, fillcolor = _status_colors(node.status, settings)
    style = f"{node.style},dashed" if node.status is Status.REMOVED else node.style
    return replace(node, color=color, fillcolor=fillcolor, style=style, penwidth=2.0)


def _make_edge(row: dict, settings: dict[str, object]) -> Edge:
    edge = Edge(
        source=str(row["Source"]),
        target=str(row["Cible"]),
        label=_text_or_none(row.get("Libelle")),
        style=str(_cell_or(row.get("Style"), settings["EdgeDefaultStyle"])),
        color=str(_cell_or(row.get("Color"), settings["EdgeDefaultColor"])),
        penwidth=float(_cell_or(row.get("Penwidth"), settings["EdgeDefaultPenwidth"])),
        direction=str(_cell_or(row.get("Direction"), "forward")),
        flow_type=_text_or_none(row.get("TypeFlux")),
        data=_text_or_none(row.get("Données")),
        status=row.get("Status", Status.UNCHANGED),
    )
    if edge.status is Status.UNCHANGED:
        return edge
    # Added edge: green and thicker. Removed: red, thicker and dashed.
    color, _ = _status_colors(edge.status, settings)  # "_": the fill color is not needed
    style = "dashed" if edge.status is Status.REMOVED else edge.style
    return replace(edge, color=color, style=style, penwidth=2.0)


def _cell_or(value: object, default: object) -> object:
    """Return the cell value, or the default if the cell is empty (None or NaN)."""
    # pd.isna recognizes both None (missing column, row.get) and NaN (empty cell).
    return default if pd.isna(value) else value


def _text_or_none(value: object) -> str | None:
    """Return the cell as text, or None if it is empty."""
    return None if pd.isna(value) else str(value)
