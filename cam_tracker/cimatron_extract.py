"""
cam_tracker/cimatron_extract.py
================================
Estrattore parametri NC da Cimatron via SDK COM (standalone, gira su CAM35).

Iniziativa "Classificazione percorsi NC + MAIN builder" — Fase 1.
Mappa dati e verdetto fonti: DATI_ESTRAIBILI_CIMATRON.md.
Ricetta d'accesso verificata: memoria progetto cimatron-sdk-ncmodel.

Flusso:
  1. Activation context reg-free COM (le classi Cimatron non sono nel registro)
  2. AppAccess -> GetActiveApplication -> IApplication (istanza già aperta)
  3. Documento attivo: path/titolo/tipo (procede solo se cmNc)
  4. IPdm.GetModel(path) -> QI INcModel -> GetProcessManagerAsXML2 -> XML UTF-16
  5. parse_xml2(): funzione PURA XML -> dict secondo la mappa concordata
     (testabile offline su un dump salvato, senza Cimatron)
  6. SavePicture2 -> PNG anteprima del documento
  7. Salvataggio con STORICO: parametri_cam/<commessa>_<posizione>/<ts>.json
     + latest.json (decisione 2026-07-10: ogni estrazione conservata, la
     "lampadina rotture" deve vedere i parametri di ALLORA)

Uso CLI:
    python cimatron_extract.py                    # estrae dal doc attivo
    python cimatron_extract.py --no-png           # senza anteprima
    python cimatron_extract.py --solo-parse F.xml # test offline del parser
    python cimatron_extract.py --out DIR          # cartella output custom

NON tocca nulla dei flussi DMG Desk esistenti: modulo nuovo, additivo.
Tutte le chiamate COM sono in sola lettura (nessun Save/modifica documento).
"""

import argparse
import ctypes
import json
import os
import re
import shutil
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

VERSIONE_ESTRATTORE = "1.4"   # 1.1: +passo_orizzontale; 1.2: +ID 21341;
                              # 1.3: tutti i documenti aperti + parametri MW;
                              # 1.4: TUTTI I SETUP/FASI del documento (prima
                              #      solo il primo Setup: fasi 2/3 invisibili)

# Cartella Program di Cimatron: auto-detect versione più recente installata
# (stesso criterio di cam_tracker: detect_cimatron_installations).
CIMATRON_BASE = Path(os.environ.get(
    "CIMATRON_INSTALL_BASE", r"C:\Program Files\Cimatron\Cimatron"))

# Manifest reg-free con TUTTI gli assembly SDK (già nel repo, provato nello spike)
MANIFEST = Path(__file__).parent / "cimatron_query.manifest"

# Output di default: sottocartella del cam_tracker (poi inviata/letta da DD)
OUT_DIR_DEFAULT = Path(__file__).parent / "parametri_cam"


# ─────────────────────────────────────────────────────────────────────────────
# Mappa ID parametri Cimatron (stabili, indipendenti dalla lingua UI).
# Verificati su dump reale 2026-07-10 — vedi DATI_ESTRAIBILI_CIMATRON.md.
# Dove lo stesso ID è riusato (55, 57) si disambigua con Name-contains.
# ─────────────────────────────────────────────────────────────────────────────
ID_COMMENTO      = "30008"
ID_STATO_CALCOLO = "30009"
ID_NUMERO_PROC   = "30069"

ID_OFFSET_PARTE     = "55"     # Name senza 'Pareti' = combinato (modo Base)
ID_OFFSET_FONDO     = "20391"  # modo Avanzate
ID_OFFSET_CONTORNO  = "20"
ID_OFFSET_CONTROLLO = "21367"
ID_OFFSET_SUP_MW    = "21341"  # 'Offset Superfici' delle Multi Asse/MW
                               # (dettatura #1 2026-07-13: l'offset 0.1 delle
                               # prefiniture figura sta qui, non in ID 55)
ID_MODO_OFFSET      = "20568"  # Twig 'Offset e Tolleranza Superfici': Base/Avanzate

ID_TOLL_SUPERFICI   = "57"     # Name con 'Guida' = toll_guida (MW/5X)
ID_TOLL_CTRL_GREZZO = "218"
ID_TOLL_CONTORNO    = "25"
ID_TOLL_LTOL        = "20620"
ID_MAX_GAP          = "20542"

ID_UT_TIPO      = "20766"
ID_UT_DIAMETRO  = "3021"
ID_UT_RAGGIO    = "3031"
ID_UT_LUNG_UTILE = "3023"
ID_UT_SPORGENZA = "20984"   # 'Lungh. Tot. F.P.' = fuori pinza
ID_UT_VITA      = "3026"
ID_UT_DENTI     = "3041"
ID_UT_NUMERO_T  = "3058"
ID_UT_PINZA     = "20985"
ID_UT_ALIAS     = "3059"    # 'Commento Utensile' = alias CNC
ID_UT_GAMBO     = "21431"

