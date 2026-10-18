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

# PROVA FATTA (mutation testing): con _cell_or che restituisce sempre la cella (ignorando
# i default) falliscono 4 test su 7. In quel caso un colore vuoto diventerebbe la STRINGA
# "nan" (str(NaN) dà "nan") e Graphviz riceverebbe un colore inesistente.
# Con _legend_label che restituisce sempre solo il tipo (mai dominio né "default style")
# falliscono i 2 test sulle etichette della legenda.
# Con _status_colors che restituisce sempre l'arancione dei sistemi (lo stato non cambia i
# colori) falliscono i 3 test sui colori di added/removed.


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
    assert graph.subtitle == "08.10.2026"
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


# --- Legenda ---------------------------------------------------------------------------


def test_legend_explains_every_node_color(graph: Graph) -> None:
    # Una voce per ogni (tipo, colori), nell'ordine dell'Excel. Il tipo con più aspetti
    # (Processus) prende il dominio; BANK, senza colori propri, "default style".
    assert graph.legend == [
        LegendEntry("Macro processus", "#2B8CBE", "#2B8CBE"),
        LegendEntry("Processus · Production", "#2F8F2F", "#EAF7EA"),
        LegendEntry("Processus · Sales", "#C51B8A", "#FDE0EF"),
        LegendEntry("Système", "#F03B20", "#FDBB84"),
        LegendEntry("Système · default style", "#555555", "#F8F8F8"),
    ]


def test_every_node_color_is_in_the_legend(graph: Graph) -> None:
    # Controllo generale: nessun colore del disegno resta senza spiegazione.
    # Set comprehension con TUPLE: l'insieme delle coppie (bordo, riempimento).
    node_colors = {(node.color, node.fillcolor) for node in graph.nodes}
    legend_colors = {(entry.color, entry.fillcolor) for entry in graph.legend}

    assert node_colors == legend_colors


def test_no_domain_when_a_color_is_shared_by_several_domains() -> None:
    # Due sistemi con lo stesso colore ma domini diversi, più un terzo con un altro colore:
    # il tipo ha due aspetti, ma il colore arancione non appartiene a un solo dominio.
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


# --- Confronto tra due date ------------------------------------------------------------


@pytest.fixture
def comparison_graph() -> Graph:
    data = load_excel(SAMPLE_FILE)
    return build_graph(compare(data, DAY, date(2027, 6, 1)), data.parameters)


def test_comparison_subtitle(comparison_graph: Graph) -> None:
    assert comparison_graph.subtitle == "Changes 08.10.2026 → 01.06.2027"


def test_added_and_removed_nodes_get_the_status_colors(comparison_graph: Graph) -> None:
    shop = node(comparison_graph, "SHOP")  # nato tra le due date
    sheets = node(comparison_graph, "SHEETS")  # sparito
    mill = node(comparison_graph, "MILL")  # rimasto

    assert (shop.status, shop.color, shop.fillcolor) == (
        Status.ADDED,
        FALLBACK["AddedColor"],
        FALLBACK["AddedFillcolor"],
    )
    assert sheets.status is Status.REMOVED
    assert sheets.color == FALLBACK["RemovedColor"]
    assert sheets.style.endswith(",dashed")  # bordo tratteggiato
    assert mill.color == "#F03B20"  # i nodi rimasti tengono il loro colore


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

    # [-2:] = gli ultimi due elementi (slicing con indice negativo: si conta dalla fine).
    assert labels[-2:] == ["Added", "Removed"]


def test_snapshot_legend_has_no_status_entries(graph: Graph) -> None:
    labels = [entry.label for entry in graph.legend]

    assert "Added" not in labels and "Removed" not in labels
