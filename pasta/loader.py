"""Read the input Excel file into pandas tables."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

# COME LEGGE PANDAS IL NOSTRO EXCEL (visto esplorando data/sample_pastificio.xlsx):
# 1. Ogni colonna ha UN SOLO tipo, il "dtype", dedotto dai valori: str, float64, bool,
#    datetime64... In C++ è come se ogni colonna fosse un std::vector<T> con un solo T.
# 2. Le celle vuote diventano NaN ("Not a Number"), che è un FLOAT. Quindi:
#    - una colonna di interi con celle vuote diventa float64 (Penwidth: 1.0, 2.0, NaN);
#    - una colonna di testo tutta vuota diventa float64 (Commentaire).
#    NaN == NaN è FALSO (come i float IEEE in C++): per una cella vuota si usa SEMPRE
#    pd.isna(valore), mai "== NaN".
# 3. Le date diventano Timestamp (data + ora 00:00:00). Il resto del programma (e Config)
#    usa datetime.date: qui le convertiamo, così c'è un solo tipo di data ovunque.
# 4. La colonna Valeur di Parametres mescola tipi diversi (str, int, datetime): la
#    trasformiamo in un dizionario {nome: valore}.

# Nomi dei fogli, in francese come nel file reale.
NODES_SHEET = "Noeuds"
LINKS_SHEET = "Liens"
PROJECTS_SHEET = "Projets"
PARAMETERS_SHEET = "Parametres"

DATE_COLUMNS = ["DateDebut", "DateFin"]


class LoadError(Exception):
    """The Excel file cannot be read or is missing a sheet."""


@dataclass
class InputData:
    """The content of the Excel file, ready for the rest of the program."""

    # pd.DataFrame come type hint: VSCode sa che nodes è una tabella e suggerisce i metodi.
    nodes: pd.DataFrame
    links: pd.DataFrame
    projects: pd.DataFrame
    # dict[str, object]: chiavi di tipo str, valori di tipo qualsiasi (testo, numeri, date).
    # In C++: std::map<std::string, std::any>.
    parameters: dict[str, object]


def load_excel(path: Path) -> InputData:
    """Read the four sheets of the input file and convert their types."""
    try:
        # sheet_name=None legge TUTTI i fogli in un colpo: il risultato è un dizionario
        # {nome del foglio: DataFrame}.
        sheets = pd.read_excel(path, sheet_name=None)
    except FileNotFoundError:
        raise LoadError(f"Input file not found: {path}") from None

    # Controllo dei fogli prima di usarli, così l'errore dice QUALE foglio manca invece di
    # un generico KeyError. Il controllo delle colonne e dei valori lo farà validation.py.
    expected = [NODES_SHEET, LINKS_SHEET, PROJECTS_SHEET, PARAMETERS_SHEET]
    # List comprehension con filtro: "i nomi attesi che NON sono tra le chiavi di sheets".
    missing = [name for name in expected if name not in sheets]
    if missing:  # una lista vuota vale False, una lista non vuota vale True
        raise LoadError(f"{path.name}: missing sheet(s) {', '.join(missing)}")

    return InputData(
        nodes=_clean(sheets[NODES_SHEET]),
        links=_clean(sheets[LINKS_SHEET]),
        projects=_clean(sheets[PROJECTS_SHEET]),
        parameters=_parameters_to_dict(_clean(sheets[PARAMETERS_SHEET])),
    )


def _clean(table: pd.DataFrame) -> pd.DataFrame:
    """Remove empty rows, turn dates into datetime.date and Actif into True/False.

    Values that cannot be converted are left as they are: validation.py reports them.
    """
    # RIGHE VUOTE: una riga vuota IN MEZZO al foglio arriva come riga di soli NaN (quelle
    # vuote IN FONDO, anche se formattate, pandas le salta già da solo).
    # dropna(how="all") toglie le righe in cui TUTTE le celle sono vuote, e restituisce una
    # NUOVA tabella: quella ricevuta non viene modificata (come passare per valore in C++).
    # L'INDICE resta quello originale (es. 0, 2 se la riga 1 era vuota): così validation.py
    # potrà indicare la riga Excel giusta = indice + 2 (+1 perché l'indice parte da 0,
    # +1 per la riga delle intestazioni).
    # SCELTA (regola "A"): una riga con UNA sola cella compilata (es. solo Actif = True, magari
    # trascinato lungo la colonna in Excel) NON è vuota, quindi resta. validation.py troverà
    # Id e date vuoti e fermerà il programma: meglio un errore da correggere che nascondere
    # qualcosa.
    table = table.dropna(how="all")

    if "Actif" in table.columns:
        # .map(funzione) applica la funzione a OGNI cella della colonna e restituisce la
        # nuova colonna. Si passa il NOME della funzione, senza (): come un puntatore a
        # funzione in C++.
        table["Actif"] = table["Actif"].map(_as_bool)

    for column in DATE_COLUMNS:
        if column in table.columns:
            # OPERAZIONE "VETTORIALE": si applica a TUTTA la colonna in un colpo, senza
            # scrivere un ciclo for sulle righe. È lo stile tipico di pandas.
            # errors="coerce": un valore che non è una data diventa NaT ("Not a Time", il NaN
            # delle date) invece di bloccare tutto; validation.py lo segnalerà.
            # .dt.date: da Timestamp (data + ora) a datetime.date (solo data).
            # Dopo la conversione il dtype della colonna è "object": il tipo GENERICO di pandas,
            # una colonna di oggetti Python qualsiasi (qui date). Meno efficiente di datetime64,
            # ma con poche righe non conta, e abbiamo un solo tipo di data in tutto il programma.
            table[column] = pd.to_datetime(table[column], errors="coerce").dt.date
    return table


def _as_bool(value: object) -> object:
    """Return True/False for a boolean cell, the value unchanged otherwise."""
    # Quando una colonna di booleani contiene anche celle vuote, pandas non può usare il
    # dtype bool (che non ammette NaN) e ripiega su float: True diventa 1.0, False 0.0.
    # Qui li riportiamo a True/False. Celle vuote e valori strani (es. testo "oui") restano
    # come sono: Actif deve SEMPRE valere True o False, e validation.py fermerà il
    # programma con un errore chiaro, costringendo a correggere il file.
    if pd.isna(value):
        return value
    # "in (0, 1)" vale per True/False (in Python bool è un sottotipo di int: True == 1)
    # e per 1.0/0.0. Una stringa come "1" NON è uguale a 1, quindi resta invariata.
    if value in (0, 1):
        return bool(value)
    return value


def _parameters_to_dict(table: pd.DataFrame) -> dict[str, object]:
    """Turn the Parametres sheet into {name: value}, with dates as datetime.date."""
    # zip() scorre due colonne in parallelo, a coppie: (nome1, valore1), (nome2, valore2)...
    # DICT COMPREHENSION: come la list comprehension ma con { } e "chiave: valore".
    # "if pd.notna(name)" salta le righe con il nome vuoto (es. righe vuote in fondo al foglio).
    # strict=True: se le due sequenze avessero lunghezze diverse, zip() normalmente si
    # fermerebbe IN SILENZIO alla più corta; con strict=True solleva un errore (Ruff B905).
    pairs = zip(table["Parametre"], table["Valeur"], strict=True)
    parameters = {name: value for name, value in pairs if pd.notna(name)}
    # isinstance(value, datetime) è vero anche per i Timestamp di pandas, che "derivano" da
    # datetime (ereditarietà, come in C++). .date() tiene solo la data.
    # .items() su un dizionario dà le coppie (chiave, valore).
    for name, value in parameters.items():
        if isinstance(value, datetime):
            parameters[name] = value.date()
    return parameters
