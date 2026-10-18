"""Tests for pasta.render_graphviz."""

import shutil
from datetime import date
from pathlib import Path

import pytest

from pasta.loader import load_excel
from pasta.model import Graph, LegendEntry, build_graph
from pasta.render_graphviz import render_svg, to_dot
from pasta.timeline import compare, take_snapshot

SAMPLE_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_pastificio.xlsx"


def sample_graph(day: date) -> Graph:
    data = load_excel(SAMPLE_FILE)
    return build_graph(take_snapshot(data, day), data.parameters)


def attributes_of(source: str, start: str) -> str:
    """Return the DOT text from `start` (e.g. 'BANK [') up to the closing ']'."""
    # NON si può cercare "la riga di BANK": se l'etichetta ha un a capo ("Bank\n(external)")
    # la descrizione del nodo occupa DUE righe del testo DOT, e gli attributi sono sulla
    # seconda. (Era il bug della prima versione di questi test.)
    # str.index(testo, da) = posizione in cui testo compare, cercando a partire da "da".
    # SLICING source[a:b] = la parte di stringa dalla posizione a (inclusa) alla b (esclusa),
    # come std::string::substr(a, b - a) in C++.
    begin = source.index(start)
    end = source.index("]", begin)
    return source[begin:end]


# La maggior parte dei test controlla il TESTO DOT (dot.source): non serve eseguire Graphviz,
# quindi sono veloci e funzionano anche su un computer dove Graphviz non è installato.
# PROVE FATTE (mutation testing): se lo stile delle frecce si perde, fallisce
# test_migration_edge_is_dashed; senza html.escape fallisce
# test_special_characters_are_escaped_in_the_legend.
# LEZIONE: quando un test fallisce, prima di "aggiustare" il codice guarda il dato vero.
# Qui la prima versione dei test era sbagliata (cercava gli attributi su una sola riga),
# mentre il codice era giusto.
def test_dot_contains_all_nodes_and_edges() -> None:
    source = to_dot(sample_graph(date(2026, 10, 8))).source

    for node_id in ["MP_PROD", "P_PLAN", "MILL", "SHEETS", "BANK"]:
        assert node_id in source
    assert "MP_PROD -> P_PLAN" in source
    assert "SHOP" not in source  # a questa data il WebShop non esiste


def test_graph_settings_and_title() -> None:
    source = to_dot(sample_graph(date(2026, 10, 8))).source

    assert "rankdir=LR" in source
    assert "08.10.2026" in source  # data nel titolo, in formato svizzero


def test_default_style_reaches_the_drawing() -> None:
    source = to_dot(sample_graph(date(2026, 10, 8))).source

    assert 'fillcolor="#F8F8F8"' in attributes_of(source, "BANK [")  # NodeDefaultFillcolor


def test_migration_edge_is_dashed() -> None:
    source = to_dot(sample_graph(date(2027, 3, 15))).source

    assert "style=dashed" in attributes_of(source, "SHEETS -> SHOP [")


# --- Legenda ---------------------------------------------------------------------------


def test_legend_is_in_the_title_label() -> None:
    source = to_dot(sample_graph(date(2026, 10, 8))).source

    assert "Legend" in source
    assert "Macro processus" in source
    assert "Processus · Production" in source
    assert "Système · default style" in source
    assert 'BGCOLOR="#FDBB84"' in source  # il quadratino arancione dei sistemi


def empty_graph(legend: list[LegendEntry]) -> Graph:
    """A graph without nodes, only to test the title and the legend."""
    return Graph(
        title="Title",
        subtitle="08.10.2026",
        layout="dot",
        rankdir="LR",
        fontname="Arial",
        nodes=[],
        edges=[],
        legend=legend,
    )


def test_no_legend_when_there_is_nothing_to_explain() -> None:
    assert "Legend" not in to_dot(empty_graph([])).source


def test_special_characters_are_escaped_in_the_legend() -> None:
    # "&" in un'etichetta HTML va scritto "&amp;": altrimenti Graphviz non legge la tabella.
    source = to_dot(empty_graph([LegendEntry("R&D", "#000000", "#FFFFFF")])).source

    assert "R&amp;D" in source


def test_comparison_title_and_removed_node() -> None:
    data = load_excel(SAMPLE_FILE)
    graph = build_graph(compare(data, date(2026, 10, 8), date(2027, 6, 1)), data.parameters)

    source = to_dot(graph).source

    assert "Changes 08.10.2026 → 01.06.2027" in source
    assert "dashed" in attributes_of(source, "SHEETS [")  # nodo sparito: bordo tratteggiato


# SKIPIF: questo test esegue davvero Graphviz. Se dot.exe non è installato (es. sul computer
# di qualcun altro), pytest lo SALTA invece di farlo fallire, e lo dice nel riepilogo ("s").
# shutil.which("dot") cerca il programma come farebbe il terminale: None se non lo trova.
@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz (dot) is not installed")
def test_render_svg_writes_a_file(tmp_path: Path) -> None:
    output = tmp_path / "sub" / "graph.svg"  # anche la cartella "sub" va creata

    render_svg(sample_graph(date(2026, 10, 8)), output)

    assert output.exists()
    # read_text legge il file come testo; un SVG è testo XML che contiene il tag <svg.
    assert "<svg" in output.read_text(encoding="utf-8")
