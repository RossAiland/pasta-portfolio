"""Choose the nodes and links that exist at a given date."""

from dataclasses import dataclass
from datetime import date

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