ID_AVANZAMENTO  = "3201"
ID_ROTAZIONE    = "3207"
ID_VC           = "3202"
ID_REFRIGERANTE = "3209"

ID_PASSO_Z       = "3409"
ID_PASSO_Z_FISSO = "3410"
ID_PASSO_LAT     = "3411"
ID_PASSO_ORIZZ   = "3408"   # 'Passo Orizz.' (finiture aree orizzontali) → ae
ID_METODO_TAGLIO = "27"
ID_SPESS_GREZZO  = "125"

ID_SR_NOME = "3217"

ID_GEO_SUP_PARTE  = "43"
ID_GEO_SUP_CTRL   = "44"
ID_GEO_CONTORNI   = "35"
ID_GEO_TASCHE     = "21347"
ID_GEO_SEG_RIP    = "21402"

# Forature: cicli e posizioni (per foro)
ID_FOR_TIPO   = "30037"
ID_FOR_PASSO  = "30042"
ID_LOC_DESIGN = "30048"   # 'Sgrossa e Finisci' = designazione (es. M8)
ID_LOC_X, ID_LOC_Y, ID_LOC_Z = "30049", "30050", "30051"
ID_LOC_I, ID_LOC_J, ID_LOC_K = "30052", "30053", "30054"
ID_FIL_DIA   = "30061"
ID_FIL_PASSO = "30063"
ID_FIL_POS   = "30084"
ID_FIL_TOLL  = "20783"


def _num(v):
    """Converte in float se possibile, altrimenti ritorna la stringa (o None)."""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return s


def _intero(v):
    """Come _num ma normalizza i float integrali a int (T355.0 -> 355)."""
    n = _num(v)
    if isinstance(n, float) and n.is_integer():
        return int(n)
    return n


# ─────────────────────────────────────────────────────────────────────────────
# PARSER PURO: XML (GetProcessManagerAsXML2) -> dict secondo la mappa.
# Nessuna dipendenza COM: testabile offline su un dump salvato.
# ─────────────────────────────────────────────────────────────────────────────

def _params_by_id(root_el):
    """Indice {id: [(name, value), ...]} di tutti i Parameter sotto root_el."""
    out = {}
    for el in root_el.iter("Parameter"):
        pid = el.get("ID")
        if pid:
            out.setdefault(pid, []).append((el.get("Name") or "", el.get("Value")))
    return out


def _pick(idx, pid, name_contains=None, name_excludes=None):
    """Primo valore per ID, con filtro opzionale sul Name (riuso ID 55/57)."""
    for name, val in idx.get(pid, []):
        if name_contains and name_contains not in name:
            continue
        if name_excludes and name_excludes in name:
            continue
        return val
    return None


def _parse_setup(setup_el):
    """SetupParameters -> dict {nome: valore} + chiavi note normalizzate."""
    raw = {}
    sp = setup_el.find("SetupParameters")
    if sp is None:
        return {}
    for el in sp:
        nome = el.get("Name") or el.tag
        if el.get("Value") is not None:
            raw[nome] = el.get("Value")
        elif el.get("X") is not None:  # es. Zero Pezzo
            raw[nome] = {k: v for k, v in el.attrib.items() if k != "Name"}
    setup = {"raw": raw}
    # chiavi note per contains (i Name possono variare leggermente col template)
    for chiave, needle in [("materiale", "ateriale"), ("macchina", "acchina"),
                           ("post", "ost"), ("adattatore", "dattatore"),
                           ("report", "eport"), ("fase_sr", "SR")]:
        for nome, val in raw.items():
            if needle in nome and isinstance(val, str) and val:
                setup.setdefault(chiave, val)
                break
    return setup


def _parse_utensile(proc_el):
    """Branch 'Utensili e Pinze': nome completo (Value del Branch) + dettagli."""
    for br in proc_el.iter("Branch"):
        if (br.get("Name") or "") != "Utensili e Pinze":
            continue
        idx = _params_by_id(br)
        denti = _num(_pick(idx, ID_UT_DENTI))
        return {
            "nome": br.get("Value") or None,
            "alias": _pick(idx, ID_UT_ALIAS),
            "numero_t": _intero(_pick(idx, ID_UT_NUMERO_T)),
            "tipo": _pick(idx, ID_UT_TIPO),
            "diametro": _num(_pick(idx, ID_UT_DIAMETRO)),
            "raggio": _num(_pick(idx, ID_UT_RAGGIO)),
            "denti": _intero(denti) if denti is not None else None,
            "lunghezza_utile": _num(_pick(idx, ID_UT_LUNG_UTILE)),
            "sporgenza_fp": _num(_pick(idx, ID_UT_SPORGENZA)),
            "diametro_gambo": _num(_pick(idx, ID_UT_GAMBO)),
            "vita_teorica": _num(_pick(idx, ID_UT_VITA)),
            "pinza": _pick(idx, ID_UT_PINZA),
        }
    return None


