"""Draw a Graph as a static image (SVG) with Graphviz."""

from html import escape
from pathlib import Path

import graphviz

from pasta.model import Graph

# HOW GRAPHVIZ WORKS: it is an EXTERNAL program (dot.exe, installed separately) that receives
# the description of a graph in a text language, DOT, and works out by itself where to put
# each node (the "layout"). Example of DOT:
#     digraph {
#         rankdir=LR
#         MILL [label="MillControl" shape=rectangle color="#F03B20"]
#         P_PLAN -> MILL
#     }
# The Python library "graphviz" is used to BUILD this text with functions (dot.node,
# dot.edge) and to call dot.exe to turn it into an SVG.
#
# TWO SEPARATE FUNCTIONS:
# - to_dot(graph): builds the DOT. It can be tested WITHOUT running Graphviz (just check the
#   text it produces, dot.source);
# - render_svg(graph, file): calls dot.exe and writes the file.
#
# The library escapes quotes and special characters (& < >) in labels by itself, and a
# newline "\n" becomes a second line of text: nothing special to do.


def to_dot(graph: Graph) -> graphviz.Digraph:
    """Build the Graphviz description (DOT) of the graph."""
    # Digraph = DIRECTED graph (with arrows). engine = which layout algorithm to use
    # ("dot" = hierarchical, in levels: suits processes -> systems).
    dot = graphviz.Digraph(name="pasta", engine=graph.layout)

    # dot.attr(...) sets the attributes of the whole graph. In Graphviz every value is TEXT,
    # which is why numbers are passed with str(...).
    # The graph label holds the title and the legend (see _title_and_legend);
    # labelloc="t" puts it at the top.
    dot.attr(
        rankdir=graph.rankdir,
        label=_title_and_legend(graph),
        labelloc="t",
        fontname=graph.fontname,
    )
    # dot.attr("node", ...) / dot.attr("edge", ...) = values shared by all nodes / edges.
    dot.attr("node", fontname=graph.fontname, fontsize="11")
    dot.attr("edge", fontname=graph.fontname, fontsize="9")

    for node in graph.nodes:
        dot.node(
            node.id,
            label=node.label,
            shape=node.shape,
            style=node.style,
            color=node.color,
            fillcolor=node.fillcolor,
            penwidth=str(node.penwidth),
            # tooltip = text shown when the mouse is over the node in the browser.
            # "a or b" returns a if it is "truthy" (not None, not empty), otherwise b: here
            # node.domain, or "" if the domain is missing.
            tooltip=f"{node.kind} - {node.domain or ''}",
        )

    for edge in graph.edges:
        # The edge attributes go in a dictionary, because some are there only when needed
        # (label, tooltip): Graphviz does not want empty values.
        attributes = {
            "style": edge.style,
            "color": edge.color,
            "penwidth": str(edge.penwidth),
            "dir": edge.direction,  # "forward" = one arrow head, "both" = two heads
        }
        if edge.label:  # None (or empty text) counts as False: no label
            attributes["label"] = edge.label
        if edge.data:
            attributes["tooltip"] = edge.data
        # **attributes "UNPACKS" the dictionary into keyword arguments: like writing
        # dot.edge(source, target, style=..., color=..., ...). (Seen with {**a, **b} in model.py.)
        dot.edge(edge.source, edge.target, **attributes)

    return dot


# LEGEND: WHY IN AN HTML TABLE UNDER THE TITLE.
# First version (tried and dropped): a box made of nodes inside the graph (a
# "cluster_legend" subgraph). Graphviz treats it as part of the graph: it places it where it
# likes, and moving it to the right needed invisible edges that SPOILED the layout of the
# real nodes (e.g. Bank ended up under the legend).
# Solution: the graph label (the title) can be an HTML TABLE. There the legend does NOT take
# part in the layout, so it moves nothing.
# Each entry is a small square with the colors (border and fill) + the text; the entries
# are computed by model.py (all node colors: type, plus domain or "default style" if needed).
# (An earlier version also showed sample lines for the flow types, drawn as the bottom
# border of a cell, SIDES="B", even dashed: removed on request.)
#
# HTML LABELS: in Graphviz a label written between < > (instead of quotes) is "HTML-like":
# you can use <TABLE>, <TR> (row), <TD> (cell), <FONT>, <BR/> (line break).
# Special characters in the data text (& < >) must be ESCAPED with html.escape: a domain
# like "R&D" would otherwise break the table.


def _title_and_legend(graph: Graph) -> str:
    """Return the HTML-like label of the graph: title, date and legend."""
    # Under the title: the snapshot date, or "Changes <before> → <after>" for a comparison
    # (the text is prepared by timeline.py, subtitle property).
    title_lines = [*graph.title.split("\n"), graph.subtitle]
    # [*list, other]: "*" unpacks the list into a new list (like {**a} for dicts).
    title = "<BR/>".join(escape(line) for line in title_lines)

    rows = [f'<TR><TD><FONT POINT-SIZE="14">{title}</FONT></TD></TR>']
    legend = _legend_table(graph)
    if legend:
        rows.append(f"<TR><TD>{legend}</TD></TR>")
    # The OUTER < > tell Graphviz "this is an HTML label".
    return f'<<TABLE BORDER="0" CELLSPACING="4">{"".join(rows)}</TABLE>>'


def _legend_table(graph: Graph) -> str:
    """Return the legend as an HTML table on one row, or "" if there is nothing to explain."""
    if not graph.legend:
        return ""  # nothing to explain: no legend

    small = '<FONT POINT-SIZE="9">{}</FONT>'  # str.format: {} is replaced by the text
    cells = []
    # For each entry: a small square with the colors (border and fill) + the text.
    for entry in graph.legend:
        cells.append(
            f'<TD BORDER="1" STYLE="rounded" COLOR="{entry.color}" '
            f'BGCOLOR="{entry.fillcolor}" WIDTH="14" HEIGHT="10"></TD>'
        )
        cells.append(f'<TD ALIGN="LEFT">{small.format(escape(entry.label))}</TD>')

    # Two strings written next to each other are JOINED by Python (even across lines, inside
    # parentheses): it is only used to stay within 100 characters per line.
    header = f'<TD ALIGN="LEFT">{small.format("<B>Legend</B>")}</TD>'
    return (
        '<TABLE BORDER="1" STYLE="rounded" COLOR="#999999" CELLBORDER="0" CELLSPACING="3">'
        f"<TR>{header}{''.join(cells)}</TR></TABLE>"
    )


def render_svg(graph: Graph, output_file: Path) -> Path:
    """Draw the graph into an SVG file and return its path."""
    # mkdir(parents=True, exist_ok=True): creates the folder (and the ones above, if missing);
    # no error if it already exists. Like std::filesystem::create_directories.
    output_file.parent.mkdir(parents=True, exist_ok=True)
    # pipe() runs dot.exe and returns the result in memory as BYTES (binary data, not text):
    # that is why it is written with write_bytes and not write_text.
    svg = to_dot(graph).pipe(format="svg")
    output_file.write_bytes(svg)
    return output_file
