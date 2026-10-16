"""Create data/sample_pastificio.xlsx: a small, entirely FICTIONAL company.

A pasta factory with a few processes, the IT systems that support them and
the data flows between them. One project replaces an old system with a new
one, so the picture changes after this trasformation project is over.

Run from the project folder:

    python scripts/make_sample_data.py
"""

# Il testo tra """...""" qui sopra è la DOCSTRING del modulo: la documentazione del file.
# Python la conserva, e help() e VSCode la mostrano. Va messa in cima al file, oppure subito
# dopo "def" o "class": negli altri punti è solo una stringa che Python valuta e ignora.

# IMPORT
# - "import X" è simile a #include, ma crea anche un namespace: pandas.DataFrame, come std::vector.
# - "from X import Y" porta direttamente il nome Y: si scrive date(...) e non datetime.date(...)
#   (simile a "using std::vector;").
# - "as pd" è un alias; "pd" per pandas è una convenzione universale.
# - Ordine: prima la libreria standard, riga vuota, poi le librerie esterne
#   (Ruff lo corregge da solo al salvataggio).
from datetime import date
from pathlib import Path

import pandas as pd

# Where the file is written: <project folder>/data/sample_pastificio.xlsx
# L'operatore "/" tra percorsi non è una divisione: Path lo RIDEFINISCE per unire i pezzi di un
# percorso (operator overloading, come std::string con "+"). Funziona su Windows e Linux.
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
# date(anno, mese, giorno) crea un oggetto data (come std::chrono::year_month_day, ma più semplice).
ALWAYS_START = date(2026, 1, 1)
ALWAYS_END = date(2100, 12, 31)

# Column names of each sheet, in French like the real working file.
# Cells we don't fill stay empty: the program will use the defaults
# from the "Parametres" sheet.
"""Creo le liste. Python non ha const quindi l a convenzione è scrivere i nomi TUTTO_MAIUSCOLO: 
vuol dire "non modificarmi"."""
# [...] è una LISTA: l'equivalente di std::vector, ma può contenere oggetti di tipo qualsiasi
# e cresce da sola.
# La virgola dopo l'ultimo elemento ("trailing comma") dice a Ruff "tieni questa lista su più
# righe": un elemento per riga. Più lungo, ma nei diff di Git aggiungere una colonna cambia
# una sola riga.
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
# {chiave: valore} è un DIZIONARIO, simile a std::map<std::string, ...>; i valori possono
# essere di tipi diversi nello stesso dizionario.
# ("#2F8F2F", "#EAF7EA") è una TUPLA: come una lista ma IMMUTABILE (simile a std::pair/tuple).
# COLORI "#RRGGBB": esadecimale RGB, come in HTML/CSS. Ogni coppia va da 00 a FF (0-255, come
# un uint8_t). Es. #2B8CBE = rosso 43, verde 140, blu 190 -> azzurro. Maiuscole o minuscole
# sono uguali. VSCode mostra accanto un quadratino colorato (color decorator) e cliccandolo
# si apre un selettore di colore. Molti colori vengono da ColorBrewer (colorbrewer2.org).
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
# FUNZIONI: "def nome(parametri):". Come in C++ ma senza tipi e senza { }: il corpo è definito
# dall'INDENTAZIONE (4 spazi). Nessun tipo di ritorno dichiarato: "return" restituisce
# qualsiasi cosa (qui un dizionario = una riga dell'Excel).


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
    # UNPACKING: "spacchetta" la tupla in due variabili in un colpo solo.
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


# i processi di sales sono customer orders, invoicing. il customer crea il processo
# di production planning , parte del macro processo production.

# PARAMETRI CON DEFAULT: start=ALWAYS_START si può omettere nella chiamata, come in C++.
# ARGOMENTI CON NOME: nella chiamata si può scrivere project="PRJ_SHOP" e saltare quelli che
# non servono (es. end resta al default). In C++ non si può.
# I default qui sono DATE (immutabili), quindi va bene. Trappola da evitare (Ruff B006):
# un default MUTABILE come items=[] viene creato UNA volta sola e si "ricorda" le chiamate
# precedenti. Soluzione: items=None e poi "if items is None: items = []".
# None è il "niente" di Python (simile a nullptr): nell'Excel diventa una cella vuota.


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