def _parse_offset_toll(proc_el):
    """Twig 'Offset e Tolleranza Superfici' + Gestione Contorni + Param. Utente."""
    modo = None
    for tw in proc_el.iter("Twig"):
        if tw.get("ID") == ID_MODO_OFFSET:
            modo = tw.get("Value")
            break
    idx = _params_by_id(proc_el)
    offset = {
        "modo": modo,
        "parte": _num(_pick(idx, ID_OFFSET_PARTE, name_excludes="Pareti")),
        "parete": _num(_pick(idx, ID_OFFSET_PARTE, name_contains="Pareti")),
        "fondo": _num(_pick(idx, ID_OFFSET_FONDO)),
        "contorno": _num(_pick(idx, ID_OFFSET_CONTORNO)),
        "controllo": _num(_pick(idx, ID_OFFSET_CONTROLLO)),
        "superfici_mw": _num(_pick(idx, ID_OFFSET_SUP_MW)),
    }
    tolleranze = {
        "superfici": _num(_pick(idx, ID_TOLL_SUPERFICI, name_excludes="Guida")),
        "guida": _num(_pick(idx, ID_TOLL_SUPERFICI, name_contains="Guida")),
        "controllo_grezzo": _num(_pick(idx, ID_TOLL_CTRL_GREZZO)),
        "contorno": _num(_pick(idx, ID_TOLL_CONTORNO)),
        "l_tol": _num(_pick(idx, ID_TOLL_LTOL)),
        "max_gap": _num(_pick(idx, ID_MAX_GAP)),
    }
    return offset, tolleranze


def _parse_macchina(proc_el):
    idx = _params_by_id(proc_el)
    avanz = _num(_pick(idx, ID_AVANZAMENTO))
    rot = _num(_pick(idx, ID_ROTAZIONE))
    denti = _num(_pick(idx, ID_UT_DENTI))
    fz = None
    try:
        if avanz and rot and denti:
            fz = round(float(avanz) / (float(rot) * float(denti)), 4)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return {
        "avanzamento": avanz,
        "rotazione": rot,
        "vc": _num(_pick(idx, ID_VC)),
        "fz": fz,
        "refrigerante": _pick(idx, ID_REFRIGERANTE),
    }


def _parse_traiettoria(proc_el):
    idx = _params_by_id(proc_el)
    return {
        "passo_z": _num(_pick(idx, ID_PASSO_Z)),
        "passo_z_fisso": _num(_pick(idx, ID_PASSO_Z_FISSO)),
        "passo_laterale": _num(_pick(idx, ID_PASSO_LAT)),
        "passo_orizzontale": _num(_pick(idx, ID_PASSO_ORIZZ)),
        "metodo_taglio": _pick(idx, ID_METODO_TAGLIO),
        "spessore_grezzo": _num(_pick(idx, ID_SPESS_GREZZO)),
    }


def _parse_geometria(proc_el):
    for br in proc_el.iter("Branch"):
        if (br.get("Name") or "") == "Geometria":
            idx = _params_by_id(br)
            return {
                "superfici_parte": _num(_pick(idx, ID_GEO_SUP_PARTE)),
                "superfici_controllo": _num(_pick(idx, ID_GEO_SUP_CTRL)),
                "contorni": _num(_pick(idx, ID_GEO_CONTORNI)),
                "tasche": _num(_pick(idx, ID_GEO_TASCHE)),
                "segmenti_ripresa": _num(_pick(idx, ID_GEO_SEG_RIP)),
            }
    return None


def _parse_foratura(proc_el):
    """Cicli di foratura/filettatura con dettaglio PER FORO (blocco B)."""
    cicli = []
    for cd in proc_el.iter("CycleData"):
        idx = _params_by_id(cd)
        fori = []
        for loc in cd.iter("LocationData"):
            lidx = _params_by_id(loc)
            fori.append({
                "x": _num(_pick(lidx, ID_LOC_X)),
                "y": _num(_pick(lidx, ID_LOC_Y)),
                "z": _num(_pick(lidx, ID_LOC_Z)),
                "i": _num(_pick(lidx, ID_LOC_I)),
                "j": _num(_pick(lidx, ID_LOC_J)),
                "k": _num(_pick(lidx, ID_LOC_K)),
                "designazione": _pick(lidx, ID_LOC_DESIGN),
            })
        filetto = None
        dia_fil = _num(_pick(idx, ID_FIL_DIA))
        if dia_fil:
            filetto = {
                "diametro_nominale": dia_fil,
                "passo": _num(_pick(idx, ID_FIL_PASSO)),
                "posizione": _pick(idx, ID_FIL_POS),
                "tolleranza": _num(_pick(idx, ID_FIL_TOLL)),
            }
        cicli.append({
            "tipo": _pick(idx, ID_FOR_TIPO),
            "passo_peck": _num(_pick(idx, ID_FOR_PASSO)),
            "n_fori": len(fori),
            "fori": fori,
            "filetto": filetto,
        })
    if not cicli:
        return None
    designazioni = sorted({f["designazione"] for c in cicli for f in c["fori"]
                           if f.get("designazione")})
    return {"cicli": cicli,
            "n_fori_totale": sum(c["n_fori"] for c in cicli),
            "designazioni": designazioni}


