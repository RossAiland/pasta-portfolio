"""Turn a snapshot or a comparison into Node and Edge objects with a resolved style."""

from collections import Counter
from dataclasses import dataclass, replace

import pandas as pd

from pasta.timeline import Comparison, Snapshot, Status

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
    # Colori del CONFRONTO tra due date (si possono cambiare dal foglio Parametres):
    # verde = nato tra le due date, rosso = sparito.
    "AddedColor": "#1A9850",
    "AddedFillcolor": "#D9F0D3",
    "RemovedColor": "#D73027",
    "RemovedFillcolor": "#FDDBC7",
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
    # True se le celle Color e Fillcolor erano VUOTE e i colori vengono dai default
    # (es. BANK): serve alla legenda per scrivere "default style".
    uses_default_colors: bool = False
    # Nel confronto tra due date: unchanged / added / removed. In uno snapshot semplice
    # vale sempre UNCHANGED.
    status: Status = Status.UNCHANGED


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
    status: Status = Status.UNCHANGED


# LEGENDA. Cosa spiega (scelta dell'utente): TUTTI I COLORI dei nodi, cioè una voce per ogni
# combinazione "tipo di elemento + colori" che compare nel disegno, nell'ordine dell'Excel.
# Etichetta = il tipo (Macro processus, Processus, Système...). Se lo stesso tipo ha più
# aspetti, si aggiunge:
#   - il DOMINIO, se quel colore appartiene a un solo dominio ("Processus · Production");
#   - "default style", se gli elementi non hanno colori propri ("Système · default style").
# Nel CONFRONTO tra due date si aggiungono in fondo "Added" (verde) e "Removed" (rosso), se
# almeno un nodo o una freccia ha quello stato; i nodi added/removed non vengono contati
# nelle voci per tipo, perché il loro colore è quello dello stato.
# È costruita DAI DATI, non scritta a mano: mostra solo ciò che compare davvero nel grafo,
# così funziona anche con il file reale. Il calcolo sta qui nel modello, così i due
# disegnatori (Graphviz e HTML) mostrano la stessa legenda.
# (Prima versione, poi sostituita su richiesta: colori dei domini + tipi di flusso.)
LEGEND_SEPARATOR = " · "
DEFAULT_STYLE_LABEL = "default style"


@dataclass(frozen=True)
class LegendEntry:
    label: str  # es. "Processus · Production"
    color: str  # bordo
    fillcolor: str  # riempimento


@dataclass(frozen=True)
class Graph:
    title: str
    subtitle: str  # es. "08.10.2026" o "Changes 08.10.2026 → 01.06.2027"
    layout: str  # motore di Graphviz, es. "dot"
    rankdir: str  # direzione: "LR" sinistra -> destra, "TB" alto -> basso
    fontname: str
    # list[Node]: una lista di Node. In C++: std::vector<Node>.
    nodes: list[Node]
    edges: list[Edge]
    legend: list[LegendEntry]  # voci della legenda (vedi sopra)


# "Snapshot | Comparison": il parametro può essere UNO DEI DUE tipi. La funzione usa solo ciò
# che entrambi hanno (.nodes, .links, .subtitle), quindi non deve sapere quale dei due riceve:
# è il "DUCK TYPING" di Python ("se cammina come un'anatra e fa qua qua, è un'anatra").
# In C++ servirebbe una classe base comune o un template.
def build_graph(source: Snapshot | Comparison, parameters: dict[str, object]) -> Graph:
    """Build the Graph of a snapshot or a comparison, filling empty style cells."""
    # Prima si uniscono i due dizionari: i valori di Parametres SOVRASCRIVONO quelli di
    # FALLBACK. "{**a, **b}" crea un nuovo dizionario con le chiavi di a e poi quelle di b
    # (se una chiave è in entrambi vince b). "**" "spacchetta" un dizionario, come "*"
    # spacchetta una lista.
    settings = {**FALLBACK, **parameters}

    # to_dict(orient="records") trasforma la tabella in una LISTA DI DIZIONARI, uno per riga:
    # [{"Id": "MILL", "Shape": "rectangle", ...}, ...]. Così ogni riga si legge con
    # row.get("Colonna"), che restituisce None se la colonna non esiste nel file (invece di
    # dare errore): utile se il file reale non ha tutte le colonne di stile.
    nodes = [_make_node(row, settings) for row in source.nodes.to_dict(orient="records")]
    edges = [_make_edge(row, settings) for row in source.links.to_dict(orient="records")]

    return Graph(
        title=str(settings["GraphLabel"]),
        subtitle=source.subtitle,
        layout=str(settings["Layout"]),
        rankdir=str(settings["Rankdir"]),
        fontname=str(settings["Fontname"]),
        nodes=nodes,
        edges=edges,
        legend=_legend(nodes, edges, settings),
    )


