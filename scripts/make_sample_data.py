"""Create data/sample_pastificio.xlsx: a small, entirely FICTIONAL company.

A pasta factory with a few processes, the IT systems that support them and
the data flows between them. One project replaces an old system with a new
one, so the picture changes after this transformation project is over.

Run from the project folder:

    python scripts/make_sample_data.py
"""

# The text between """...""" above is the module DOCSTRING: the documentation of the file.
# Python keeps it, and help() and VSCode show it. It goes at the top of the file, or right
# after "def" or "class": anywhere else it is just a string that Python evaluates and ignores.

# IMPORTS
# - "import X" is similar to #include, but also creates a namespace: pandas.DataFrame, like
#   std::vector.
# - "from X import Y" brings in the name Y directly: you write date(...) and not
#   datetime.date(...) (similar to "using std::vector;").
# - "as pd" is an alias; "pd" for pandas is a universal convention.
# - Order: standard library first, empty line, then external libraries
#   (Ruff fixes it by itself on save).
from datetime import date
from pathlib import Path

import pandas as pd

# Where the file is written: <project folder>/data/sample_pastificio.xlsx
# The "/" operator between paths is not a division: Path REDEFINES it to join the pieces of a
# path (operator overloading, like std::string with "+"). It works on Windows and Linux.
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_pastificio.xlsx"
"""__file__ is the path of this script, .resolve() makes it an absolute path,
the first .parent is the scripts/ folder;
the second .parent is the project folder;
/ "data" / "sample_pastificio.xlsx" appends the rest.
Why not simply write "data/sample_pastificio.xlsx"? Because a relative path
depends on where you launch the program from. Starting from __file__, the script finds the
data/ folder from any location.
"""
# Validity used for things that "always" exist
# date(year, month, day) creates a date object (like std::chrono::year_month_day, but simpler).
ALWAYS_START = date(2026, 1, 1)
ALWAYS_END = date(2100, 12, 31)

# Column names of each sheet, in French like the real working file.
# Cells we don't fill stay empty: the program will use the defaults
# from the "Parametres" sheet.
"""I create the lists. Python has no const, so the convention is to write the names in
ALL_CAPS: it means "don't modify me"."""
# [...] is a LIST: the equivalent of std::vector, but it can hold objects of any type and
# grows by itself.
# The comma after the last element ("trailing comma") tells Ruff "keep this list on several
# lines": one element per line. Longer, but in Git diffs adding a column changes a single line.
NODE_COLUMNS = [
    "Id",
    "Libelle",
    "TypeElement",
    "Domaine",
    "Shape",
    "Style",
    "Color",
    "Fillcolor",
    "Penwidth",
    "Actif",
    "DateDebut",
    "DateFin",
    "Projet",
    "Commentaire",
]
LINK_COLUMNS = [
    "Source",
    "Cible",
    "Libelle",
    "Domaine",
    "TypeFlux",
    "Direction",
    "Style",
    "Color",
    "Penwidth",
    "Données",
    "Actif",
    "DateDebut",
    "DateFin",
    "Projet",
    "Commentaire",
]

# ---------------------------------------------------------------------------
# Nodes: what the company does (processes) and what it uses (systems)
# ---------------------------------------------------------------------------

# Go-live of the "Online shop" project: from this day the WebShop replaces
# the order spreadsheets
SHOP_GO_LIVE = date(2027, 4, 1)
# During the month before the go-live, the old data is copied into the WebShop
MIGRATION_START = date(2027, 3, 1)
MIGRATION_END = date(2027, 3, 31)

# Border and fill color of the processes, by domain
# {key: value} is a DICTIONARY, similar to std::map<std::string, ...>; values of different
# types can live in the same dictionary.
# ("#2F8F2F", "#EAF7EA") is a TUPLE: like a list but IMMUTABLE (similar to std::pair/tuple).
# "#RRGGBB" COLORS: hexadecimal RGB, as in HTML/CSS. Each pair goes from 00 to FF (0-255, like
# a uint8_t). E.g. #2B8CBE = red 43, green 140, blue 190 -> light blue. Upper and lower case
# are the same. VSCode shows a small colored square next to it (color decorator), and clicking
# it opens a color picker. Many colors come from ColorBrewer (colorbrewer2.org).
DOMAIN_COLORS = {
    "Production": ("#2F8F2F", "#EAF7EA"),  # tuple
    "Sales": ("#C51B8A", "#FDE0EF"),
}

