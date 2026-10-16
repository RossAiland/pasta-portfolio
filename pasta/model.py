"""Turn a snapshot (pandas tables) into simple Node and Edge objects with a resolved style."""

from dataclasses import dataclass
from datetime import date

import pandas as pd

from pasta.timeline import Snapshot

# PERCHÉ QUESTO MODULO: i due "disegnatori" (Graphviz al passo 7, HTML interattivo al
# passo 10) ricevono lo STESSO elenco di Node/Edge e non devono sapere nulla di pandas,
# NaN o valori di default. È l'idea "un'interfaccia, due implementazioni" del C++:
# il modello è l'interfaccia comune, i disegnatori le implementazioni.
#
# REGOLA DELLO STILE, per ogni cella (es. il colore di un nodo):
#   1. il valore della cella, se c'è;
#   2. altrimenti il default del foglio Parametres (es. NodeDefaultColor);
#   3. se manca anche quello, il valore di riserva scritto qui sotto (FALLBACK).
# Il livello 3 serve per la Tappa 2: se il file reale non ha un parametro, il programma
# funziona lo stesso.
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
}


# frozen=True: una volta creati, nodi e frecce non cambiano (come campi const in C++).
@dataclass(frozen=True)
class Node:
    id: str
    label: str
    kind: str  # TypeElement: "Macro processus", "Processus", "Système"...
    shape: str
    style: str
    color: str  # bordo
    fillcolor: str  # riempimento
    penwidth: float  # spessore del bordo
    domain: str | None = None
    project: str | None = None


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    label: str | None
    style: str  # "solid", "dashed", "dotted"
    color: str
    penwidth: float
    direction: str = "forward"  # "forward" = freccia da source a target, "both" = due punte
    flow_type: str | None = None
    data: str | None = None  # colonna "Données": quali dati passano (utile come tooltip)


@dataclass(frozen=True)
class Graph:
    title: str
    day: date
    layout: str  # motore di Graphviz, es. "dot"
    rankdir: str  # direzione: "LR" sinistra -> destra, "TB" alto -> basso
    fontname: str
    # list[Node]: una lista di Node. In C++: std::vector<Node>.
    nodes: list[Node]
    edges: list[Edge]


def build_graph(snapshot: Snapshot, parameters: dict[str, object]) -> Graph:
    """Build the Graph of one snapshot, filling empty style cells with the defaults."""
    # Prima si uniscono i due dizionari: i valori di Parametres SOVRASCRIVONO quelli di
    # FALLBACK. "{**a, **b}" crea un nuovo dizionario con le chiavi di a e poi quelle di b
    # (se una chiave è in entrambi vince b). "**" "spacchetta" un dizionario, come "*"
    # spacchetta una lista.
    settings = {**FALLBACK, **parameters}

    # to_dict(orient="records") trasforma la tabella in una LISTA DI DIZIONARI, uno per riga:
    # [{"Id": "MILL", "Shape": "rectangle", ...}, ...]. Così ogni riga si legge con
    # row.get("Colonna"), che restituisce None se la colonna non esiste nel file (invece di
    # dare errore): utile se il file reale non ha tutte le colonne di stile.
    nodes = [_make_node(row, settings) for row in snapshot.nodes.to_dict(orient="records")]
    edges = [_make_edge(row, settings) for row in snapshot.links.to_dict(orient="records")]

    return Graph(
        title=str(settings["GraphLabel"]),
        day=snapshot.day,
        layout=str(settings["Layout"]),
        rankdir=str(settings["Rankdir"]),
        fontname=str(settings["Fontname"]),
        nodes=nodes,
        edges=edges,
    )


def _make_node(row: dict, settings: dict[str, object]) -> Node:
    # str(...) e float(...) sono CONVERSIONI esplicite (come static_cast in C++):
    # - garantiscono il tipo promesso dalla dataclass (un Id numerico come 12 diventa "12";
    #   lo spessore 1 letto dall'Excel diventa 1.0);
    # - dicono a VSCode che tipo esce, visto che i valori del dizionario sono "object".
    return Node(
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
    )


def _make_edge(row: dict, settings: dict[str, object]) -> Edge:
    return Edge(
        source=str(row["Source"]),
        target=str(row["Cible"]),
        label=_text_or_none(row.get("Libelle")),
        style=str(_cell_or(row.get("Style"), settings["EdgeDefaultStyle"])),
        color=str(_cell_or(row.get("Color"), settings["EdgeDefaultColor"])),
        penwidth=float(_cell_or(row.get("Penwidth"), settings["EdgeDefaultPenwidth"])),
        direction=str(_cell_or(row.get("Direction"), "forward")),
        flow_type=_text_or_none(row.get("TypeFlux")),
        data=_text_or_none(row.get("Données")),
    )


def _cell_or(value: object, default: object) -> object:
    """Return the cell value, or the default if the cell is empty (None or NaN)."""
    # pd.isna riconosce sia None (colonna assente, row.get) sia NaN (cella vuota).
    return default if pd.isna(value) else value


def _text_or_none(value: object) -> str | None:
    """Return the cell as text, or None if it is empty."""
    return None if pd.isna(value) else str(value)