# Solo source e target sono obbligatori, tutto il resto ha un default: le frecce semplici si
# scrivono in una riga, link("P_PLAN", "MILL"), quelle speciali indicano solo ciò che cambia.
# La definizione è su più righe perché non sta in 100 caratteri: Ruff l'ha divisa così.


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
        # (la colonna "Domaine" dei link resta vuota di proposito: qui non serve, e il
        # programma deve comunque accettarla vuota)
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


# ARGOMENTI POSIZIONALI + CON NOME insieme: i primi vanno IN ORDINE (source, target, label),
# gli altri PER NOME e in qualsiasi ordine. Regola: prima i posizionali, poi quelli con nome.
# "\n" nelle etichette è un a capo, come in C++: Graphviz scriverà l'etichetta su due righe.
# Accenti ("échange de données"): in Python 3 tutte le stringhe sono Unicode, funzionano e basta.
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
# Lista di TUPLE: ogni parametro ha sempre 3 valori, e una tupla è perfetta per un "record"
# corto e fisso (più compatta di un dizionario con 3 chiavi ripetute 11 volte).
# La colonna Valeur contiene TIPI DIVERSI (testo, numeri, una data): in Excel è normale,
# il programma dovrà convertirla a seconda del parametro.
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


# "def main()" è solo una CONVENZIONE per tenere il codice "da eseguire" in un posto ordinato:
# in Python non esiste un main() speciale come in C++ (vedi l'"if" in fondo al file).
def main():
    # DataFrame = la tabella di pandas (righe e colonne con un nome, un foglio Excel in memoria).
    # Da una lista di dizionari: ogni dizionario diventa una riga. "columns=" impone l'elenco e
    # l'ordine delle colonne: quelle che un dizionario non ha (es. Shape per BANK) restano vuote.
    # Da una lista di tuple (PARAMETERS) basta dare i nomi delle colonne.
    #
    # LIST COMPREHENSION (qui non serve, ma la troverai ovunque). Questo ciclo:
    #     names = []
    #     for name, value, text in PARAMETERS:
    #         names.append(name)
    # si scrive in una riga:
    #     names = [name for name, value, text in PARAMETERS]
    # Con un filtro: [n for n in NODES if n["Actif"]]. In C++: std::transform / ranges (C++20).
    sheets = {
        "Noeuds": pd.DataFrame(NODES, columns=NODE_COLUMNS),
        "Liens": pd.DataFrame(LINKS, columns=LINK_COLUMNS),
        "Projets": pd.DataFrame(PROJECTS),
        "Parametres": pd.DataFrame(PARAMETERS, columns=["Parametre", "Valeur", "Description"]),
    }

    # CONTEXT MANAGER "with": all'uscita dal blocco il file viene chiuso e salvato, anche se
    # dentro c'è un errore. È il RAII del C++ (un std::ofstream che si chiude nel distruttore).
    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        # .items() dà le coppie (chiave, valore) del dizionario; l'unpacking le separa subito.
        # In C++: for (auto& [name, table] : sheets)
        for name, table in sheets.items():
            table.to_excel(writer, sheet_name=name, index=False)

    # F-STRING: la "f" davanti permette di inserire espressioni tra { } (come std::format C++20).
    # len() restituisce la lunghezza di qualsiasi contenitore: qui il numero di righe.
    print(f"Created {OUTPUT_FILE.name}")
    for name, table in sheets.items():
        print(f"  {name}: {len(table)} rows")


# In Python TUTTO il codice di un file viene eseguito quando il file viene caricato, anche
# quando viene importato da un altro file. __name__ vale "__main__" solo se il file è stato
# LANCIATO direttamente (python scripts/make_sample_data.py). Così l'Excel viene creato solo
# lanciando lo script, non se un test lo importa per leggere NODES.
if __name__ == "__main__":
    main()