"""The story the data tells: today customer orders are handled with Excel spreadsheets.
The "Online shop" project replaces them
with a WebShop from April 1st, 2027. In March 2027 there is one month of data migration
from the old to the new system. Comparing October 2026 with June 2027,
the graph of the changes will show the spreadsheets in red and the WebShop in green."""

# I am defining 3 functions to get the dictionaries of these objects with the style I want,
# so that they can be told apart.
"""
NOTE id_ with the underscore: id is already the name of a Python function. Calling a
parameter id would "hide" it. The trailing underscore is the convention to avoid that, like
class_ or type_
"""
# FUNCTIONS: "def name(parameters):". Like C++ but without types and without { }: the body is
# defined by INDENTATION (4 spaces). No declared return type: "return" returns anything
# (here a dictionary = one row of the Excel file).


def macro_process(id_, label, domain):
    return {
        "Id": id_,
        "Libelle": label,
        "TypeElement": "Macro processus",
        "Domaine": domain,
        "Shape": "rectangle",
        "Style": "filled",
        "Color": "#2B8CBE",
        "Fillcolor": "#2B8CBE",
        "Penwidth": 2,
        "Actif": True,
        "DateDebut": ALWAYS_START,
        "DateFin": ALWAYS_END,
    }


# in my company the macro processes are production and sales.


def process(id_, label, domain):
    # UNPACKING: "unpacks" the tuple into two variables in one go.
    # In C++17: auto [border, fill] = DOMAIN_COLORS[domain];
    border, fill = DOMAIN_COLORS[domain]
    return {
        "Id": id_,
        "Libelle": label,
        "TypeElement": "Processus",
        "Domaine": domain,
        "Shape": "ellipse",
        "Style": "filled",
        "Color": border,
        "Fillcolor": fill,
        "Actif": True,
        "DateDebut": ALWAYS_START,
        "DateFin": ALWAYS_END,
    }


# the sales processes are customer orders and invoicing. The customer triggers the
# production planning process, part of the production macro process.

# PARAMETERS WITH DEFAULTS: start=ALWAYS_START can be left out in the call, as in C++.
# KEYWORD ARGUMENTS: in the call you can write project="PRJ_SHOP" and skip the ones you don't
# need (e.g. end keeps its default). In C++ you cannot.
# The defaults here are DATES (immutable), so that is fine. Trap to avoid (Ruff B006):
# a MUTABLE default like items=[] is created only ONCE and "remembers" the previous calls.
# Solution: items=None and then "if items is None: items = []".
# None is Python's "nothing" (similar to nullptr): in the Excel file it becomes an empty cell.


def system(
    id_, label, domain, start=ALWAYS_START, end=ALWAYS_END, project=None
):  # note the default
    # is that there are no projects changing it.
    return {
        "Id": id_,
        "Libelle": label,
        "TypeElement": "Système",
        "Domaine": domain,
        "Shape": "rectangle",
        "Style": "rounded,filled",
        "Color": "#F03B20",
        "Fillcolor": "#FDBB84",
        "Actif": True,
        "DateDebut": start,
        "DateFin": end,
        "Projet": project,
    }


# systems are used by processes. The system for production planning is MillControl.
# The system for invoicing is BillingPro, which works with the bank as a vendor.