def _parse_procedura(proc_el, pu_nome, seq_globale):
    """Un elemento <Procedure> -> record della mappa."""
    nome = proc_el.get("Name") or ""
    # sotto-strategia = nome senza il suffisso _<numero>
    sotto = re.sub(r"_\d+$", "", nome)
    idx_sum = _params_by_id(proc_el)

    # strategia principale/sub: primi due Parameter SENZA ID del sommario
    # (in XML2 i Name di questi due sono inaffidabili, i Value sono giusti —
    # verificato su dump reale: 'Sgrossatura' / 'Sgrossatura Spirale')
    principale = None
    pp = proc_el.find("ProcedureParameters")
    if pp is not None:
        senza_id = [el.get("Value") for el in pp.findall("Parameter")
                    if not el.get("ID") and el.get("Value")]
        if senza_id:
            principale = senza_id[0]

    commento = _pick(idx_sum, ID_COMMENTO)
    if commento and commento.strip().lower() == "nessun testo":
        commento = None

    numero = _pick(idx_sum, ID_NUMERO_PROC)
    try:
        numero = int(numero)
    except (TypeError, ValueError):
        m = re.search(r"_(\d+)$", nome)
        numero = int(m.group(1)) if m else None

    offset, tolleranze = _parse_offset_toll(proc_el)
    return {
        "seq": seq_globale,
        "pu": pu_nome,
        "numero": numero,
        "nome": nome,
        "strategia": principale,
        "sotto_strategia": sotto,
        "commento": commento,
        "sr": _pick(idx_sum, ID_SR_NOME),
        "stato_calcolo": _pick(idx_sum, ID_STATO_CALCOLO),
        "utensile": _parse_utensile(proc_el),
        "offset": offset,
        "tolleranze": tolleranze,
        "macchina": _parse_macchina(proc_el),
        "traiettoria": _parse_traiettoria(proc_el),
        "geometria": _parse_geometria(proc_el),
        "foratura": _parse_foratura(proc_el),
    }


def parse_xml2(xml_path) -> dict:
    """
    Funzione PURA: file XML di GetProcessManagerAsXML2 -> dict mappa completa.
    Ordine procedure = ordine documento (sequenza reale programmata).

    v1.4: l'XML contiene TUTTI i Setup del documento (F1/F2/F3... = le FASI,
    più eventuali sub-setup F1_0...) — si leggono tutti; prima solo il primo
    veniva parsato (bug scoperto sul campo: "nessun dato per la fase 3").
    Ogni procedura porta i campi `setup` (nome, es. F3) e `fase` (cifre, es. 3).
    """
    tree = ET.parse(str(xml_path))   # gestisce UTF-16 dall'intestazione
    root = tree.getroot()

    procedure = []
    setups = []
    seq = 0

    def visita(contenitore, pu_nome, setup_nome, fase):
        nonlocal seq
        for el in contenitore:
            if el.tag == "Procedure":
                seq += 1
                rec = _parse_procedura(el, pu_nome, seq)
                rec["setup"] = setup_nome
                rec["fase"] = fase
                procedure.append(rec)
            elif el.tag == "ToolPath":
                folder = el.find("ToolpathFolder")
                if folder is not None:
                    visita(folder, el.get("Name") or "?", setup_nome, fase)
            elif el.tag in ("SetupFolder", "ToolpathFolder"):
                visita(el, pu_nome, setup_nome, fase)

    for setup_el in root.iter("Setup"):
        nome_setup = setup_el.get("Name") or "?"
        # fase = prime cifre nel nome del setup (F1→1, F2→2, F1_0→1)
        m = re.search(r"(\d+)", nome_setup)
        fase = m.group(1) if m else None
        info = _parse_setup(setup_el)
        info["nome"] = nome_setup
        info["id"] = setup_el.get("ID")
        setups.append(info)
        visita(setup_el, "(setup)", nome_setup, fase)

    return {
        "versione_estrattore": VERSIONE_ESTRATTORE,
        "setup": setups[0] if setups else {},   # compat: primo setup
        "setups": [{k: v for k, v in s.items() if k != "raw"} for s in setups],
        "n_procedure": len(procedure),
        "procedure": procedure,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Aggancio COM (solo lettura). Ricetta verificata nello spike 2026-07-10.
# ─────────────────────────────────────────────────────────────────────────────

class _ACTCTXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.ULONG), ("dwFlags", wintypes.DWORD),
                ("lpSource", wintypes.LPCWSTR),
                ("wProcessorArchitecture", wintypes.USHORT),
                ("wLangId", wintypes.WORD),
                ("lpAssemblyDirectory", wintypes.LPCWSTR),
                ("lpResourceName", wintypes.LPCWSTR),
                ("lpApplicationName", wintypes.LPCWSTR),
                ("hModule", wintypes.HMODULE)]


