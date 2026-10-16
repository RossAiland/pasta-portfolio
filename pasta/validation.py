"""Check the content of the Excel file and report ALL the errors at once."""

from dataclasses import dataclass

import pandas as pd

from pasta.loader import LINKS_SHEET, NODES_SHEET, PROJECTS_SHEET, InputData

# IDEA: invece di fermarsi al PRIMO errore, si controlla tutto il file e si raccolgono gli
# errori in una lista. Chi corregge l'Excel vede l'elenco completo in una volta sola, invece
# di correggere, rilanciare, scoprire l'errore successivo, e così via.
#
# DUE FUNZIONI SEPARATE:
# - find_errors(data) -> list[str]: TROVA gli errori e li restituisce (facile da testare:
#   basta controllare la lista);
# - validate(data): chiama find_errors e, se la lista non è vuota, FERMA il programma
#   sollevando DataValidationError. È quella che userà il programma.

# Colonne che DEVONO esistere in ogni foglio, e che non possono avere celle vuote.
# (Actif è controllato a parte: deve essere True o False.)
NODE_REQUIRED = ["Id", "Libelle", "TypeElement", "Actif", "DateDebut", "DateFin"]
LINK_REQUIRED = ["Source", "Cible", "Actif", "DateDebut", "DateFin"]
PROJECT_REQUIRED = ["Id"]

# Ordine dei fogli nell'elenco degli errori (lo stesso dell'Excel).
SHEET_ORDER = {NODES_SHEET: 0, LINKS_SHEET: 1, PROJECTS_SHEET: 2}


class DataValidationError(Exception):
    """The input file has one or more errors; .errors holds the full list."""

    # Questa eccezione, a differenza di ConfigError, ha un COSTRUTTORE (__init__): riceve la
    # lista degli errori e la conserva in self.errors, così chi la intercetta può usarla
    # (per esempio un test può contare gli errori).
    # "self" è l'oggetto stesso: come "this" in C++, ma va scritto esplicitamente come
    # primo parametro di ogni metodo.
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        # "\n".join(lista) unisce le stringhe della lista mettendo un a capo tra l'una e l'altra.
        # Dentro join c'è una GENERATOR EXPRESSION: come una list comprehension ma senza [ ].
        # Produce i valori uno alla volta invece di costruire una lista intera in memoria.
        lines = "\n".join(f"  {error}" for error in errors)
        # super().__init__(...) chiama il costruttore della classe base (Exception), come
        # ": Exception(message)" nella lista di inizializzazione di un costruttore C++.
        # Il testo passato è il messaggio che si vede quando l'errore viene stampato.
        super().__init__(f"The input file has {len(errors)} error(s):\n{lines}")


# Un errore trovato, con il numero di riga come INTERO: se fossero solo stringhe, ordinandole
# "row 10" verrebbe prima di "row 9" (le stringhe si confrontano carattere per carattere).
# Si ordina sui campi, e solo alla fine si trasforma in testo.
@dataclass
class Problem:
    sheet: str
    row: int  # riga Excel; 0 = problema dell'intero foglio (es. colonna mancante)
    text: str

    # Un METODO: una funzione definita dentro la classe, che riceve l'oggetto come "self".
    def __str__(self) -> str:
        # __str__ è il metodo "speciale" che Python chiama quando l'oggetto diventa testo
        # (str(problem), print(problem), f"{problem}"). Come ridefinire operator<< in C++.
        if self.row == 0:
            return f"{self.sheet}: {self.text}"
        return f"{self.sheet}, row {self.row}: {self.text}"


def validate(data: InputData) -> None:
    """Stop the program with DataValidationError if the input data has errors."""
    errors = find_errors(data)
    if errors:
        raise DataValidationError(errors)


