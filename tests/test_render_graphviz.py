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
    # You CANNOT look for "the line of BANK": if the label has a newline ("Bank\n(external)")
    # the description of the node takes TWO lines of DOT text, and the attributes are on the
    # second one. (That was the bug of the first version of these tests.)
    # str.index(text, start) = position where text appears, searching from "start" on.
    # SLICING source[a:b] = the part of the string from position a (included) to b
    # (excluded), like std::string::substr(a, b - a) in C++.
    begin = source.index(start)
    end = source.index("]", begin)
    return source[begin:end]


# Most tests check the DOT TEXT (dot.source): there is no need to run Graphviz, so they are
# fast and also work on a computer where Graphviz is not installed.
# CHECKS DONE (mutation testing): if the edge style gets lost,
# test_migration_edge_is_dashed fails; without html.escape,
# test_special_characters_are_escaped_in_the_legend fails.
# LESSON: when a test fails, look at the real data before "fixing" the code.
# Here the first version of the tests was wrong (it looked for the attributes on a single
# line), while the code was right.
def test_dot_contains_all_nodes_and_edges() -> None:
    source = to_dot(sample_graph(date(2026, 10, 8))).source

    for node_id in ["MP_PROD", "P_PLAN", "MILL", "SHEETS", "BANK"]:
        assert node_id in source
    assert "MP_PROD -> P_PLAN" in source
    assert "SHOP" not in source  # on this date the WebShop does not exist


def test_graph_settings_and_title() -> None:
    source = to_dot(sample_graph(date(2026, 10, 8))).source

    assert "rankdir=LR" in source
    assert "08.10.2026" in source  # date in the title, in Swiss format


def test_default_style_reaches_the_drawing() -> None:
    source = to_dot(sample_graph(date(2026, 10, 8))).source

    assert 'fillcolor="#F8F8F8"' in attributes_of(source, "BANK [")  # NodeDefaultFillcolor


def test_migration_edge_is_dashed() -> None:
    source = to_dot(sample_graph(date(2027, 3, 15))).source

    assert "style=dashed" in attributes_of(source, "SHEETS -> SHOP [")


# --- Legend -----------------------------------------------------------------------------


def test_legend_is_in_the_title_label() -> None:
    source = to_dot(sample_graph(date(2026, 10, 8))).source

    assert "Legend" in source
    assert "Macro processus" in source
    assert "Processus · Production" in source
    assert "Système · default style" in source
    assert 'BGCOLOR="#FDBB84"' in source  # the orange square of the systems


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
    # "&" in an HTML label must be written "&amp;": otherwise Graphviz cannot read the table.
    source = to_dot(empty_graph([LegendEntry("R&D", "#000000", "#FFFFFF")])).source

    assert "R&amp;D" in source


def test_comparison_title_and_removed_node() -> None:
    data = load_excel(SAMPLE_FILE)
    graph = build_graph(compare(data, date(2026, 10, 8), date(2027, 6, 1)), data.parameters)

    source = to_dot(graph).source

    assert "Changes 08.10.2026 → 01.06.2027" in source
    assert "dashed" in attributes_of(source, "SHEETS [")  # removed node: dashed border


# SKIPIF: this test really runs Graphviz. If dot.exe is not installed (e.g. on someone
# else's computer), pytest SKIPS it instead of failing, and says so in the summary ("s").
# shutil.which("dot") looks for the program as the terminal would: None if not found.
@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz (dot) is not installed")
def test_render_svg_writes_a_file(tmp_path: Path) -> None:
    output = tmp_path / "sub" / "graph.svg"  # the "sub" folder must be created too

    render_svg(sample_graph(date(2026, 10, 8)), output)

    assert output.exists()
    # read_text reads the file as text; an SVG is XML text that contains the <svg tag.
    assert "<svg" in output.read_text(encoding="utf-8")
