"""Draw a Graph as an interactive web page (HTML) with pyvis."""

import json
import re
from html import escape
from pathlib import Path

from pyvis.network import Network

from pasta.model import Graph

# COME FUNZIONA PYVIS: è una libreria Python che genera una pagina HTML con dentro VIS.JS,
# una libreria JavaScript che disegna grafi nel browser. Nel browser si può fare zoom
# (rotella), trascinare i nodi e il grafo, e passare il mouse per vedere i tooltip.
# cdn_resources="in_line": tutto il JavaScript di vis.js viene COPIATO nel file, quindi
# l'HTML è autonomo (si apre anche offline e si può mandare per email). Pesa circa 700 KB.
#
# UN'INTERFACCIA, DUE IMPLEMENTAZIONI: questo modulo riceve LO STESSO Graph di
# render_graphviz.py e lo traduce nel "linguaggio" di vis.js. Timeline e modello non sono
# stati toccati: è la prova che la separazione fatta con model.py funziona.

# Forme di Graphviz -> forme di vis.js. Le forme sconosciute diventano "box" (.get con default).
SHAPES = {"rectangle": "box", "box": "box", "ellipse": "ellipse", "circle": "circle"}
# rankdir di Graphviz -> direzione del layout gerarchico di vis.js (UD = up-down, ecc.).
DIRECTIONS = {"LR": "LR", "RL": "RL", "TB": "UD", "BT": "DU"}

# Il template di pyvis carica BOOTSTRAP (una libreria di stili) da internet anche con
# "in_line": serve solo a un bordo decorativo. Lo togliamo, così la pagina non fa nessuna
# richiesta a siti esterni.
# ESPRESSIONE REGOLARE (modulo "re" della libreria standard): un "modello" di testo da cercare.
#   <(link|script)  = "<link" oppure "<script"
#   [^>]*           = qualsiasi carattere tranne ">", ripetuto (cioè il resto del tag)
#   bootstrap       = deve contenere la parola "bootstrap"
#   (\s*</script>)? = eventualmente seguito da spazi e "</script>" (? = facoltativo)
# re.compile prepara il modello una volta sola; .sub("", testo) sostituisce ogni occorrenza
# con "" (cioè la cancella). In C++: std::regex e std::regex_replace.
BOOTSTRAP_TAGS = re.compile(r"<(link|script)[^>]*bootstrap[^>]*>(\s*</script>)?")


def to_html(graph: Graph) -> str:
    """Build the interactive web page of the graph."""
    # height="85vh": l'85% dell'altezza della finestra del browser (vh = viewport height).
    net = Network(height="85vh", width="100%", directed=True, cdn_resources="in_line")

    for node in graph.nodes:
        net.add_node(
            node.id,
            label=node.label,
            shape=SHAPES.get(node.shape, "box"),
            # In vis.js il colore di un nodo è un DIZIONARIO: bordo e sfondo.
            color={"border": node.color, "background": node.fillcolor},
            borderWidth=node.penwidth,
            shapeProperties={
                # "x in testo": True se x è contenuto nella stringa (es. "rounded,filled").
                "borderDashes": "dashed" in node.style,  # nodo removed: bordo tratteggiato
                "borderRadius": 6 if "rounded" in node.style else 0,  # angoli arrotondati
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
            dashes=edge.style in ("dashed", "dotted"),  # "in" su una tupla: è uno di questi?
            arrows="to, from" if edge.direction == "both" else "to",
            title=edge.data or "",  # tooltip
            font={"face": graph.fontname, "size": 11},
        )

    # Le OPZIONI di vis.js si passano come testo JSON. json.dumps trasforma un dizionario
    # Python in JSON: True diventa true, None diventa null...
    options = {
        "layout": {
            "hierarchical": {
                "enabled": True,  # a livelli, come Graphviz "dot"
                "direction": DIRECTIONS.get(graph.rankdir, "LR"),
                "sortMethod": "directed",  # i livelli seguono il verso delle frecce
                "levelSeparation": 220,
                "nodeSpacing": 110,
            }
        },
        "physics": {"enabled": False},  # i nodi restano dove li mette il layout
        "edges": {"smooth": {"type": "cubicBezier", "forceDirection": "horizontal"}},
        "interaction": {"hover": True},  # evidenzia ciò che sta sotto il mouse
    }
    net.set_options(json.dumps(options))

    html = BOOTSTRAP_TAGS.sub("", net.generate_html())
    # Titolo e legenda in cima alla pagina: subito dopo il tag <body> (count=1: solo il primo).
    return html.replace("<body>", "<body>\n" + _header(graph), 1)


def _header(graph: Graph) -> str:
    """Return the HTML block shown above the graph: title, subtitle and legend."""
    # Anche qui i testi che vengono dai dati vanno protetti con html.escape (& < > ").
    title = "<br>".join(escape(line) for line in graph.title.split("\n"))

    # Una voce di legenda = un quadratino colorato + il testo, come nel disegno SVG.
    items = "".join(
        '<span class="pasta-item">'
        f'<span class="pasta-swatch" style="border-color:{escape(entry.color)};'
        f'background:{escape(entry.fillcolor)}"></span>{escape(entry.label)}</span>'
        for entry in graph.legend
    )
    legend = f'<div class="pasta-legend"><b>Legend</b>{items}</div>' if graph.legend else ""

    # Stringa su più righe con """...""": qui è un pezzo di HTML con un po' di CSS (lo stile
    # della pagina). Le parentesi graffe del CSS vanno RADDOPPIATE ({{ }}) dentro una f-string,
    # altrimenti Python le scambierebbe per un'espressione da inserire.
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
    # Qui il risultato è TESTO (non bytes come per l'SVG): si scrive con write_text, in UTF-8
    # così gli accenti ("Système") restano corretti.
    output_file.write_text(to_html(graph), encoding="utf-8")
    return output_file
