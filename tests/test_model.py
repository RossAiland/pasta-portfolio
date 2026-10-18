"""Tests for pasta.model."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from pasta.loader import load_excel
from pasta.model import FALLBACK, Graph, LegendEntry, Node, build_graph
from pasta.timeline import Snapshot, Status, compare, take_snapshot

SAMPLE_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_pastificio.xlsx"
DAY = date(2026, 10, 8)

# CHECKS DONE (mutation testing): with _cell_or always returning the cell (ignoring the
# defaults), 4 tests out of 7 fail. In that case an empty color would become the STRING
# "nan" (str(NaN) gives "nan") and Graphviz would receive a color that does not exist.
# With _legend_label always returning just the type (never domain nor "default style"),
# the 2 tests on legend labels fail.
# With _status_colors always returning the systems' orange (status does not change the
# colors), the 3 tests on added/removed colors fail.


@pytest.fixture
def graph() -> Graph:
    data = load_excel(SAMPLE_FILE)
    return build_graph(take_snapshot(data, DAY), data.parameters)


def node(graph: Graph, node_id: str) -> Node:
    """Return the node with the given id."""
    # next(...) returns the FIRST element produced by the generator expression:
    # "the first n among the nodes with that id". (If there is none it raises StopIteration,
    # and the test fails: that is fine.)
    return next(n for n in graph.nodes if n.id == node_id)


def test_graph_settings_come_from_parametres(graph: Graph) -> None:
    assert graph.title == "Pastificio - IT landscape (fictional data)"
    assert graph.subtitle == "08.10.2026"
    assert (graph.layout, graph.rankdir, graph.fontname) == ("dot", "LR", "Arial")


def test_one_node_and_one_edge_per_visible_row(graph: Graph) -> None:
    assert len(graph.nodes) == 9  # all except SHOP, which does not exist on this date
    assert len(graph.edges) == 8


def test_own_style_is_kept(graph: Graph) -> None:
    mill = node(graph, "MILL")

    assert (mill.color, mill.fillcolor, mill.shape) == ("#F03B20", "#FDBB84", "rectangle")


def test_empty_style_takes_the_parametres_defaults(graph: Graph) -> None:
    bank = node(graph, "BANK")  # in the sample file all its style cells are empty

    assert bank.shape == "rectangle"  # NodeDefaultShape
    assert bank.style == "rounded,filled"  # NodeDefaultStyle
    assert bank.color == "#555555"  # NodeDefaultColor
    assert bank.fillcolor == "#F8F8F8"  # NodeDefaultFillcolor


def test_empty_penwidth_takes_the_fallback(graph: Graph) -> None:
    # In the Excel file the processes have no Penwidth, and Parametres has no
    # NodeDefaultPenwidth: the fallback value written in the code applies.
    assert node(graph, "P_PLAN").penwidth == FALLBACK["NodeDefaultPenwidth"]


def test_edge_styles(graph: Graph) -> None:
    # next() with a generator expression: the first edge that meets the condition.
    macro = next(e for e in graph.edges if (e.source, e.target) == ("MP_PROD", "P_PLAN"))
    plain = next(e for e in graph.edges if (e.source, e.target) == ("P_PLAN", "MILL"))

    assert (macro.color, macro.penwidth) == ("#2B8CBE", 2.0)  # its own style
    assert (plain.color, plain.penwidth) == ("#555555", 1.0)  # default from Parametres
    assert plain.label is None  # empty cell -> None, not NaN


def test_missing_parametres_use_the_fallback() -> None:
    # Hand-made snapshot, with EMPTY parameters and no style columns.
    nodes = pd.DataFrame([{"Id": "A", "Libelle": "A", "TypeElement": "Système"}])
    links = pd.DataFrame(columns=["Source", "Cible"])  # empty table, headers only
    snapshot = Snapshot(day=DAY, nodes=nodes, links=links)

    graph = build_graph(snapshot, parameters={})

    a = graph.nodes[0]
    assert (a.shape, a.color, a.fillcolor) == ("box", "#555555", "#FFFFFF")
    assert graph.layout == "dot"
    assert graph.edges == []


# --- Legend -----------------------------------------------------------------------------


def test_legend_explains_every_node_color(graph: Graph) -> None:
    # One entry per (type, colors), in Excel order. The type with several looks (Processus)
    # gets the domain; BANK, without colors of its own, gets "default style".
    assert graph.legend == [
        LegendEntry("Macro processus", "#2B8CBE", "#2B8CBE"),
        LegendEntry("Processus · Production", "#2F8F2F", "#EAF7EA"),
        LegendEntry("Processus · Sales", "#C51B8A", "#FDE0EF"),
        LegendEntry("Système", "#F03B20", "#FDBB84"),
        LegendEntry("Système · default style", "#555555", "#F8F8F8"),
    ]


def test_every_node_color_is_in_the_legend(graph: Graph) -> None:
    # General check: no color of the drawing is left unexplained.
    # Set comprehension with TUPLES: the set of (border, fill) pairs.
    node_colors = {(node.color, node.fillcolor) for node in graph.nodes}
    legend_colors = {(entry.color, entry.fillcolor) for entry in graph.legend}

    assert node_colors == legend_colors


def test_no_domain_when_a_color_is_shared_by_several_domains() -> None:
    # Two systems with the same color but different domains, plus a third one with another
    # color: the type has two looks, but orange does not belong to a single domain.
    nodes = pd.DataFrame(
        [
            {
                "Id": "A",
                "Libelle": "A",
                "TypeElement": "Système",
                "Domaine": "Sales",
                "Color": "#F03B20",
                "Fillcolor": "#FDBB84",
            },
            {
                "Id": "B",
                "Libelle": "B",
                "TypeElement": "Système",
                "Domaine": "Production",
                "Color": "#F03B20",
                "Fillcolor": "#FDBB84",
            },
            {
                "Id": "C",
                "Libelle": "C",
                "TypeElement": "Système",
                "Domaine": "Sales",
                "Color": "#000000",
                "Fillcolor": "#FFFFFF",
            },
        ]
    )
    links = pd.DataFrame(columns=["Source", "Cible"])

    graph = build_graph(Snapshot(day=DAY, nodes=nodes, links=links), parameters={})

    assert [entry.label for entry in graph.legend] == ["Système", "Système · Sales"]


# --- Comparing two dates ----------------------------------------------------------------


@pytest.fixture
def comparison_graph() -> Graph:
    data = load_excel(SAMPLE_FILE)
    return build_graph(compare(data, DAY, date(2027, 6, 1)), data.parameters)


def test_comparison_subtitle(comparison_graph: Graph) -> None:
    assert comparison_graph.subtitle == "Changes 08.10.2026 → 01.06.2027"


def test_added_and_removed_nodes_get_the_status_colors(comparison_graph: Graph) -> None:
    shop = node(comparison_graph, "SHOP")  # appeared between the two dates
    sheets = node(comparison_graph, "SHEETS")  # disappeared
    mill = node(comparison_graph, "MILL")  # still there

    assert (shop.status, shop.color, shop.fillcolor) == (
        Status.ADDED,
        FALLBACK["AddedColor"],
        FALLBACK["AddedFillcolor"],
    )
    assert sheets.status is Status.REMOVED
    assert sheets.color == FALLBACK["RemovedColor"]
    assert sheets.style.endswith(",dashed")  # dashed border
    assert mill.color == "#F03B20"  # nodes still there keep their color


def test_removed_edge_is_red_and_dashed(comparison_graph: Graph) -> None:
    edge = next(e for e in comparison_graph.edges if (e.source, e.target) == ("P_ORDERS", "SHEETS"))

    assert (edge.color, edge.style) == (FALLBACK["RemovedColor"], "dashed")


def test_status_colors_can_be_changed_in_parametres() -> None:
    data = load_excel(SAMPLE_FILE)
    parameters = {**data.parameters, "AddedColor": "#0000FF"}

    graph = build_graph(compare(data, DAY, date(2027, 6, 1)), parameters)

    assert node(graph, "SHOP").color == "#0000FF"


def test_comparison_legend_ends_with_added_and_removed(comparison_graph: Graph) -> None:
    labels = [entry.label for entry in comparison_graph.legend]

    # [-2:] = the last two elements (slicing with a negative index: counting from the end).
    assert labels[-2:] == ["Added", "Removed"]


def test_snapshot_legend_has_no_status_entries(graph: Graph) -> None:
    labels = [entry.label for entry in graph.legend]

    assert "Added" not in labels and "Removed" not in labels