def _cimatron_program_dir() -> Path | None:
    """Versione installata più recente (come cam_tracker auto-detect)."""
    if not CIMATRON_BASE.exists():
        return None
    versioni = sorted([d for d in CIMATRON_BASE.iterdir()
                       if d.is_dir() and (d / "Program").exists()],
                      key=lambda d: d.name, reverse=True)
    return versioni[0] / "Program" if versioni else None


def attiva_actctx(program_dir: Path) -> bool:
    """Activation context reg-free per gli assembly interop Cimatron."""
    k32 = ctypes.windll.kernel32
    k32.CreateActCtxW.restype = ctypes.c_void_p
    ctx = _ACTCTXW(cbSize=ctypes.sizeof(_ACTCTXW),
                   dwFlags=0x004,  # ASSEMBLY_DIRECTORY_VALID
                   lpSource=str(MANIFEST),
                   lpAssemblyDirectory=str(program_dir))
    h = k32.CreateActCtxW(ctypes.byref(ctx))
    if h in (None, ctypes.c_void_p(-1).value):
        return False
    cookie = ctypes.c_size_t()
    return bool(k32.ActivateActCtx(ctypes.c_void_p(h), ctypes.byref(cookie)))


# Strategie i cui parametri vivono nell'archivio ModuleWorks (fuori dall'XML2)
_STRATEGIE_MW = ("MULTI ASSE", "LOCALI", "RIPRESA GUIDATA")
_MAX_CHIAMATE_MW = 40   # tetto per estrazione (bound sul tempo)


def _parse_mw_raw(raw_bytes: bytes) -> dict:
    """Dump di GetModuleworksParameters -> {chiave: numero}, SOLO se testo/XML.

    ATTENZIONE (verificato 2026-07-17 sul campo): su Cimatron 2025 questo dump è
    un blob BINARIO proprietario — header 'ZSTDZSTD' + frame Zstandard + payload
    'MWGL' (ModuleWorks), con i parametri come double binari NON etichettati.
    Non è estraibile come parametri nominati senza reverse-engineering del layout
    (fragile e versione-dipendente) → per quel formato ritorna {} (niente dati
    inventati e niente spazzatura da un regex su binario). Resta il parsing
    testo/XML per eventuali versioni Cimatron che restituiscono un formato leggibile.
    Funzione PURA: testabile offline su un dump salvato, senza COM.
    """
    import re as _re
    if not raw_bytes:
        return {}
    # Blob binario ModuleWorks (ZSTD/MWGL): non un formato a parametri nominati.
    head = raw_bytes[:8]
    if head[:4] == b"ZSTD" or head[:4] == b"MWGL" or b"\x28\xb5\x2f\xfd" in head:
        return {}
    try:
        raw = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return {}   # binario ignoto: non produrre coppie fasulle
    trovati: dict = {}
    try:
        radice = ET.fromstring(raw)
        for el in radice.iter():
            nome = (el.get("Name") or el.get("name") or el.tag or "")
            val = el.get("Value") or el.get("value") or (el.text or "").strip()
            if _re.search(r"offset|stock|toleran|allowance", nome, _re.I):
                n = _num(val)
                if isinstance(n, float):
                    trovati[nome] = n
    except ET.ParseError:
        for m in _re.finditer(
                r"([\w .%-]*(?:offset|stock|toleran|allowance)[\w .%-]*)\s*[:=]\s*(-?\d+[.,]?\d*)",
                raw, _re.I):
            trovati[m.group(1).strip()] = _num(m.group(2))
    return trovati


