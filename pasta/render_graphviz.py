"""Draw a Graph as a static image (SVG) with Graphviz."""

from html import escape
from pathlib import Path

import graphviz

from pasta.model import Graph

# COME FUNZIONA GRAPHVIZ: è un programma ESTERNO (dot.exe, installato a parte) che riceve
# la descrizione di un grafo in un linguaggio di testo, il DOT, e calcola da solo dove
# mettere ogni nodo (il "layout"). Esempio di DOT:
#     digraph {
#         rankdir=LR
#         MILL [label="MillControl" shape=rectangle color="#F03B20"]
#         P_PLAN -> MILL
#     }
# La libreria Python "graphviz" serve a COSTRUIRE questo testo con delle funzioni
# (dot.node, dot.edge) e a chiamare dot.exe per trasformarlo in SVG.
#
# DUE FUNZIONI SEPARATE:
# - to_dot(graph): costruisce il DOT. Si testa SENZA eseguire Graphviz (basta controllare
#   il testo prodotto, dot.source);
# - render_svg(graph, file): chiama dot.exe e scrive il file.
#
# La libreria protegge da sola virgolette e caratteri speciali (& < >) nelle etichette, e un
# a capo "\n" diventa una seconda riga di testo: non serve fare nulla di particolare.


def to_dot(graph: Graph) -> graphviz.Digraph:
    """Build the Graphviz description (DOT) of the graph."""
    # Digraph = grafo ORIENTATO (con frecce). engine = quale algoritmo di layout usare
    # ("dot" = gerarchico, a livelli: adatto a processi -> sistemi).
    dot = graphviz.Digraph(name="pasta", engine=graph.layout)

    # dot.attr(...) imposta gli attributi di tutto il grafo. In Graphviz tutti i valori sono
    # TESTO, per questo i numeri vengono passati con str(...).
    # L'etichetta del grafo contiene il titolo e la legenda (vedi _title_and_legend);
    # labelloc="t" la mette in alto (top).
    dot.attr(
        rankdir=graph.rankdir,
        label=_title_and_legend(graph),
        labelloc="t",
        fontname=graph.fontname,
    )
    # dot.attr("node", ...) / dot.attr("edge", ...) = valori comuni a tutti i nodi / frecce.
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
            # tooltip = testo che appare passando il mouse sul nodo nel browser.
            # "a or b" restituisce a se è "vero" (non None, non vuoto), altrimenti b: qui
            # node.domain, oppure "" se il dominio manca.
            tooltip=f"{node.kind} - {node.domain or ''}",
        )

    for edge in graph.edges:
        # Gli attributi della freccia vanno in un dizionario, perché alcuni ci sono solo
        # quando servono (label, tooltip): Graphviz non vuole valori vuoti.
        attributes = {
            "style": edge.style,
            "color": edge.color,
            "penwidth": str(edge.penwidth),
            "dir": edge.direction,  # "forward" = una punta, "both" = due punte
        }
        if edge.label:  # None (o testo vuoto) vale False: niente etichetta
            attributes["label"] = edge.label
        if edge.data:
            attributes["tooltip"] = edge.data
        # **attributes "SPACCHETTA" il dizionario in argomenti con nome: è come scrivere
        # dot.edge(source, target, style=..., color=..., ...). (Visto con {**a, **b} in model.py.)
        dot.edge(edge.source, edge.target, **attributes)

    return dot


# LEGENDA: PERCHÉ IN UNA TABELLA HTML SOTTO IL TITOLO.
# Prima versione (provata e scartata): un riquadro fatto di nodi dentro il grafo (un
# sottografo "cluster_legend"). Graphviz lo tratta come parte del grafo: lo mette dove vuole,
# e per spostarlo a destra servivano frecce invisibili che ROVINAVANO la disposizione dei
# nodi veri (es. Bank finiva sotto la legenda).
# Soluzione: l'etichetta del grafo (il titolo) può essere una TABELLA HTML. Lì la legenda
# NON partecipa al layout, quindi non sposta nulla.
# Ogni voce è un quadratino con i colori (bordo e riempimento) + il testo; le voci le
# calcola model.py (tutti i colori dei nodi: tipo, e se serve dominio o "default style").
# (Una versione precedente mostrava anche linee campione per i tipi di flusso, disegnate
# come bordo inferiore di una cella, SIDES="B", anche tratteggiato: tolta su richiesta.)
#
# ETICHETTE HTML: in Graphviz un'etichetta scritta tra < > (invece che tra virgolette) è
# "HTML-like": si possono usare <TABLE>, <TR> (riga), <TD> (cella), <FONT>, <BR/> (a capo).
# Nel testo dei dati i caratteri speciali (& < >) vanno PROTETTI con html.escape: un
# dominio come "R&D" altrimenti romperebbe la tabella.


def _title_and_legend(graph: Graph) -> str:
    """Return the HTML-like label of the graph: title, date and legend."""
    # Sotto il titolo: la data dello snapshot, oppure "Changes <prima> → <dopo>" per un
    # confronto (il testo lo prepara timeline.py, proprietà subtitle).
    title_lines = [*graph.title.split("\n"), graph.subtitle]
    # [*lista, altro]: "*" spacchetta la lista dentro una lista nuova (come {**a} per i dict).
    title = "<BR/>".join(escape(line) for line in title_lines)

    rows = [f'<TR><TD><FONT POINT-SIZE="14">{title}</FONT></TD></TR>']
    legend = _legend_table(graph)
    if legend:
        rows.append(f"<TR><TD>{legend}</TD></TR>")
    # Le parentesi < > ESTERNE dicono a Graphviz "questa è un'etichetta HTML".
    return f'<<TABLE BORDER="0" CELLSPACING="4">{"".join(rows)}</TABLE>>'


def _legend_table(graph: Graph) -> str:
    """Return the legend as an HTML table on one row, or "" if there is nothing to explain."""
    if not graph.legend:
        return ""  # niente da spiegare: niente legenda

    small = '<FONT POINT-SIZE="9">{}</FONT>'  # str.format: {} viene sostituito dal testo
    cells = []
    # Per ogni voce: un quadratino con i colori (bordo e riempimento) + il testo.
    for entry in graph.legend:
        cells.append(
            f'<TD BORDER="1" STYLE="rounded" COLOR="{entry.color}" '
            f'BGCOLOR="{entry.fillcolor}" WIDTH="14" HEIGHT="10"></TD>'
        )
        cells.append(f'<TD ALIGN="LEFT">{small.format(escape(entry.label))}</TD>')

    # Due stringhe scritte una accanto all'altra vengono UNITE da Python (anche su più righe,
    # dentro parentesi): serve solo a non superare i 100 caratteri per riga.
    header = f'<TD ALIGN="LEFT">{small.format("<B>Legend</B>")}</TD>'
    return (
        '<TABLE BORDER="1" STYLE="rounded" COLOR="#999999" CELLBORDER="0" CELLSPACING="3">'
        f"<TR>{header}{''.join(cells)}</TR></TABLE>"
    )


def render_svg(graph: Graph, output_file: Path) -> Path:
    """Draw the graph into an SVG file and return its path."""
    # mkdir(parents=True, exist_ok=True): crea la cartella (e quelle sopra, se mancano);
    # se esiste già non dà errore. Come std::filesystem::create_directories.
    output_file.parent.mkdir(parents=True, exist_ok=True)
    # pipe() esegue dot.exe e restituisce il risultato in memoria come BYTES (dati binari,
    # non testo): per questo si scrive con write_bytes e non con write_text.
    svg = to_dot(graph).pipe(format="svg")
    output_file.write_bytes(svg)
    return output_file
