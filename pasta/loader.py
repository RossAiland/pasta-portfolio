"""Read the input Excel file into pandas tables."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

# HOW PANDAS READS OUR EXCEL FILE (seen by exploring data/sample_pastificio.xlsx):
# 1. Each column has ONE type only, its "dtype", guessed from the values: str, float64, bool,
#    datetime64... In C++ terms, each column is like a std::vector<T> with a single T.
# 2. Empty cells become NaN ("Not a Number"), which is a FLOAT. Therefore:
#    - a column of integers with empty cells becomes float64 (Penwidth: 1.0, 2.0, NaN);
#    - a text column that is completely empty becomes float64 (Commentaire).
#    NaN == NaN is FALSE (like IEEE floats in C++): to detect an empty cell ALWAYS use
#    pd.isna(value), never "== NaN".
# 3. Dates become Timestamps (date + time 00:00:00). The rest of the program (and Config)
#    uses datetime.date: they are converted here, so there is one date type everywhere.
# 4. The Valeur column of Parametres mixes different types (str, int, datetime): it is
#    turned into a dictionary {name: value}.

# Sheet names, in French like in the real file.
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

    # pd.DataFrame as a type hint: VSCode knows that nodes is a table and suggests its methods.
    nodes: pd.DataFrame
    links: pd.DataFrame
    projects: pd.DataFrame
    # dict[str, object]: keys of type str, values of any type (text, numbers, dates).
    # In C++: std::map<std::string, std::any>.
    parameters: dict[str, object]


def load_excel(path: Path) -> InputData:
    """Read the four sheets of the input file and convert their types."""
    try:
        # sheet_name=None reads ALL the sheets at once: the result is a dictionary
        # {sheet name: DataFrame}.
        sheets = pd.read_excel(path, sheet_name=None)
    except FileNotFoundError:
        raise LoadError(f"Input file not found: {path}") from None

    # The sheets are checked before use, so the error says WHICH sheet is missing instead of
    # a generic KeyError. Columns and values are checked later by validation.py.
    expected = [NODES_SHEET, LINKS_SHEET, PROJECTS_SHEET, PARAMETERS_SHEET]
    # List comprehension with a filter: "the expected names that are NOT keys of sheets".
    missing = [name for name in expected if name not in sheets]
    if missing:  # an empty list counts as False, a non-empty list as True
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
    # EMPTY ROWS: an empty row IN THE MIDDLE of the sheet arrives as a row of NaN only (empty
    # rows AT THE END, even if formatted, are already skipped by pandas).
    # dropna(how="all") removes the rows where ALL cells are empty, and returns a NEW table:
    # the one received is not modified (like passing by value in C++).
    # The INDEX stays the original one (e.g. 0, 2 if row 1 was empty): this way validation.py
    # can point to the right Excel row = index + 2 (+1 because the index starts at 0,
    # +1 for the header row).
    # CHOICE ("rule A"): a row with ONE filled cell only (e.g. only Actif = True, maybe
    # dragged down the column in Excel) is NOT empty, so it stays. validation.py will find
    # an empty Id and empty dates and stop the program: better an error to fix than
    # something hidden.
    table = table.dropna(how="all")

    if "Actif" in table.columns:
        # .map(function) applies the function to EVERY cell of the column and returns the new
        # column. You pass the NAME of the function, without (): like a function pointer
        # in C++.
        table["Actif"] = table["Actif"].map(_as_bool)

    for column in DATE_COLUMNS:
        if column in table.columns:
            # "VECTORIZED" OPERATION: it applies to the WHOLE column at once, without writing
            # a for loop over the rows. This is the typical pandas style.
            # errors="coerce": a value that is not a date becomes NaT ("Not a Time", the NaN
            # of dates) instead of stopping everything; validation.py will report it.
            # .dt.date: from Timestamp (date + time) to datetime.date (date only).
            # After the conversion the column dtype is "object": pandas' GENERIC type, a column
            # of arbitrary Python objects (dates here). Less efficient than datetime64, but
            # with a few rows it does not matter, and the program has a single date type.
            table[column] = pd.to_datetime(table[column], errors="coerce").dt.date
    return table


def _as_bool(value: object) -> object:
    """Return True/False for a boolean cell, the value unchanged otherwise."""
    # When a column of booleans also has empty cells, pandas cannot use the bool dtype
    # (which does not allow NaN) and falls back to float: True becomes 1.0, False 0.0.
    # Here they are turned back into True/False. Empty cells and odd values (e.g. the text
    # "oui") stay as they are: Actif must ALWAYS be True or False, and validation.py will
    # stop the program with a clear error, forcing the user to fix the file.
    if pd.isna(value):
        return value
    # "in (0, 1)" holds for True/False (in Python bool is a subtype of int: True == 1)
    # and for 1.0/0.0. A string like "1" is NOT equal to 1, so it stays unchanged.
    if value in (0, 1):
        return bool(value)
    return value


def _parameters_to_dict(table: pd.DataFrame) -> dict[str, object]:
    """Turn the Parametres sheet into {name: value}, with dates as datetime.date."""
    # zip() walks through two columns in parallel, in pairs: (name1, value1), (name2, value2)...
    # DICT COMPREHENSION: like a list comprehension but with { } and "key: value".
    # "if pd.notna(name)" skips rows with an empty name (e.g. empty rows at the end).
    # strict=True: if the two sequences had different lengths, zip() would normally stop
    # SILENTLY at the shorter one; with strict=True it raises an error (Ruff B905).
    pairs = zip(table["Parametre"], table["Valeur"], strict=True)
    parameters = {name: value for name, value in pairs if pd.notna(name)}
    # isinstance(value, datetime) is also true for pandas Timestamps, which "derive" from
    # datetime (inheritance, as in C++). .date() keeps the date only.
    # .items() on a dictionary gives the (key, value) pairs.
    for name, value in parameters.items():
        if isinstance(value, datetime):
            parameters[name] = value.date()
    return parameters
