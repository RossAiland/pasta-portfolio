"""Tests for pasta.timeline."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from pasta.loader import InputData, load_excel
from pasta.timeline import Comparison, Snapshot, Status, compare, take_snapshot

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


# --- Confronto tra due date ------------------------------------------------------------

BEFORE, AFTER = date(2026, 10, 8), date(2027, 6, 1)


def ids_with(comparison: Comparison, status: Status) -> set[str]:
    nodes = comparison.nodes
    return set(nodes.loc[nodes["Status"] == status, "Id"])


def pairs_with(comparison: Comparison, status: Status) -> set[tuple[str, str]]:
    links = comparison.links.loc[comparison.links["Status"] == status]
    return set(zip(links["Source"], links["Cible"], strict=True))


def test_compare_finds_added_and_removed(data: InputData) -> None:
    comparison = compare(data, BEFORE, AFTER)

    assert ids_with(comparison, Status.ADDED) == {"SHOP"}
    assert ids_with(comparison, Status.REMOVED) == {"SHEETS"}
    assert ids_with(comparison, Status.UNCHANGED) == ALL_NODES - {"SHOP", "SHEETS"}
    assert pairs_with(comparison, Status.ADDED) == {("P_ORDERS", "SHOP"), ("SHOP", "MILL")}
    assert pairs_with(comparison, Status.REMOVED) == {("P_ORDERS", "SHEETS")}


def test_compare_contains_each_row_once(data: InputData) -> None:
    comparison = compare(data, BEFORE, AFTER)

    # Unione dei due snapshot: ogni nodo compare UNA sola volta, qualunque sia lo stato.
    # duplicated().any(): True se almeno un Id è ripetuto.
    assert not comparison.nodes["Id"].duplicated().any()
    assert set(comparison.nodes["Id"]) == ALL_NODES


def test_compare_in_the_other_direction_swaps_added_and_removed(data: InputData) -> None:
    comparison = compare(data, AFTER, BEFORE)

    assert ids_with(comparison, Status.ADDED) == {"SHEETS"}
    assert ids_with(comparison, Status.REMOVED) == {"SHOP"}


def test_compare_same_day_changes_nothing(data: InputData) -> None:
    comparison = compare(data, BEFORE, BEFORE)

    # set(colonna) == {un solo valore}: tutte le righe hanno lo stesso stato.
    assert set(comparison.nodes["Status"]) == {Status.UNCHANGED}
    assert set(comparison.links["Status"]) == {Status.UNCHANGED}


def test_link_with_empty_flow_type_is_still_matched() -> None:
    # TypeFlux vuoto nella chiave del link: senza fillna("") (NaN != NaN) lo stesso link
    # risulterebbe "removed" E "added" invece che "unchanged".
    # ATTENZIONE: va usato float("nan"), cioè ciò che arriva davvero da una cella Excel vuota.
    # La prima versione usava None, ma None == None è VERO: il test passava anche senza
    # fillna e non proteggeva niente (scoperto con il mutation testing).
    start, end = date(2026, 1, 1), date(2100, 12, 31)
    data = InputData(
        nodes=pd.DataFrame(
            [{"Id": x, "Actif": True, "DateDebut": start, "DateFin": end} for x in ["A", "B"]]
        ),
        links=pd.DataFrame(
            [
                {
                    "Source": "A",
                    "Cible": "B",
                    "TypeFlux": float("nan"),
                    "Actif": True,
                    "DateDebut": start,
                    "DateFin": end,
                }
            ]
        ),
        projects=pd.DataFrame(),
        parameters={},
    )

    comparison = compare(data, BEFORE, AFTER)

    assert list(comparison.links["Status"]) == [Status.UNCHANGED]


def test_subtitles() -> None:
    empty = pd.DataFrame()
    assert Snapshot(BEFORE, empty, empty).subtitle == "08.10.2026"
    assert Comparison(BEFORE, AFTER, empty, empty).subtitle == "Changes 08.10.2026 → 01.06.2027"
