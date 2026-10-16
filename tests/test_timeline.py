"""Tests for pasta.timeline."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from pasta.loader import InputData, load_excel
from pasta.timeline import Snapshot, take_snapshot

SAMPLE_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_pastificio.xlsx"

# Date chiave dei dati di esempio (progetto "Online shop"):
#   SHOP (WebShop) esiste dal 2027-03-01; SHEETS (fogli Excel) fino al 2027-03-31;
#   la migrazione SHEETS -> SHOP vale dal 2027-03-01 al 2027-03-31;
#   go-live il 2027-04-01: da quel giorno P_ORDERS usa SHOP.
ALL_NODES = {
    "MP_PROD",
    "MP_SALES",
    "P_PLAN",
    "P_ORDERS",
    "P_INVOICE",
    "MILL",
    "BILLING",
    "SHEETS",
    "SHOP",
    "BANK",
}


@pytest.fixture
def data() -> InputData:
    return load_excel(SAMPLE_FILE)


# INSIEMI (set): {a, b, c} è una collezione SENZA ordine e SENZA duplicati, come std::set
# (ma basata su hash, quindi più simile a std::unordered_set). Due insiemi sono uguali se
# contengono gli stessi elementi, in qualunque ordine: perfetto per dire "questi nodi ci
# sono" senza preoccuparsi dell'ordine delle righe.
# Operazioni utili: "x in s" (appartenenza), s1 - s2 (differenza), s1 | s2 (unione).
# ATTENZIONE: {} da solo è un dizionario vuoto; l'insieme vuoto si scrive set().
def node_ids(snapshot: Snapshot) -> set[str]:
    return set(snapshot.nodes["Id"])


def link_pairs(snapshot: Snapshot) -> set[tuple[str, str]]:
    # Un link è identificato qui dalla coppia (Source, Cible). Le tuple possono stare in un
    # insieme perché sono IMMUTABILI (le liste no: un elemento di un set non deve cambiare).
    return set(zip(snapshot.links["Source"], snapshot.links["Cible"], strict=True))


def test_before_the_project(data: InputData) -> None:
    snapshot = take_snapshot(data, date(2026, 10, 8))

    # ALL_NODES - {"SHOP"}: tutti i nodi tranne il WebShop, che non esiste ancora.
    assert node_ids(snapshot) == ALL_NODES - {"SHOP"}
    assert ("P_ORDERS", "SHEETS") in link_pairs(snapshot)
    assert ("P_ORDERS", "SHOP") not in link_pairs(snapshot)


def test_during_the_migration(data: InputData) -> None:
    snapshot = take_snapshot(data, date(2027, 3, 15))

    assert node_ids(snapshot) == ALL_NODES  # vecchio e nuovo sistema insieme
    assert ("SHEETS", "SHOP") in link_pairs(snapshot)  # la freccia di migrazione
    assert ("P_ORDERS", "SHOP") not in link_pairs(snapshot)  # il go-live non c'è ancora


def test_after_the_go_live(data: InputData) -> None:
    snapshot = take_snapshot(data, date(2027, 6, 1))

    assert node_ids(snapshot) == ALL_NODES - {"SHEETS"}
    assert ("P_ORDERS", "SHOP") in link_pairs(snapshot)
    assert ("SHEETS", "SHOP") not in link_pairs(snapshot)


# TEST AI BORDI: gli errori si nascondono spesso proprio sui confini (un "<" al posto di
# "<="). Si prova il primo giorno, l'ultimo giorno, e i giorni subito prima e subito dopo.
# PROVA FATTA ("mutation testing" = rompere il codice apposta per vedere se i test se ne
# accorgono): con ">" al posto di ">=" in _exists_on fallisce SOLO test_last_day_is_included.
# Gli altri test passavano lo stesso, perché nessuna delle loro date cade su una DateFin.
def test_first_day_is_included(data: InputData) -> None:
    assert "SHOP" in node_ids(take_snapshot(data, date(2027, 3, 1)))
    assert "SHOP" not in node_ids(take_snapshot(data, date(2027, 2, 28)))


def test_last_day_is_included(data: InputData) -> None:
    assert "SHEETS" in node_ids(take_snapshot(data, date(2027, 3, 31)))
    assert "SHEETS" not in node_ids(take_snapshot(data, date(2027, 4, 1)))


# PARAMETRIZE: lo stesso test eseguito più volte con valori diversi. pytest lo conta come
# 3 test separati, e se ne fallisce uno dice per quale data. È come un ciclo for, ma ogni
# giro è un test a sé.
@pytest.mark.parametrize("day", [date(2026, 10, 8), date(2027, 3, 15), date(2027, 6, 1)])
def test_inactive_link_is_never_shown(data: InputData, day: date) -> None:
    # MILL -> BILLING ha Actif = False nell'Excel.
    assert ("MILL", "BILLING") not in link_pairs(take_snapshot(data, day))


def test_link_is_hidden_when_one_of_its_nodes_is_hidden() -> None:
    # Dati costruiti a mano: B finisce a giugno 2026, ma il link A -> B (per errore) no.
    start, end = date(2026, 1, 1), date(2100, 12, 31)
    data = InputData(
        nodes=pd.DataFrame(
            [
                {"Id": "A", "Actif": True, "DateDebut": start, "DateFin": end},
                {"Id": "B", "Actif": True, "DateDebut": start, "DateFin": date(2026, 6, 30)},
            ]
        ),
        links=pd.DataFrame(
            [{"Source": "A", "Cible": "B", "Actif": True, "DateDebut": start, "DateFin": end}]
        ),
        projects=pd.DataFrame(),
        parameters={},
    )

    assert link_pairs(take_snapshot(data, date(2026, 5, 1))) == {("A", "B")}
    assert link_pairs(take_snapshot(data, date(2026, 10, 1))) == set()
