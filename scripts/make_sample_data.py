"""Create data/sample_pastificio.xlsx: a small, entirely FICTIONAL company.

A pasta factory with a few processes, the IT systems that support them and
the data flows between them. One project replaces an old system with a new
one, so the picture changes after this trasformation project is over.

Run from the project folder:

    python scripts/make_sample_data.py
"""

from datetime import date
from pathlib import Path

import pandas as pd

# Where the file is written: <project folder>/data/sample_pastificio.xlsx
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_pastificio.xlsx"
"""__file__ è il percorso di questo script,.resolve() lo rende un percorso assoluto,
il primo .parent è la cartella scripts/;
il secondo .parent è la cartella del progetto 
/ "data" / "sample_pastificio.xlsx" aggiunge. 
Perché non scrivere semplicemente "data/sample_pastificio.xlsx"? Perché un percorso relativo 
dipende da dove lanci il programma. Partendo da __file__, lo script trova la cartella data/ da 
qualunque posizione.
"""
# Validity used for things that "always" exist
ALWAYS_START = date(2026, 1, 1)
ALWAYS_END = date(2100, 12, 31)

# Column names of each sheet, in French like the real working file.
# Cells we don't fill stay empty: the program will use the defaults
# from the "Parametres" sheet.
"""Creo le liste. Python non ha const quindi l a convenzione è scrivere i nomi TUTTO_MAIUSCOLO: 
vuol dire "non modificarmi"."""
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
DOMAIN_COLORS = {
    "Production": ("#2F8F2F", "#EAF7EA"),  # tupla
    "Sales": ("#C51B8A", "#FDE0EF"),
}

"""a storia che i dati raccontano: oggi gli ordini dei clienti si gestiscono con dei fogli Excel. 
Il progetto "Online shop" li sostituisce 
con un WebShop a partire dal 1° aprile 2027. A marzo 2027 c'è un mese di migrazione 
dei dati dal vecchio al nuovo sistema. Confrontando ottobre 2026 con giugno 2027,
 il grafo delle differenze mostrerà i fogli Excel in rosso e il WebShop in verde."""

# sto definendo 3 funzioni per avere i dizionari di questi oggetti con lo stile che voglio
# in modo da distinguerli.
"""
NOTA id_ con il trattino basso: id è già il nome di una funzione di Python. Chiamare un parametro 
id la "nasconderebbe". Il trattino basso finale è la convenzione per evitarlo, come class_ 
o type_
"""


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


# nella mia azienda i macro pro sono production e sales.


def process(id_, label, domain):
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


# i processi di sales sono customer orders, invoicing. il customer crea il processo
# di production planning , parte del macro processo production.


def system(id_, label, domain, start=ALWAYS_START, end=ALWAYS_END, project=None):  # nota il default
    # é che non ci sono progetti che modificano.
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


# i sistemi sono usati dai processi. il sistema per prodcution planning è millcontrol.
# il sistema per invoicing è billing che è con la banca come vendor.

NODES = [  # è una list di dizionari, ogni dizionario è un nodo del grafo=una riga dell'Excel
    macro_process("MP_PROD", "Production", "Production"),
    macro_process("MP_SALES", "Sales", "Sales"),
    process("P_PLAN", "Production\nplanning", "Production"),
    process("P_ORDERS", "Customer\norders", "Sales"),
    process("P_INVOICE", "Invoicing", "Sales"),
    system("MILL", "MillControl", "Production"),
    system("BILLING", "BillingPro", "Sales"),
    # Old system: used until the day before the go-live: gli ordini sono gestiti con excel.
    system("SHEETS", "Order\nspreadsheets", "Sales", end=MIGRATION_END, project="PRJ_SHOP"),
    # New system: installed one month before the go-live, to receive the old data.
    # il progetto SHOP cambia questo sistema.
    system("SHOP", "WebShop", "Sales", start=MIGRATION_START, project="PRJ_SHOP"),
    # External system: style left empty on purpose, the program must use the defaults. Non usa
    # system() proprio perché deve avere lo stile vuoto: è il caso di prova per i valori
    # predefiniti di Parametres. Le chiavi che mancano nel dizionario (Shape, Color…)
    # diventeranno celle vuote quando pandas costruirà la tabella excel
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


def main():
    sheets = {
        "Noeuds": pd.DataFrame(NODES, columns=NODE_COLUMNS),
        "Liens": pd.DataFrame(LINKS, columns=LINK_COLUMNS),
        "Projets": pd.DataFrame(PROJECTS),
        "Parametres": pd.DataFrame(PARAMETERS, columns=["Parametre", "Valeur", "Description"]),
    }

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        for name, table in sheets.items():
            table.to_excel(writer, sheet_name=name, index=False)

    print(f"Created {OUTPUT_FILE.name}")
    for name, table in sheets.items():
        print(f"  {name}: {len(table)} rows")


if __name__ == "__main__":
    main()