def find_errors(data: InputData) -> list[str]:
    """Return the list of all the errors found in the input data (empty if all is fine)."""
    problems: list[Problem] = []  # type hint su una variabile: "lista di Problem", vuota

    # Se mancano colonne in un foglio, gli altri controlli su quel foglio non hanno senso
    # (darebbero KeyError): lo segnaliamo e passiamo oltre.
    # Le funzioni _check_* ricevono la lista "problems" e la RIEMPIONO: in Python una lista
    # passata a una funzione NON viene copiata (come passare un riferimento in C++), quindi
    # le aggiunte fatte dentro la funzione si vedono anche qui.
    nodes_ok = _check_columns(data.nodes, NODES_SHEET, NODE_REQUIRED, problems)
    links_ok = _check_columns(data.links, LINKS_SHEET, LINK_REQUIRED, problems)
    projects_ok = _check_columns(data.projects, PROJECTS_SHEET, PROJECT_REQUIRED, problems)

    if nodes_ok:
        _check_not_empty(data.nodes, NODES_SHEET, NODE_REQUIRED, problems)
        _check_actif(data.nodes, NODES_SHEET, problems)
        _check_unique_ids(data.nodes, NODES_SHEET, problems)
        _check_date_order(data.nodes, NODES_SHEET, problems)
    if links_ok:
        _check_not_empty(data.links, LINKS_SHEET, LINK_REQUIRED, problems)
        _check_actif(data.links, LINKS_SHEET, problems)
        _check_date_order(data.links, LINKS_SHEET, problems)
    if projects_ok:
        _check_not_empty(data.projects, PROJECTS_SHEET, PROJECT_REQUIRED, problems)
        _check_unique_ids(data.projects, PROJECTS_SHEET, problems)
        _check_date_order(data.projects, PROJECTS_SHEET, problems)

    # Controlli tra fogli diversi: servono le colonne di entrambi.
    if nodes_ok and links_ok:
        for column in ["Source", "Cible"]:
            _check_references(
                data.links, LINKS_SHEET, column, data.nodes["Id"], NODES_SHEET, problems
            )
    if projects_ok:
        project_ids = data.projects["Id"]
        if nodes_ok and "Projet" in data.nodes.columns:
            _check_references(
                data.nodes, NODES_SHEET, "Projet", project_ids, PROJECTS_SHEET, problems
            )
        if links_ok and "Projet" in data.links.columns:
            _check_references(
                data.links, LINKS_SHEET, "Projet", project_ids, PROJECTS_SHEET, problems
            )

    # ORDINAMENTO per foglio e poi per riga.
    # key=... dice a sort() su COSA confrontare gli elementi. "lambda p: ..." è una funzione
    # anonima di una riga (come una lambda C++: [](const Problem& p) { return ...; }).
    # Restituisce una TUPLA: le tuple si confrontano campo per campo (prima il foglio, a
    # parità di foglio la riga), come std::tie in C++.
    # sort() è STABILE: due errori sulla stessa riga restano nell'ordine in cui sono stati
    # trovati.
    problems.sort(key=lambda p: (SHEET_ORDER[p.sheet], p.row))
    return [str(problem) for problem in problems]


def _excel_row(index: int) -> int:
    """Return the row number shown in Excel for a pandas index."""
    # Riga Excel = indice + 2: +1 perché l'indice di pandas parte da 0, +1 per la riga
    # delle intestazioni. Il loader conserva l'indice originale anche dopo aver tolto le
    # righe vuote, quindi il numero è quello giusto.
    return index + 2


def _check_columns(
    table: pd.DataFrame, sheet: str, required: list[str], problems: list[Problem]
) -> bool:
    """Add a problem for each missing column; return True if none is missing."""
    missing = [column for column in required if column not in table.columns]
    for column in missing:
        problems.append(Problem(sheet, 0, f"column '{column}' is missing"))
    # "not missing": True se la lista è vuota (nessuna colonna mancante).
    return not missing


def _check_not_empty(
    table: pd.DataFrame, sheet: str, columns: list[str], problems: list[Problem]
) -> None:
    """Add a problem for each empty cell in the given columns (Actif excluded)."""
    for column in columns:
        if column == "Actif":
            continue  # controllato da _check_actif
        # MASCHERA BOOLEANA: table[column].isna() restituisce una colonna di True/False,
        # True dove la cella è vuota. È un'operazione vettoriale (nessun ciclo sulle righe).
        empty = table[column].isna()
        # table.index[maschera] = gli INDICI delle righe in cui la maschera vale True.
        for index in table.index[empty]:
            # Per le date "vuota" comprende anche "non era una data": il loader ha trasformato
            # i valori non validi in NaT.
            if column.startswith("Date"):
                text = f"{column} is empty or not a valid date"
            else:
                text = f"{column} is empty"
            problems.append(Problem(sheet, _excel_row(index), text))


