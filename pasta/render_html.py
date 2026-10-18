"""Draw a Graph as an interactive web page (HTML) with pyvis."""

import json
import re
from html import escape
from pathlib import Path

from pyvis.network import Network

from pasta.model import Graph

# HOW PYVIS WORKS: it is a Python library that generates an HTML page containing VIS.JS,
# a JavaScript library that draws graphs in the browser. In the browser you can zoom
# (mouse wheel), drag the nodes and the graph, and hover to see the tooltips.
# cdn_resources="in_line": all of vis.js' JavaScript is COPIED into the file, so the HTML is
# self-contained (it opens offline and can be sent by email). It weighs about 700 KB.
#
# ONE INTERFACE, TWO IMPLEMENTATIONS: this module receives THE SAME Graph as
# render_graphviz.py and translates it into vis.js' "language". Timeline and model were not
# touched: proof that the separation made with model.py works.

# Graphviz shapes -> vis.js shapes. Unknown shapes become "box" (.get with a default).
SHAPES = {"rectangle": "box", "box": "box", "ellipse": "ellipse", "circle": "circle"}
# Graphviz rankdir -> direction of vis.js' hierarchical layout (UD = up-down, etc.).
DIRECTIONS = {"LR": "LR", "RL": "RL", "TB": "UD", "BT": "DU"}

# The pyvis template loads BOOTSTRAP (a styling library) from the internet even with
# "in_line": it is only used for a decorative border. We remove it, so the page makes no
# request to external sites.
# REGULAR EXPRESSION (standard library module "re"): a text "pattern" to search for.
#   <(link|script)  = "<link" or "<script"
#   [^>]*           = any character except ">", repeated (i.e. the rest of the tag)
#   bootstrap       = must contain the word "bootstrap"
#   (\s*</script>)? = possibly followed by spaces and "</script>" (? = optional)
# re.compile prepares the pattern once; .sub("", text) replaces every match with ""
# (i.e. deletes it). In C++: std::regex and std::regex_replace.
BOOTSTRAP_TAGS = re.compile(r"<(link|script)[^>]*bootstrap[^>]*>(\s*</script>)?")


def to_html(graph: Graph) -> str:
    """Build the interactive web page of the graph."""
    # height="85vh": 85% of the height of the browser window (vh = viewport height).
    net = Network(height="85vh", width="100%", directed=True, cdn_resources="in_line")

    for node in graph.nodes:
        net.add_node(
            node.id,
            label=node.label,
            shape=SHAPES.get(node.shape, "box"),
            # In vis.js the color of a node is a DICTIONARY: border and background.
            color={"border": node.color, "background": node.fillcolor},
            borderWidth=node.penwidth,
            shapeProperties={
                # "x in text": True if x is contained in the string (e.g. "rounded,filled").
                "borderDashes": "dashed" in node.style,  # removed node: dashed border
                "borderRadius": 6 if "rounded" in node.style else 0,  # rounded corners
            },
            title=f"{node.kind} - {node.domain or ''}",  # tooltip
            font={"face": graph.fontname},
        )

    for edge in graph.edges:
        net.add_edge(
            edge.source,
            edge.target,
            label=edge.label or "",
            color=edge.color,
            width=edge.penwidth,
            dashes=edge.style in ("dashed", "dotted"),  # "in" on a tuple: is it one of these?
            arrows="to, from" if edge.direction == "both" else "to",
            title=edge.data or "",  # tooltip
            font={"face": graph.fontname, "size": 11},
        )

    # vis.js OPTIONS are passed as JSON text. json.dumps turns a Python dictionary into JSON:
    # True becomes true, None becomes null...
    options = {
        "layout": {
            "hierarchical": {
                "enabled": True,  # in levels, like Graphviz "dot"
                "direction": DIRECTIONS.get(graph.rankdir, "LR"),
                "sortMethod": "directed",  # levels follow the direction of the arrows
                "levelSeparation": 220,
                "nodeSpacing": 110,
            }
        },
        "physics": {"enabled": False},  # nodes stay where the layout puts them
        "edges": {"smooth": {"type": "cubicBezier", "forceDirection": "horizontal"}},
        "interaction": {"hover": True},  # highlight what is under the mouse
    }
    net.set_options(json.dumps(options))

    html = BOOTSTRAP_TAGS.sub("", net.generate_html())
    # Title and legend at the top of the page: right after the <body> tag (count=1: only the
    # first one).
    return html.replace("<body>", "<body>\n" + _header(graph), 1)


def _header(graph: Graph) -> str:
    """Return the HTML block shown above the graph: title, subtitle and legend."""
    # Here too, text coming from the data must be escaped with html.escape (& < > ").
    title = "<br>".join(escape(line) for line in graph.title.split("\n"))

    # A legend entry = a small colored square + the text, as in the SVG drawing.
    items = "".join(
        '<span class="pasta-item">'
        f'<span class="pasta-swatch" style="border-color:{escape(entry.color)};'
        f'background:{escape(entry.fillcolor)}"></span>{escape(entry.label)}</span>'
        for entry in graph.legend
    )
    legend = f'<div class="pasta-legend"><b>Legend</b>{items}</div>' if graph.legend else ""

    # Multi-line string with """...""": here a piece of HTML with some CSS (the page style).
    # The CSS curly braces must be DOUBLED ({{ }}) inside an f-string, otherwise Python would
    # take them for an expression to insert.
    return f"""
<style>
  .pasta-header {{ font-family: {escape(graph.fontname)}, sans-serif; text-align: center; }}
  .pasta-header h2 {{ margin: 8px 0 0 0; }}
  .pasta-header p {{ margin: 2px 0 8px 0; }}
  .pasta-legend {{ display: inline-flex; flex-wrap: wrap; gap: 14px; align-items: center;
                   border: 1px solid #999; border-radius: 8px; padding: 4px 12px;
                   font-size: 12px; }}
  .pasta-item {{ display: inline-flex; align-items: center; gap: 4px; }}
  .pasta-swatch {{ width: 14px; height: 10px; border: 1px solid; border-radius: 3px; }}
</style>
<div class="pasta-header">
  <h2>{title}</h2>
  <p>{escape(graph.subtitle)}</p>
  {legend}
</div>
"""


def render_html(graph: Graph, output_file: Path) -> Path:
    """Write the interactive web page of the graph and return its path."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    # Here the result is TEXT (not bytes as for the SVG): it is written with write_text, in
    # UTF-8 so that accents ("Système") stay correct.
    output_file.write_text(to_html(graph), encoding="utf-8")
    return output_file