def _arricchisci_mw(ncm, dati, proj_dir: Path):
    """Offset delle procedure MW (modo Avanzate) letto dal BLOB
    GetModuleworksParameters — NON via GetProcedureParameter.

    Perche' il blob e non l'ID (deciso 2026-07-17):
      - GetProcedureParameter APRE/chiude il pannello parametri di Cimatron a ogni
        chiamata (flickering della UI) → inaccettabile in produzione;
      - e per l'offset MW ritorna comunque 0 (ID 21341 non e' quel campo).
    Il valore vero ('Offset Superfici Lavoro', es. 0.1 prefinitura vs 0 finitura)
    vive nel blob ModuleWorks, che GetModuleworksParameters scrive SENZA toccare
    la UI.

    Formato: header 'ZSTDZSTD' (8 byte) + frame Zstandard. Decompresso (sempre
    33608 byte, stessa struttura per tutte le strategie ModuleWorks di questa
    versione), il double 'Offset Superfici Lavoro' sta a **byte 597** — verificato
    diffando procedure di test con offset 0/0.1/0.2/1.0, sia Multi Asse Adv. sia
    Operazioni Locali: entrambe tracciano l'offset a 597.
    Valore validato nel range plausibile [-3, 3] mm; fuori range → None (probabile
    cambio di layout in una futura versione ModuleWorks).
    """
    import struct
    try:
        import zstandard as _zstd
    except Exception:
        log.warning("cimatron_extract: zstandard non disponibile → offset MW non letto")
        return {"letti": 0}

    POS_OFFSET_MW = 597   # byte del double 'Offset Superfici Lavoro' nel blob decompresso

    def _leggi_offset(num, pos):
        tmp = Path(tempfile.gettempdir()) / f"cimx_mw_{os.getpid()}_{num}.bin"
        try:
            if tmp.exists():
                tmp.unlink()
            ncm.GetModuleworksParameters(int(num), str(tmp))
            raw = tmp.read_bytes()
            if len(raw) < 16 or raw[:4] != b"ZSTD":
                return None
            blob = _zstd.ZstdDecompressor().decompress(raw[8:])
            if pos + 8 > len(blob):
                return None
            val = struct.unpack("<d", blob[pos:pos + 8])[0]
            return round(val, 5) if -3.0 <= val <= 3.0 else None
        except Exception:
            return None
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass

    letti = 0
    for proc in dati.get("procedure", []):
        sotto = (proc.get("sotto_strategia") or "").upper()
        if not any(k in sotto for k in _STRATEGIE_MW):
            continue
        off = proc.get("offset") or {}
        if any(v is not None for k, v in off.items() if k not in ("modo",)):
            continue           # già popolato dall'XML2 (modo Base)
        num = proc.get("numero")
        if num is None:
            continue
        val = _leggi_offset(num, POS_OFFSET_MW)
        if val is not None:
            off["superfici_mw"] = val
            proc["offset"] = off
            letti += 1
    return {"letti": letti}