NODES = [  # a list of dictionaries: each dictionary is a node of the graph = one Excel row
    macro_process("MP_PROD", "Production", "Production"),
    macro_process("MP_SALES", "Sales", "Sales"),
    process("P_PLAN", "Production\nplanning", "Production"),
    process("P_ORDERS", "Customer\norders", "Sales"),
    process("P_INVOICE", "Invoicing", "Sales"),
    system("MILL", "MillControl", "Production"),
    system("BILLING", "BillingPro", "Sales"),
    # Old system: used until the day before the go-live: orders are handled in Excel.
    system("SHEETS", "Order\nspreadsheets", "Sales", end=MIGRATION_END, project="PRJ_SHOP"),
    # New system: installed one month before the go-live, to receive the old data.
    # The SHOP project changes this system.
    system("SHOP", "WebShop", "Sales", start=MIGRATION_START, project="PRJ_SHOP"),
    # External system: style left empty on purpose, the program must use the defaults. It does
    # not use system() precisely because it must have an empty style: it is the test case for
    # the default values in Parametres. The keys missing from the dictionary (Shape, Color…)
    # will become empty cells when pandas builds the Excel table
    {
        "Id": "BANK",
        "Libelle": "Bank\n(external)",
        "TypeElement": "Système",
        "Domaine": "Sales",
        "Actif": True,
        "DateDebut": ALWAYS_START,
        "DateFin": ALWAYS_END,
    },
]

# ---------------------------------------------------------------------------
# Links: the arrows between nodes
# ---------------------------------------------------------------------------

MACRO_BLUE = "#2B8CBE"

# Only source and target are required, everything else has a default: simple arrows fit on
# one line, link("P_PLAN", "MILL"), special ones only state what changes.
# The definition spans several lines because it does not fit in 100 characters: Ruff split it.


def link(
    source,
    target,
    label=None,
    flow_type="processus",
    style="solid",
    color=None,
    penwidth=None,
    data=None,
    start=ALWAYS_START,
    end=ALWAYS_END,
    project=None,
    active=True,
    comment=None,
):
    return {
        "Source": source,
        "Cible": target,
        "Libelle": label,
        "TypeFlux": flow_type,
        "Direction": "forward",
        # (the "Domaine" column of the links is left empty on purpose: it is not needed here,
        # and the program must accept it empty anyway)
        "Style": style,
        "Color": color,
        "Penwidth": penwidth,
        "Données": data,
        "Actif": active,
        "DateDebut": start,
        "DateFin": end,
        "Projet": project,
        "Commentaire": comment,
    }


# POSITIONAL + KEYWORD ARGUMENTS together: the first ones go IN ORDER (source, target, label),
# the others BY NAME and in any order. Rule: positional ones first, then keyword ones.
# "\n" in labels is a line break, as in C++: Graphviz will write the label on two lines.
# Accents ("échange de données"): in Python 3 all strings are Unicode, they just work.
LINKS = [
    # Macro process -> its processes (thick blue lines)
    link("MP_PROD", "P_PLAN", color=MACRO_BLUE, penwidth=2),
    link("MP_SALES", "P_ORDERS", color=MACRO_BLUE, penwidth=2),
    link("MP_SALES", "P_INVOICE", color=MACRO_BLUE, penwidth=2),
    # Process -> process
    link("P_ORDERS", "P_PLAN", "orders to\nproduce"),
    # Process -> the system that supports it
    link("P_PLAN", "MILL"),
    link("P_INVOICE", "BILLING"),
    link("P_ORDERS", "SHEETS", end=MIGRATION_END, project="PRJ_SHOP"),
    link("P_ORDERS", "SHOP", start=SHOP_GO_LIVE, project="PRJ_SHOP"),
    # System -> system: data exchanges
    link(
        "SHOP",
        "MILL",
        "orders",
        flow_type="échange de données",
        data="customer orders",
        start=SHOP_GO_LIVE,
        project="PRJ_SHOP",
    ),
    link("BILLING", "BANK", "payments", flow_type="échange de données", data="invoices"),
    # Data migration: exists only while old and new system live together
    link(
        "SHEETS",
        "SHOP",
        "data\nmigration",
        flow_type="migration",
        style="dashed",
        start=MIGRATION_START,
        end=MIGRATION_END,
        project="PRJ_SHOP",
    ),
    # A discarded idea: Actif = False, so it must never be drawn
    link("MILL", "BILLING", "production\ncosts", active=False, comment="Idea dropped"),
]