def _check_actif(table: pd.DataFrame, sheet: str, problems: list[Problem]) -> None:
    """Add a problem for each Actif cell that is not exactly True or False."""
    # pd.api.types.is_bool(v) è vero sia per i bool di Python sia per i numpy.bool_ (il tipo
    # che pandas usa quando la colonna è tutta booleana). Con isinstance(v, bool) i
    # numpy.bool_ verrebbero rifiutati per sbaglio.
    # .map(funzione) la applica a ogni cella; "~" NEGA una maschera (True <-> False),
    # come "!" in C++ ma elemento per elemento.
    wrong = ~table["Actif"].map(pd.api.types.is_bool)
    for index in table.index[wrong]:
        value = table.at[index, "Actif"]  # .at[indice, colonna] = il valore di UNA cella
        # ESPRESSIONE CONDIZIONALE "a if condizione else b": è l'operatore ternario del C++
        # (condizione ? a : b), scritto in un altro ordine.
        # repr(value) dà la rappresentazione del valore: 'oui' con le virgolette, 1.5 senza.
        found = "empty" if pd.isna(value) else repr(value)
        text = f"Actif must be True or False (found: {found})"
        problems.append(Problem(sheet, _excel_row(index), text))


def _check_unique_ids(table: pd.DataFrame, sheet: str, problems: list[Problem]) -> None:
    """Add a problem for each row whose Id is also used by another row."""
    # duplicated(keep=False) segna con True TUTTE le righe il cui valore compare più di una
    # volta (con il default keep="first" la prima resterebbe False, e non la segnaleremmo).
    # "&" combina due maschere: True solo dove sono vere ENTRAMBE (un "and" elemento per
    # elemento). Gli Id vuoti li segnala già _check_not_empty, quindi li escludiamo.
    # Le PARENTESI sono obbligatorie: & ha precedenza più alta dei confronti.
    ids = table["Id"]
    duplicated = ids.duplicated(keep=False) & ids.notna()
    for index in table.index[duplicated]:
        text = f"Id '{ids[index]}' is used by more than one row"
        problems.append(Problem(sheet, _excel_row(index), text))


def _check_date_order(table: pd.DataFrame, sheet: str, problems: list[Problem]) -> None:
    """Add a problem for each row whose DateFin is before its DateDebut."""
    if "DateDebut" not in table.columns or "DateFin" not in table.columns:
        return  # nel foglio Projets le date non sono obbligatorie
    # Confrontiamo solo le righe con ENTRAMBE le date: quelle vuote le segnala già
    # _check_not_empty, e confrontare una data con un valore vuoto non ha senso.
    both = table["DateDebut"].notna() & table["DateFin"].notna()
    # table.loc[maschera] = solo le righe in cui la maschera vale True (una tabella più piccola,
    # che conserva gli indici originali).
    dated = table.loc[both]
    wrong = dated["DateFin"] < dated["DateDebut"]
    for index in dated.index[wrong]:
        start, end = dated.at[index, "DateDebut"], dated.at[index, "DateFin"]
        text = f"DateFin {end} is before DateDebut {start}"
        problems.append(Problem(sheet, _excel_row(index), text))


def _check_references(
    table: pd.DataFrame,
    sheet: str,
    column: str,
    valid_ids: pd.Series,
    target_sheet: str,
    problems: list[Problem],
) -> None:
    """Add a problem for each value of table[column] that is not one of valid_ids."""
    # pd.Series = UNA colonna di pandas (un DataFrame è un insieme di Series con un nome).
    # isin(valori): maschera True dove il valore della cella è tra i valori dati. Con "~"
    # otteniamo quelli che NON ci sono. Le celle vuote non sono un riferimento sbagliato
    # (es. Projet vuoto = nessun progetto; Source vuota la segnala già _check_not_empty).
    values = table[column]
    unknown = ~values.isin(valid_ids) & values.notna()
    for index in table.index[unknown]:
        text = f"{column} '{values[index]}' is not an Id in {target_sheet}"
        problems.append(Problem(sheet, _excel_row(index), text))
