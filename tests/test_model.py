"""Tests for pasta.model."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from pasta.loader import load_excel
from pasta.model import FALLBACK, Graph, Node, build_graph
from pasta.timeline import Snapshot, take_snapshot

SAMPLE_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_pastificio.xlsx"
DAY = date(2026, 10, 8)

# PROVA FATTA (mutation testing): con _cell_or che restituisce sempre la cella (ignorando
# i default) falliscono 4 test su 7. In quel caso un colore vuoto diventerebbe la STRINGA
# "nan" (str(NaN) dà "nan") e Graphviz riceverebbe un colore inesistente.


@pytest.fixture
def graph() -> Graph:
    data = load_excel(SAMPLE_FILE)
    return build_graph(take_snapshot(data, DAY), data.parameters)


def node(graph: Graph, node_id: str) -> Node:
    """Return the node with the given id."""
    # next(...) restituisce il PRIMO elemento prodotto dalla generator expression:
    # "il primo n tra i nodi con quell'id". (Se non ce n'è nessuno solleva StopIteration,
    # e il test fallisce: va bene così.)
    return next(n for n in graph.nodes if n.id == node_id)


def test_graph_settings_come_from_parametres(graph: Graph) -> None:
    assert graph.title == "Pastificio - IT landscape (fictional data)"
    assert graph.day == DAY
    assert (graph.layout, graph.rankdir, graph.fontname) == ("dot", "LR", "Arial")


def test_one_node_and_one_edge_per_visible_row(graph: Graph) -> None:
    assert len(graph.nodes) == 9  # tutti tranne SHOP, che a questa data non esiste
    assert len(graph.edges) == 8


def test_own_style_is_kept(graph: Graph) -> None:
    mill = node(graph, "MILL")

    assert (mill.color, mill.fillcolor, mill.shape) == ("#F03B20", "#FDBB84", "rectangle")


def test_empty_style_takes_the_parametres_defaults(graph: Graph) -> None:
    bank = node(graph, "BANK")  # nel file di esempio ha tutte le celle di stile vuote

    assert bank.shape == "rectangle"  # NodeDefaultShape
    assert bank.style == "rounded,filled"  # NodeDefaultStyle
    assert bank.color == "#555555"  # NodeDefaultColor
    assert bank.fillcolor == "#F8F8F8"  # NodeDefaultFillcolor


def test_empty_penwidth_takes_the_fallback(graph: Graph) -> None:
    # Nell'Excel i processi non hanno Penwidth, e Parametres non ha NodeDefaultPenwidth:
    # vale il valore di riserva scritto nel codice.
    assert node(graph, "P_PLAN").penwidth == FALLBACK["NodeDefaultPenwidth"]


def test_edge_styles(graph: Graph) -> None:
    # next() con una generator expression: la prima freccia che soddisfa la condizione.
    macro = next(e for e in graph.edges if (e.source, e.target) == ("MP_PROD", "P_PLAN"))
    plain = next(e for e in graph.edges if (e.source, e.target) == ("P_PLAN", "MILL"))

    assert (macro.color, macro.penwidth) == ("#2B8CBE", 2.0)  # stile proprio
    assert (plain.color, plain.penwidth) == ("#555555", 1.0)  # default di Parametres
    assert plain.label is None  # cella vuota -> None, non NaN


def test_missing_parametres_use_the_fallback() -> None:
    # Snapshot costruito a mano, con parametri VUOTI e senza colonne di stile.
    nodes = pd.DataFrame([{"Id": "A", "Libelle": "A", "TypeElement": "Système"}])
    links = pd.DataFrame(columns=["Source", "Cible"])  # tabella vuota, solo le intestazioni
    snapshot = Snapshot(day=DAY, nodes=nodes, links=links)

    graph = build_graph(snapshot, parameters={})

    a = graph.nodes[0]
    assert (a.shape, a.color, a.fillcolor) == ("box", "#555555", "#FFFFFF")
    assert graph.layout == "dot"
    assert graph.edges == []