# ---------------------------------------------------------------------------
# Projects and parameters
# ---------------------------------------------------------------------------

PROJECTS = [
    {
        "Id": "PRJ_SHOP",
        "Libelle": "Online shop",
        "DateDebut": date(2026, 9, 1),
        "DateFin": SHOP_GO_LIVE,
        "Commentaire": "DateFin = go-live",
    },
]

# (name, value, description): general settings of the graph and default styles
# A list of TUPLES: each parameter always has 3 values, and a tuple is perfect for a short,
# fixed "record" (more compact than a dictionary with 3 keys repeated 11 times).
# The Valeur column holds DIFFERENT TYPES (text, numbers, a date): normal in Excel, the
# program will have to convert it depending on the parameter.
PARAMETERS = [
    ("GraphLabel", "Pastificio - IT landscape (fictional data)", "Title on top of the graph"),
    ("Layout", "dot", "Graphviz layout engine"),
    ("Rankdir", "LR", "Graph direction: left to right"),
    ("Fontname", "Arial", "Font of all texts"),
    ("NodeDefaultShape", "rectangle", "Node shape when the cell is empty"),
    ("NodeDefaultStyle", "rounded,filled", "Node style when the cell is empty"),
    ("NodeDefaultColor", "#555555", "Node border color when the cell is empty"),
    ("NodeDefaultFillcolor", "#F8F8F8", "Node fill color when the cell is empty"),
    ("EdgeDefaultColor", "#555555", "Link color when the cell is empty"),
    ("EdgeDefaultPenwidth", 1, "Link thickness when the cell is empty"),
    ("DateReference", date(2026, 10, 8), "Default date used to choose what to draw"),
]

# ---------------------------------------------------------------------------
# Write the Excel file: one sheet per table
# ---------------------------------------------------------------------------


# "def main()" is just a CONVENTION to keep the code "to run" in one tidy place:
# in Python there is no special main() as in C++ (see the "if" at the end of the file).
def main():
    # DataFrame = the pandas table (rows and named columns, an Excel sheet in memory).
    # From a list of dictionaries: each dictionary becomes a row. "columns=" sets the list and
    # order of the columns: those a dictionary does not have (e.g. Shape for BANK) stay empty.
    # From a list of tuples (PARAMETERS) it is enough to give the column names.
    #
    # LIST COMPREHENSION (not needed here, but you will find it everywhere). This loop:
    #     names = []
    #     for name, value, text in PARAMETERS:
    #         names.append(name)
    # is written in one line:
    #     names = [name for name, value, text in PARAMETERS]
    # With a filter: [n for n in NODES if n["Actif"]]. In C++: std::transform / ranges (C++20).
    sheets = {
        "Noeuds": pd.DataFrame(NODES, columns=NODE_COLUMNS),
        "Liens": pd.DataFrame(LINKS, columns=LINK_COLUMNS),
        "Projets": pd.DataFrame(PROJECTS),
        "Parametres": pd.DataFrame(PARAMETERS, columns=["Parametre", "Valeur", "Description"]),
    }

    # CONTEXT MANAGER "with": when leaving the block the file is closed and saved, even if an
    # error happens inside. It is C++ RAII (a std::ofstream closing in its destructor).
    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        # .items() gives the (key, value) pairs of the dictionary; unpacking splits them.
        # In C++: for (auto& [name, table] : sheets)
        for name, table in sheets.items():
            table.to_excel(writer, sheet_name=name, index=False)

    # F-STRING: the "f" in front allows inserting expressions between { } (like std::format
    # in C++20). len() returns the length of any container: here the number of rows.
    print(f"Created {OUTPUT_FILE.name}")
    for name, table in sheets.items():
        print(f"  {name}: {len(table)} rows")


# In Python ALL the code of a file runs when the file is loaded, even when it is imported by
# another file. __name__ is "__main__" only if the file was LAUNCHED directly
# (python scripts/make_sample_data.py). This way the Excel file is created only when the
# script is launched, not when a test imports it to read NODES.
if __name__ == "__main__":
    main()
