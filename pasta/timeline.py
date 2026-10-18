"""Choose the nodes and links that exist at a given date, and compare two dates."""

from dataclasses import dataclass
from datetime import date
from enum import Enum

import pandas as pd

from pasta.loader import InputData

# REGOLA: una riga (nodo o link) esiste in un giorno se
#     Actif è True  E  DateDebut <= giorno <= DateFin
# con ENTRAMBI i confini inclusi: il giorno di DateDebut esiste già, il giorno di DateFin
# esiste ancora (per questo il vecchio sistema finisce il giorno PRIMA del go-live).
# In più un link esiste solo se esistono ENTRAMBI i suoi nodi: altrimenti Graphviz
# disegnerebbe una freccia verso un nodo che non c'è (anzi, lo creerebbe vuoto).
#
# Questo modulo lavora su dati GIÀ VALIDATI (validation.py): Actif è sempre True/False e
# le date non sono mai vuote, quindi qui non serve ricontrollarli.


@dataclass
class Snapshot:
    """The nodes and links visible on one day: a 'photo' of the company."""

    day: date
    nodes: pd.DataFrame
    links: pd.DataFrame

    # PROPRIETÀ: un metodo che si usa COME UN CAMPO, senza parentesi: snapshot.subtitle
    # (non snapshot.subtitle()). Il valore viene calcolato ogni volta dai campi.
    # @property è un decoratore, come @dataclass. In C++ sarebbe un metodo getter const.
    @property
    def subtitle(self) -> str:
        """Text shown under the title of the drawing."""
        # FORMATO DELLA DATA nella f-string: dopo ":" si scrive come formattarla.
        # %d = giorno, %m = mese, %Y = anno a 4 cifre -> "08.10.2026" (formato svizzero).
        # In C++ sarebbe std::format("{:%d.%m.%Y}", day).
        return f"{self.day:%d.%m.%Y}"


# ---------------------------------------------------------------------------------------
# Confronto tra due date
# ---------------------------------------------------------------------------------------
# ALGORITMO (teoria degli insiemi): prima = chiavi esistenti alla data "before",
# dopo = chiavi esistenti alla data "after".
#   unchanged = prima & dopo   (intersezione: c'è in entrambe)
#   added     = dopo - prima   (differenza: c'è solo dopo)
#   removed   = prima - dopo   (c'è solo prima)
# CHIAVI: un nodo è identificato dal suo Id; un link dalla tupla (Source, Cible, TypeFlux)
# (i link non hanno un Id nell'Excel).


# ENUM: un insieme CHIUSO di valori con un nome, come "enum class" in C++. Rispetto alle
# stringhe evita errori di battitura: Status.ADDED scritto male dà subito un errore, mentre
# "addded" passerebbe inosservato. Il valore ("added") serve quando va mostrato come testo.
class Status(Enum):
    UNCHANGED = "unchanged"
    ADDED = "added"
    REMOVED = "removed"


NODE_KEY = ["Id"]
LINK_KEY = ["Source", "Cible", "TypeFlux"]


@dataclass
class Comparison:
    """The union of two snapshots, with a "Status" column on every node and link."""

    before: date
    after: date
    nodes: pd.DataFrame
    links: pd.DataFrame

    @property
    def subtitle(self) -> str:
        """Text shown under the title of the drawing."""
        # "→" è il carattere freccia →, scritto con il suo codice Unicode.
        return f"Changes {self.before:%d.%m.%Y} → {self.after:%d.%m.%Y}"


def compare(data: InputData, before: date, after: date) -> Comparison:
    """Return what is unchanged, added and removed between two dates."""
    old = take_snapshot(data, before)
    new = take_snapshot(data, after)
    return Comparison(
        before=before,
        after=after,
        nodes=_union_with_status(old.nodes, new.nodes, NODE_KEY),
        links=_union_with_status(old.links, new.links, LINK_KEY),
    )


def _keys(table: pd.DataFrame, key: list[str]) -> list[tuple]:
    """Return the key of every row, as a tuple (one per row, in the same order)."""
    # fillna(""): una cella vuota (NaN) nella chiave diventa "". Serve perché NaN != NaN:
    # due link con TypeFlux vuoto non risulterebbero "uguali" in un insieme.
    # itertuples(index=False, name=None) dà ogni riga come una TUPLA semplice di valori.
    return list(table[key].fillna("").itertuples(index=False, name=None))


def _union_with_status(old: pd.DataFrame, new: pd.DataFrame, key: list[str]) -> pd.DataFrame:
    """Return the rows of new (unchanged or added) and of old (removed), with a Status."""
    old_keys = set(_keys(old, key))
    new_keys = set(_keys(new, key))

    # Righe di "dopo": unchanged se la chiave c'era anche prima, altrimenti added.
    # (Per le righe unchanged teniamo quella di "dopo": è lo stato più recente.)
    new_status = [
        Status.UNCHANGED if row_key in old_keys else Status.ADDED for row_key in _keys(new, key)
    ]
    # Righe di "prima" la cui chiave NON c'è più dopo: removed.
    # Maschera da una lista di booleani: pd.Series(lista, index=...) usa gli stessi indici
    # della tabella, così .loc[maschera] seleziona le righe giuste.
    gone = pd.Series([row_key not in new_keys for row_key in _keys(old, key)], index=old.index)
    removed = old.loc[gone]

    # assign(Colonna=valori) restituisce una NUOVA tabella con la colonna in più.
    # pd.concat([a, b]) mette le due tabelle una sotto l'altra (come unire due vector);
    # ignore_index=True rinumera le righe 0, 1, 2... (gli indici originali qui non servono).
    return pd.concat(
        [new.assign(Status=new_status), removed.assign(Status=Status.REMOVED)],
        ignore_index=True,
    )


def take_snapshot(data: InputData, day: date) -> Snapshot:
    """Return the nodes and links that exist on the given day."""
    # .loc[maschera] tiene solo le righe in cui la maschera vale True (e conserva gli indici).
    nodes = data.nodes.loc[_exists_on(data.nodes, day)]
    links = data.links.loc[_exists_on(data.links, day)]

    # isin(nodes["Id"]): True se Source (o Cible) è tra gli Id dei nodi VISIBILI.
    # Il link resta solo se lo sono entrambi.
    both_ends_visible = links["Source"].isin(nodes["Id"]) & links["Cible"].isin(nodes["Id"])
    links = links.loc[both_ends_visible]

    return Snapshot(day=day, nodes=nodes, links=links)


def _exists_on(table: pd.DataFrame, day: date) -> pd.Series:
    """Return a mask: True for the rows that exist on the given day."""
    # CONFRONTO VETTORIALE: "colonna <= day" confronta OGNI cella della colonna con la stessa
    # data e restituisce una maschera di True/False (una per riga), senza scrivere un ciclo.
    # astype(bool): dopo il loader la colonna Actif può avere dtype "object" (contenitore
    # generico); per combinarla con "&" la vogliamo di dtype bool vero e proprio.
    # Le tre condizioni sono combinate con "&" (and elemento per elemento). Ognuna ha la sua
    # variabile, così si leggono meglio. Scritte in una riga sola, ogni confronto andrebbe
    # tra PARENTESI, perché "&" ha precedenza più alta di "<=" e ">=":
    #     active & (table["DateDebut"] <= day) & (table["DateFin"] >= day)
    active = table["Actif"].astype(bool)
    started = table["DateDebut"] <= day
    not_ended = table["DateFin"] >= day
    return active & started & not_ended