def _legend(nodes: list[Node], edges: list[Edge], settings: dict[str, object]) -> list[LegendEntry]:
    """Return one legend entry per (element type, colors), then Added/Removed if present."""
    # 1. Si raggruppano i nodi per ASPETTO: chiave = (tipo, bordo, riempimento).
    #    setdefault(chiave, []) restituisce la lista di quella chiave e, se la chiave non c'è
    #    ancora, la crea vuota: così si può fare .append() subito, senza un if.
    #    I dizionari conservano l'ORDINE DI INSERIMENTO (da Python 3.7): la legenda elenca le
    #    voci nell'ordine in cui compaiono nell'Excel. (std::map in C++ invece ordina per chiave.)
    #    Una TUPLA può essere chiave di un dizionario perché è immutabile (una lista no).
    #    I nodi added/removed sono esclusi: il loro colore è quello dello stato (punto 4).
    groups: dict[tuple[str, str, str], list[Node]] = {}
    for node in nodes:
        if node.status is Status.UNCHANGED:
            groups.setdefault((node.kind, node.color, node.fillcolor), []).append(node)

    # 2. Quanti aspetti diversi ha ogni tipo? Counter (libreria standard "collections") CONTA
    #    quante volte compare ogni valore: Counter(["Processus", "Processus", "Système"])
    #    -> {"Processus": 2, "Système": 1}.
    #    "for kind, _, _ in groups": scorrere un dizionario dà le sue CHIAVI (qui le tuple),
    #    che spacchettiamo; "_" è il nome convenzionale per "valore che non mi serve".
    looks_per_kind = Counter(kind for kind, _, _ in groups)

    # 3. Una voce per gruppo. .items() dà le coppie (chiave, valore); la chiave è a sua volta
    #    una tupla, spacchettata con le parentesi: ((kind, color, fillcolor), members).
    entries = [
        LegendEntry(_legend_label(kind, members, looks_per_kind[kind] > 1), color, fillcolor)
        for (kind, color, fillcolor), members in groups.items()
    ]

    # 4. Le voci degli stati, solo se almeno un nodo o una freccia ha quello stato.
    #    any(...) è True se la condizione vale per ALMENO UN elemento.
    #    [*nodes, *edges]: una lista nuova con tutti i nodi e poi tutte le frecce.
    for status, label in [(Status.ADDED, "Added"), (Status.REMOVED, "Removed")]:
        if any(item.status is status for item in [*nodes, *edges]):
            color, fillcolor = _status_colors(status, settings)
            entries.append(LegendEntry(label, color, fillcolor))
    return entries


def _legend_label(kind: str, members: list[Node], kind_has_several_looks: bool) -> str:
    """Return the legend text of a group of nodes that look the same."""
    # all(...) è True se la condizione vale per TUTTI gli elementi (any(...): per almeno uno).
    # Come std::all_of / std::any_of in C++.
    if all(node.uses_default_colors for node in members):
        return f"{kind}{LEGEND_SEPARATOR}{DEFAULT_STYLE_LABEL}"
    if kind_has_several_looks:
        # SET COMPREHENSION: l'insieme dei domini del gruppo, senza duplicati.
        domains = {node.domain for node in members}
        if len(domains) == 1 and None not in domains:
            # next(iter(insieme)) = l'unico elemento dell'insieme (un set non ha posizioni [0]).
            return f"{kind}{LEGEND_SEPARATOR}{next(iter(domains))}"
    return kind