def _salva_estrazione(dati, out_dir: Path, commessa, posizione, icd_attivo, con_png):
    """Salvataggio con storico + latest (+ anteprima solo per il doc attivo)."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    proj_dir = out_dir / f"{commessa}_{posizione}"
    proj_dir.mkdir(parents=True, exist_ok=True)

    png_path = None
    if con_png and icd_attivo is not None:
        try:
            png_path = proj_dir / f"{ts}_anteprima.png"
            icd_attivo.SavePicture2(str(png_path), 0, 1.0)
            if not png_path.exists() or png_path.stat().st_size == 0:
                png_path = None
        except Exception:
            png_path = None
    dati["documento"]["anteprima_png"] = png_path.name if png_path else None

    json_path = proj_dir / f"{ts}.json"
    tmp_json = json_path.with_suffix(".tmp")
    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=1)
    os.replace(tmp_json, json_path)
    shutil.copyfile(json_path, proj_dir / "latest.json")
    if png_path:
        shutil.copyfile(png_path, proj_dir / "latest_anteprima.png")
    return json_path, png_path, proj_dir


def _estratto_di_recente(out_dir: Path, commessa, posizione, minuti: int) -> bool:
    latest = out_dir / f"{commessa}_{posizione}" / "latest.json"
    try:
        return (time.time() - latest.stat().st_mtime) < minuti * 60
    except OSError:
        return False


def estrai_da_cimatron(out_dir: Path, con_png: bool = True,
                       min_intervallo_min: int = 20) -> dict:
    """
    v1.3: estrae TUTTI i documenti NC aperti nell'istanza Cimatron attiva
    (GetOpenDocuments → path; GetModel(path) per ciascuno), con throttle per
    documento; anteprima PNG solo per il documento attivo; parametri MW via
    GetModuleworksParameters dove l'XML2 non li ha.
    NB: documenti in ALTRE istanze Cimatron restano irraggiungibili (limite
    del broker AppAccess — documentato).
    Ritorna {"ok", "motivo", "documenti": [risultato per doc...]}.
    """
    program_dir = _cimatron_program_dir()
    if program_dir is None:
        return {"ok": False, "motivo": "Cimatron non installato (Program dir non trovata)"}
    if not MANIFEST.exists():
        return {"ok": False, "motivo": f"manifest mancante: {MANIFEST}"}
    if not attiva_actctx(program_dir):
        return {"ok": False, "motivo": "ActivateActCtx fallita"}

    sys.path.insert(0, str(program_dir))
    import clr  # pythonnet
    clr.AddReference("interop.CimAppAccess")
    clr.AddReference("interop.CimatronE")
    clr.AddReference("interop.CimNcAPI")
    import interop.CimAppAccess as CAA
    import interop.CimatronE as CE
    import interop.CimNcAPI as NC

    # Aggancio con retry + fallback. Caso reale scoperto sul campo (2026-07-13):
    # se l'istanza Cimatron REGISTRATA come attiva viene chiusa, il broker
    # AppAccess resta orfano e GetActiveApplication() torna None finché
    # l'operatore non interagisce con un'altra finestra Cimatron (che si
    # ri-registra). Non è un errore: si segnala e si riproverà.
    iapp = None
    ultimo_err = None
    visto_none = False
    for tentativo in range(3):
        for metodo in ("GetActiveApplication", "GetApplication"):
            try:
                acc = CAA.AppAccess()
                app = getattr(acc, metodo)()
                if app is None:
                    visto_none = True
                    continue
                iapp = CE.IApplication(app)
                break
            except Exception as e:
                ultimo_err = e
                iapp = None
        if iapp is not None:
            break
        time.sleep(3)
    if iapp is None:
        if visto_none:
            return {"ok": False,
                    "motivo": "nessuna istanza Cimatron registrata come attiva "
                              "(l'istanza attiva è stata chiusa?) — si sblocca "
                              "cliccando in una finestra Cimatron; riproverò"}
        return {"ok": False,
                "motivo": f"Cimatron non raggiungibile: {ultimo_err}"}
    try:
        pdm = CE.IPdm(iapp.GetPdm())
    except Exception as e:
        return {"ok": False, "motivo": f"PDM non raggiungibile: {e}"}

    # documento attivo (per l'anteprima e come fallback)
    path_attivo, icd_attivo = None, None
    try:
        icd_attivo = CE.ICimDocument(iapp.GetActiveDoc())
        path_attivo = icd_attivo.GetPath()
    except Exception:
        pass

    # tutti i documenti aperti dell'istanza: Object[] che contiene String[]
    paths = []
    try:
        aperti = pdm.GetOpenDocuments()
        for gruppo in aperti:
            try:
                paths.extend(str(p) for p in gruppo)
            except TypeError:
                paths.append(str(gruppo))
    except Exception:
        pass
    if path_attivo and path_attivo not in paths:
        paths.insert(0, path_attivo)
    # dedup preservando l'ordine, attivo per primo
    visti = set()
    paths = [p for p in ([path_attivo] if path_attivo else []) + paths
             if p and not (p in visti or visti.add(p))]
    if not paths:
        return {"ok": False, "motivo": "nessun documento aperto"}

    risultati = []
    for doc_path in paths:
        p = Path(doc_path)
        posizione, commessa = p.parent.name, p.parent.parent.name
        e_attivo = (doc_path == path_attivo)

        # throttle per documento: il doc attivo segue la cadenza del tracker,
        # gli altri si aggiornano al massimo ogni min_intervallo_min
        if not e_attivo and _estratto_di_recente(out_dir, commessa, posizione,
                                                 min_intervallo_min):
            risultati.append({"ok": True, "skip": "recente", "path": doc_path,
                              "commessa": commessa, "posizione": posizione})
            continue

        try:
            model = pdm.GetModel(doc_path)
            ncm = NC.INcModel(model)
        except Exception as e:
            risultati.append({"ok": False, "path": doc_path,
                              "motivo": f"modello NC non raggiungibile: {str(e)[:80]}"})
            continue

        tmp_xml = Path(tempfile.gettempdir()) / f"cimx_{os.getpid()}.xml"
        try:
            if tmp_xml.exists():
                tmp_xml.unlink()
            ncm.GetProcessManagerAsXML2(0, str(tmp_xml))
            if not tmp_xml.exists() or tmp_xml.stat().st_size == 0:
                raise RuntimeError("XML vuoto")
        except Exception as e:
            risultati.append({"ok": False, "path": doc_path,
                              "motivo": f"GetProcessManagerAsXML2 fallita: {str(e)[:80]}"})
            continue

        dati = parse_xml2(tmp_xml)
        try:
            tmp_xml.unlink()
        except OSError:
            pass
        if not dati.get("procedure"):
            risultati.append({"ok": False, "path": doc_path,
                              "motivo": "nessuna procedura (documento non NC?)"})
            continue

        titolo, pid, tipo = p.stem, None, "cmNc"
        try:
            icd = CE.ICimDocument(pdm.GetDocumentByPath(doc_path))
            titolo, pid, tipo = icd.Title, icd.PID, str(icd.Type)
        except Exception:
            if e_attivo and icd_attivo is not None:
                try:
                    titolo, pid, tipo = (icd_attivo.Title, icd_attivo.PID,
                                         str(icd_attivo.Type))
                except Exception:
                    pass

        dati["documento"] = {"path": doc_path, "titolo": titolo, "pid": pid,
                             "tipo": tipo, "commessa": commessa,
                             "posizione": posizione}
        dati["estratto_il"] = datetime.now().isoformat(timespec="seconds")

        proj_dir = out_dir / f"{commessa}_{posizione}"
        proj_dir.mkdir(parents=True, exist_ok=True)
        mw = _arricchisci_mw(ncm, dati, proj_dir)

        json_path, png_path, _ = _salva_estrazione(
            dati, out_dir, commessa, posizione,
            icd_attivo if e_attivo else None, con_png)
        risultati.append({"ok": True, "path": doc_path,
                          "json_path": str(json_path),
                          "png_path": str(png_path) if png_path else None,
                          "n_procedure": dati["n_procedure"],
                          "mw": mw, "attivo": e_attivo,
                          "commessa": commessa, "posizione": posizione})

    ok_globale = any(r.get("ok") and not r.get("skip") for r in risultati)
    return {"ok": ok_globale,
            "motivo": None if ok_globale else "nessuna estrazione riuscita",
            "documenti": risultati}


# ─────────────────────────────────────────────────────────────────────────────
# Invio a DMG Desk (POST /api/cam-params/upload) con coda di recupero.
# Ogni versione inviata con successo è marcata da un file gemello ".sent":
# gli invii falliti (DD offline) vengono ritentati alla prossima occasione.
# ─────────────────────────────────────────────────────────────────────────────

def _headers_api():
    """Header X-API-Key solo se configurata (coerente con cam_tracker/fase 8)."""
    key = (os.environ.get("DMG_API_KEY") or "").strip()
    return {"X-API-Key": key} if key else {}


def invia_a_dmgdesk(json_path: Path, base_url: str, timeout: int = 30) -> bool:
    """Invia una versione (ts.json + eventuale ts_anteprima.png). True se OK."""
    import requests
    json_path = Path(json_path)
    png_path = json_path.with_name(json_path.stem + "_anteprima.png")
    try:
        with open(json_path, "rb") as fj:
            files = {"dati": (json_path.name, fj.read(), "application/json")}
        if png_path.exists():
            with open(png_path, "rb") as fp:
                files["anteprima"] = (png_path.name, fp.read(), "image/png")
        r = requests.post(f"{base_url.rstrip('/')}/api/cam-params/upload",
                          files=files, timeout=timeout, headers=_headers_api())
        if r.status_code == 200:
            json_path.with_suffix(".sent").touch()
            return True
        print(f"[invio] HTTP {r.status_code}: {r.text[:150]}")
        return False
    except Exception as e:
        print(f"[invio] fallito: {e}")
        return False


def invia_pendenti(out_dir: Path, base_url: str, max_n: int = 5) -> int:
    """Ritenta l'invio delle versioni mai confermate (senza marker .sent)."""
    inviate = 0
    versioni = sorted(Path(out_dir).glob("*/[0-9]*-[0-9]*.json"))
    for jp in versioni:
        if jp.with_suffix(".sent").exists():
            continue
        if inviate >= max_n:
            break
        if invia_a_dmgdesk(jp, base_url):
            inviate += 1
    return inviate


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Estrattore parametri NC da Cimatron (SDK)")
    ap.add_argument("--out", default=str(OUT_DIR_DEFAULT),
                    help="cartella output (default: cam_tracker/parametri_cam)")
    ap.add_argument("--no-png", action="store_true", help="salta l'anteprima PNG")
    ap.add_argument("--solo-parse", metavar="FILE_XML",
                    help="test offline: parsa un XML già salvato, stampa il JSON")
    ap.add_argument("--invia", metavar="URL",
                    help="dopo l'estrazione invia a DMG Desk (es. http://localhost:8000) "
                         "e ritenta le versioni pendenti")
    args = ap.parse_args()

    if args.solo_parse:
        dati = parse_xml2(args.solo_parse)
        print(json.dumps(dati, ensure_ascii=False, indent=1))
        return 0

    t0 = time.time()
    ris = estrai_da_cimatron(Path(args.out), con_png=not args.no_png)
    dt = time.time() - t0
    if not ris["ok"]:
        print(f"[SKIP/ERRORE] {ris.get('motivo')}")
        if args.invia:
            n = invia_pendenti(Path(args.out), args.invia)
            if n:
                print(f"     Recuperate {n} versioni pendenti")
        return 1

    estratti = [r for r in ris["documenti"] if r.get("ok") and not r.get("skip")]
    skippati = [r for r in ris["documenti"] if r.get("skip")]
    falliti = [r for r in ris["documenti"] if not r.get("ok")]
    riass = ", ".join(f"{r['commessa']}/{r['posizione']}:{r['n_procedure']}p"
                      + ("*" if r.get("attivo") else "")
                      + (f" MW{r['mw']['letti']}/{r['mw']['chiamate']}"
                         if r.get("mw", {}).get("chiamate") else "")
                      for r in estratti)
    print(f"[OK] {len(estratti)} doc in {dt:.1f}s — {riass}"
          + (f" | {len(skippati)} recenti (skip)" if skippati else "")
          + (f" | {len(falliti)} FALLITI" if falliti else ""))
    for r in falliti:
        print(f"     [KO] {r.get('path')}: {r.get('motivo')}")
    if args.invia:
        for r in estratti:
            ok = invia_a_dmgdesk(Path(r["json_path"]), args.invia)
            print(f"     Invio {r['commessa']}/{r['posizione']}: "
                  f"{'OK' if ok else 'FALLITO (in coda)'}")
        n = invia_pendenti(Path(args.out), args.invia)
        if n:
            print(f"     Recuperate {n} versioni pendenti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