def _status_colors(status: Status, settings: dict[str, object]) -> tuple[str, str]:
    """Return (border color, fill color) of an added or removed element."""
    # status.value è il testo dell'Enum ("added"); .capitalize() mette la prima lettera
    # maiuscola ("Added"), così si costruisce il nome del parametro: "AddedColor".
    prefix = status.value.capitalize()
    return str(settings[f"{prefix}Color"]), str(settings[f"{prefix}Fillcolor"])


def _make_node(row: dict, settings: dict[str, object]) -> Node:
    # str(...) e float(...) sono CONVERSIONI esplicite (come static_cast in C++):
    # - garantiscono il tipo promesso dalla dataclass (un Id numerico come 12 diventa "12";
    #   lo spessore 1 letto dall'Excel diventa 1.0);
    # - dicono a VSCode che tipo esce, visto che i valori del dizionario sono "object".
    node = Node(
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
        # "and" tra due booleani: True solo se ENTRAMBE le celle di colore sono vuote.
        uses_default_colors=bool(pd.isna(row.get("Color")) and pd.isna(row.get("Fillcolor"))),
        # row.get(chiave, default): se la colonna Status non c'è (snapshot semplice), UNCHANGED.
        status=row.get("Status", Status.UNCHANGED),
    )
    if node.status is Status.UNCHANGED:
        return node
    # STILE DI STATO: i colori dello stato sostituiscono quelli della riga, bordo più spesso;
    # un nodo removed ha anche il bordo tratteggiato (Graphviz accetta più stili separati da
    # virgola, es. "rounded,filled,dashed").
    # dataclasses.REPLACE crea una COPIA dell'oggetto con alcuni campi cambiati: è il modo di
    # "modificare" una dataclass frozen (l'originale non cambia).
    # "is" per confrontare valori di un Enum: ogni valore esiste una sola volta (come None).
    color, fillcolor = _status_colors(node.status, settings)
    style = f"{node.style},dashed" if node.status is Status.REMOVED else node.style
    return replace(node, color=color, fillcolor=fillcolor, style=style, penwidth=2.0)


def _make_edge(row: dict, settings: dict[str, object]) -> Edge:
    edge = Edge(
        source=str(row["Source"]),
        target=str(row["Cible"]),
        label=_text_or_none(row.get("Libelle")),
        style=str(_cell_or(row.get("Style"), settings["EdgeDefaultStyle"])),
        color=str(_cell_or(row.get("Color"), settings["EdgeDefaultColor"])),
        penwidth=float(_cell_or(row.get("Penwidth"), settings["EdgeDefaultPenwidth"])),
        direction=str(_cell_or(row.get("Direction"), "forward")),
        flow_type=_text_or_none(row.get("TypeFlux")),
        data=_text_or_none(row.get("Données")),
        status=row.get("Status", Status.UNCHANGED),
    )
    if edge.status is Status.UNCHANGED:
        return edge
    # Freccia added: verde e più spessa. Removed: rossa, più spessa e tratteggiata.
    color, _ = _status_colors(edge.status, settings)  # "_": il riempimento non serve
    style = "dashed" if edge.status is Status.REMOVED else edge.style
    return replace(edge, color=color, style=style, penwidth=2.0)


def _cell_or(value: object, default: object) -> object:
    """Return the cell value, or the default if the cell is empty (None or NaN)."""
    # pd.isna riconosce sia None (colonna assente, row.get) sia NaN (cella vuota).
    return default if pd.isna(value) else value


def _text_or_none(value: object) -> str | None:
    """Return the cell as text, or None if it is empty."""
    return None if pd.isna(value) else str(value)
