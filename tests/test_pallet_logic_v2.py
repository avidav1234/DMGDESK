"""
Test della nuova logica pallet (feature/pallet-logic-v2).

Simula il tick di macchina_live.py con snapshot in-memory dei dati e verifica
che tutti gli scenari della matrice producano lo stato pallet atteso.

Esegui con:   python -m tests.test_pallet_logic_v2
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timedelta


# ═══════════════════════════════════════════════════════════════════════════
# HELPER: costruzione dati mock e simulazione tick minimo
# ═══════════════════════════════════════════════════════════════════════════

def mk_pgm(filename, stato="in_main", utensili=None, utensili_visti=None):
    """Crea un programma fresatura."""
    pgm = {
        "filename": filename,
        "stato": stato,
        "utensili": [{"alias": u} for u in (utensili or [])],
    }
    if utensili_visti is not None:
        pgm["_utensili_visti"] = utensili_visti
    return pgm


def mk_progetto(pid, name, programmi, main_programmi=None):
    """Crea un progetto con un task fresatura contenente i programmi dati."""
    proj = {
        "id": pid,
        "name": name,
        "steps": [{
            "tasks": [{
                "text": "fresatura",
                "programs": programmi,
            }],
        }],
    }
    if main_programmi is not None:
        proj["main_snapshot"] = {
            "main_path": f"/fake/{pid}/0_MAIN.MPF",
            "main_hash": "fake",
            "main_programmi": main_programmi,
        }
    return proj


def mk_pallet(numero, progetto_id=None, stato="vuoto"):
    return {"numero": numero, "progetto_id": progetto_id, "stato": stato}


# Import diretto dalle funzioni pure del router
from api.routers.macchina_live import (
    _gestisci_cross_pallet,
    _verifica_utensili_pgm,
    _itera_programmi_fresatura,
    _progetto_mai_iniziato,
)


def simula_tick(projects, pallets, mpf_filename, stato_pgm, pallet_num,
                utensile_attivo=None, now_str=None):
    """
    Simula il blocco pallet+programmi del tick. Replica la logica di
    aggiorna-stati-da-log nella versione v2.
    """
    now_str = now_str or datetime.now().isoformat(timespec="seconds")
    pallet_data = {"pallet": pallets}
    updates = {"pallet": 0, "completato": 0, "in_macchina": 0}

    # ── Blocco pallet INIZIALE — marca nuovo pallet (riga 993-1100 v2) ──────
    def _chiudi_pallet_in_lavorazione(pal, projects):
        pid = pal.get("progetto_id")
        if not pid:
            pal["stato"] = "vuoto"; return
        proj = next((p for p in projects if p.get("id") == pid), None)
        if not proj:
            pal["stato"] = "vuoto"; return
        pgm_fresatura = [
            pg for s in proj.get("steps", [])
            for t in s.get("tasks", [])
            if t.get("text", "").strip().lower() == "fresatura"
            for pg in t.get("programs", [])
            if pg.get("tipoGruppo") != "ipm"
        ]
        pgm_nel_main = [pg for pg in pgm_fresatura
                        if pg.get("stato") in ("in_main", "completato", "in_lavorazione")]
        if not pgm_nel_main:
            pal["stato"] = "guasto"; return
        if not all(pg.get("stato") == "completato" for pg in pgm_nel_main):
            pal["stato"] = "guasto"; return
        for pg in pgm_nel_main:
            attesi = [(u.get("alias") or "").upper().strip()
                      for u in (pg.get("utensili") or []) if u.get("alias")]
            visti = [(u or "").upper().strip()
                     for u in (pg.get("_utensili_visti") or [])]
            if any(a not in visti for a in attesi):
                pal["stato"] = "guasto"; return
        pal["stato"] = "finito"

    # 1. Marca nuovo pallet in_lavorazione, resetta timer
    if stato_pgm in (1, 3) and pallet_num:
        for pal in pallets:
            is_attivo = (pal.get("numero") == pallet_num)
            cur = (pal.get("stato") or "").lower().replace(" ", "_")
            if is_attivo:
                if cur != "in_lavorazione":
                    pal["stato"] = "in_lavorazione"
                    pal.pop("stop_iniziato_ts", None)
                else:
                    if pal.get("stop_iniziato_ts"):
                        pal.pop("stop_iniziato_ts", None)

    # 2. Timeout stop (stato 0/5)
    elif stato_pgm in (0, 5):
        TIMEOUT = timedelta(hours=1)
        for pal in pallets:
            cur = (pal.get("stato") or "").lower().replace(" ", "_")
            if cur != "in_lavorazione":
                continue
            if not pal.get("stop_iniziato_ts"):
                pal["stop_iniziato_ts"] = now_str
                continue
            try:
                iniz = datetime.fromisoformat(pal["stop_iniziato_ts"])
                elapsed = datetime.fromisoformat(now_str) - iniz
            except Exception:
                elapsed = timedelta(0)
            if elapsed >= TIMEOUT:
                _chiudi_pallet_in_lavorazione(pal, projects)
                pal.pop("stop_iniziato_ts", None)

    # ── Programmi in esecuzione (riga 1154-1290 di macchina_live.py v2) ─────
    if mpf_filename and stato_pgm in (1, 3):
        tgt_search = mpf_filename.upper().replace(".MPF", "").strip()
        progetto_con_match = None
        for p in projects:
            for s in p.get("steps", []):
                for t in s.get("tasks", []):
                    if t.get("text", "").strip().lower() != "fresatura":
                        continue
                    for pgm in t.get("programs", []):
                        fn = (pgm.get("filename") or "").upper().replace(".MPF", "").strip()
                        if fn == tgt_search:
                            progetto_con_match = p; break
                    if progetto_con_match: break
                if progetto_con_match: break
            if progetto_con_match: break

        if progetto_con_match:
            pid_corr = progetto_con_match.get("id") or ""
            for p_altro in projects:
                if (p_altro.get("id") or "") == pid_corr:
                    continue
                _gestisci_cross_pallet(p_altro, pallet_data, now_str, updates)

            # Logica sequenziale: marca completato i programmi del MAIN prima del corrente
            snap = progetto_con_match.get("main_snapshot") or {}
            main_list = snap.get("main_programmi") or []
            if main_list:
                def _norm(fn):
                    return (fn or "").upper().replace(".MPF", "").strip()
                main_norm = [_norm(p) for p in main_list]
                tgt_norm = _norm(mpf_filename)
                try:
                    idx = main_norm.index(tgt_norm)
                except ValueError:
                    idx = -1
                if idx > 0:
                    precedenti = set(main_norm[:idx])
                    for s in progetto_con_match.get("steps", []):
                        for t in s.get("tasks", []):
                            if t.get("text", "").strip().lower() != "fresatura":
                                continue
                            for pgm in t.get("programs", []):
                                if pgm.get("tipoGruppo") == "ipm":
                                    continue
                                if pgm.get("stato") != "in_main":
                                    continue
                                if _norm(pgm.get("filename")) in precedenti:
                                    pgm["stato"] = "completato"
                                    pgm["tempoFine"] = now_str
                                    attesi = [(u.get("alias") or "").upper().strip()
                                              for u in (pgm.get("utensili") or []) if u.get("alias")]
                                    pgm["_utensili_visti"] = attesi
                                    pgm["_completato_per_sequenza"] = True

            # Marca corrente in_lavorazione, verifica fratelli
            tgt = mpf_filename.upper().replace(".MPF", "").strip()
            for step in progetto_con_match.get("steps", []):
                for task in step.get("tasks", []):
                    if task.get("text", "").strip().lower() != "fresatura":
                        continue
                    for pgm in task.get("programs", []):
                        if pgm.get("tipoGruppo") == "ipm":
                            continue
                        fn = (pgm.get("filename") or "").upper().replace(".MPF", "").strip()
                        if fn == tgt:
                            if pgm.get("stato") != "in_lavorazione":
                                pgm["stato"] = "in_lavorazione"
                                if not pgm.get("tempoInizio"):
                                    pgm["_utensili_visti"] = []
                                pgm["tempoInizio"] = now_str
                                pgm["tempoFine"] = None
                            if utensile_attivo:
                                visti = pgm.get("_utensili_visti") or []
                                u_up = utensile_attivo.upper().strip()
                                if u_up not in visti:
                                    visti.append(u_up)
                                    pgm["_utensili_visti"] = visti
                        else:
                            if pgm.get("stato") == "in_lavorazione":
                                _verifica_utensili_pgm(pgm, progetto_con_match, pallet_data, now_str, updates)

    # 3. Chiusura DIFFERITA pallet uscenti (dopo programmi aggiornati)
    if stato_pgm in (1, 3) and pallet_num:
        for pal in pallets:
            is_attivo = (pal.get("numero") == pallet_num)
            cur = (pal.get("stato") or "").lower().replace(" ", "_")
            if not is_attivo and cur == "in_lavorazione":
                _chiudi_pallet_in_lavorazione(pal, projects)
                pal.pop("stop_iniziato_ts", None)

    return updates


# ═══════════════════════════════════════════════════════════════════════════
# TEST UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

_results = []

def check(label, actual, expected):
    ok = actual == expected
    status = "✅" if ok else "❌"
    print(f"{status} {label} — atteso: {expected!r}, ottenuto: {actual!r}")
    _results.append(ok)


# ═══════════════════════════════════════════════════════════════════════════
# SCENARI MATRICE
# ═══════════════════════════════════════════════════════════════════════════

def test_A1_ciclo_completato_pulito():
    """Ciclo completato, tutti programmi completato, utensili OK, cambio progetto."""
    print("\n[A1] Ciclo completato pulito → cambio progetto → FINITO")
    pA = mk_progetto("projA", "A", [
        mk_pgm("A_001", "completato", utensili=["T1"], utensili_visti=["T1"]),
        mk_pgm("A_002", "in_lavorazione", utensili=["T2"], utensili_visti=["T2"]),
    ], main_programmi=["A_001.MPF", "A_002.MPF"])
    pB = mk_progetto("projB", "B", [mk_pgm("B_001", "in_main", utensili=["T3"])])
    pal1 = mk_pallet(1, "projA", "in_lavorazione")
    pal2 = mk_pallet(2, "projB", "grezzo")
    simula_tick([pA, pB], [pal1, pal2], "B_001", 1, pallet_num=2, utensile_attivo="T3")
    check("A1 pallet 1 uscente", pal1["stato"], "finito")


def test_A2_ultimo_pgm_utensile_mancante():
    """Ciclo finisce ma ultimo programma completato con utensile non visto."""
    print("\n[A2] Ciclo completato ma utensili mancanti → GUASTO")
    pA = mk_progetto("projA", "A", [
        mk_pgm("A_001", "completato", utensili=["T1"], utensili_visti=["T1"]),
        # programma completato ma MISS utensile
        mk_pgm("A_002", "completato", utensili=["T2", "T3"], utensili_visti=["T2"]),
    ], main_programmi=["A_001.MPF", "A_002.MPF"])
    pB = mk_progetto("projB", "B", [mk_pgm("B_001", "in_main", utensili=["T4"])])
    pal1 = mk_pallet(1, "projA", "in_lavorazione")
    pal2 = mk_pallet(2, "projB", "grezzo")
    simula_tick([pA, pB], [pal1, pal2], "B_001", 1, pallet_num=2, utensile_attivo="T4")
    check("A2 pallet 1 uscente", pal1["stato"], "guasto")


def test_B1_interruzione_a_meta_main():
    """Programma interrotto (rottura utensile), switch su altro pallet."""
    print("\n[B1] Interruzione a metà MAIN → GUASTO")
    pA = mk_progetto("projA", "A", [
        mk_pgm("A_001", "completato", utensili=["T1"], utensili_visti=["T1"]),
        mk_pgm("A_002", "in_lavorazione", utensili=["T2"], utensili_visti=["T2"]),
        mk_pgm("A_003", "in_main", utensili=["T3"]),  # non eseguito
        mk_pgm("A_004", "in_main", utensili=["T4"]),  # non eseguito
    ], main_programmi=["A_001.MPF", "A_002.MPF", "A_003.MPF", "A_004.MPF"])
    pB = mk_progetto("projB", "B", [mk_pgm("B_001", "in_main", utensili=["T5"])])
    pal1 = mk_pallet(1, "projA", "in_lavorazione")
    pal2 = mk_pallet(2, "projB", "grezzo")
    simula_tick([pA, pB], [pal1, pal2], "B_001", 1, pallet_num=2, utensile_attivo="T5")
    check("B1 pallet 1 uscente (era in lav)", pal1["stato"], "guasto")
    check("B1 pallet 2 entrante", pal2["stato"], "in_lavorazione")


def test_B2_rottura_ultimo_programma():
    """Ultimo programma del MAIN rotto → GUASTO."""
    print("\n[B2] Rottura su ultimo programma MAIN → GUASTO")
    pA = mk_progetto("projA", "A", [
        mk_pgm("A_001", "completato", utensili=["T1"], utensili_visti=["T1"]),
        mk_pgm("A_002", "in_lavorazione", utensili=["T2", "T3"], utensili_visti=["T2"]),
    ], main_programmi=["A_001.MPF", "A_002.MPF"])
    pB = mk_progetto("projB", "B", [mk_pgm("B_001", "in_main", utensili=["T4"])])
    pal1 = mk_pallet(1, "projA", "in_lavorazione")
    pal2 = mk_pallet(2, "projB", "grezzo")
    simula_tick([pA, pB], [pal1, pal2], "B_001", 1, pallet_num=2, utensile_attivo="T4")
    # A_002 viene marcato in_main da _verifica_utensili_pgm (utensile mancante)
    # quindi al pallet check: c'è un in_main → GUASTO
    check("B2 pallet 1 uscente", pal1["stato"], "guasto")


def test_C1_timeout_1h():
    """Stop prolungato > 1h → pallet in lavorazione va GUASTO."""
    print("\n[C1] Stop > 1h → GUASTO")
    pA = mk_progetto("projA", "A", [
        mk_pgm("A_001", "completato", utensili=["T1"], utensili_visti=["T1"]),
        mk_pgm("A_002", "in_main", utensili=["T2"]),  # non eseguito
    ], main_programmi=["A_001.MPF", "A_002.MPF"])
    pal1 = mk_pallet(1, "projA", "in_lavorazione")
    # Primo tick stop: registra timer
    now1 = datetime(2026, 1, 1, 10, 0, 0).isoformat(timespec="seconds")
    simula_tick([pA], [pal1], "", 5, pallet_num=None, now_str=now1)
    check("C1 dopo primo tick stop — timer registrato", bool(pal1.get("stop_iniziato_ts")), True)
    check("C1 dopo primo tick — ancora in_lavorazione", pal1["stato"], "in_lavorazione")
    # Secondo tick dopo 30 min: ancora in lavorazione
    now2 = datetime(2026, 1, 1, 10, 30, 0).isoformat(timespec="seconds")
    simula_tick([pA], [pal1], "", 5, pallet_num=None, now_str=now2)
    check("C1 dopo 30 min", pal1["stato"], "in_lavorazione")
    # Terzo tick dopo 70 min: timeout → guasto
    now3 = datetime(2026, 1, 1, 11, 15, 0).isoformat(timespec="seconds")
    simula_tick([pA], [pal1], "", 5, pallet_num=None, now_str=now3)
    check("C1 dopo 1h15min", pal1["stato"], "guasto")


def test_C2_stop_breve_poi_ripresa():
    """Stop < 1h → ripresa → nessun cambio stato."""
    print("\n[C2] Stop breve + ripresa → in_lavorazione senza timeout")
    pA = mk_progetto("projA", "A", [
        mk_pgm("A_001", "in_lavorazione", utensili=["T1"], utensili_visti=["T1"]),
        mk_pgm("A_002", "in_main", utensili=["T2"]),
    ], main_programmi=["A_001.MPF", "A_002.MPF"])
    pal1 = mk_pallet(1, "projA", "in_lavorazione")
    now1 = datetime(2026, 1, 1, 10, 0, 0).isoformat(timespec="seconds")
    simula_tick([pA], [pal1], "", 5, pallet_num=None, now_str=now1)
    # Ripresa dopo 10 min
    now2 = datetime(2026, 1, 1, 10, 10, 0).isoformat(timespec="seconds")
    simula_tick([pA], [pal1], "A_001", 1, pallet_num=1,
                utensile_attivo="T1", now_str=now2)
    check("C2 ripresa — pallet in_lavorazione", pal1["stato"], "in_lavorazione")
    check("C2 ripresa — timer azzerato", pal1.get("stop_iniziato_ts"), None)


def test_C3_logica_sequenziale():
    """Salta programma, parte il successivo del MAIN → retro-marcatura."""
    print("\n[C3] Logica sequenziale — A_001 in_main, parte A_003 → A_001 retro-completato")
    pA = mk_progetto("projA", "A", [
        mk_pgm("A_001", "in_main", utensili=["T1"]),  # non esegito (log perso)
        mk_pgm("A_002", "completato", utensili=["T2"], utensili_visti=["T2"]),
        mk_pgm("A_003", "in_main", utensili=["T3"]),
        mk_pgm("A_extra", "da_fare", utensili=["T9"]),  # fuori MAIN → NON toccato
    ], main_programmi=["A_001.MPF", "A_002.MPF", "A_003.MPF"])
    pal1 = mk_pallet(1, "projA", "in_lavorazione")
    simula_tick([pA], [pal1], "A_003", 1, pallet_num=1, utensile_attivo="T3")
    pgm_001 = pA["steps"][0]["tasks"][0]["programs"][0]
    pgm_extra = pA["steps"][0]["tasks"][0]["programs"][3]
    check("C3 A_001 retro-marcato completato", pgm_001["stato"], "completato")
    check("C3 A_001 flag _completato_per_sequenza", pgm_001.get("_completato_per_sequenza"), True)
    check("C3 A_001 _utensili_visti riempiti", pgm_001.get("_utensili_visti"), ["T1"])
    check("C3 A_extra fuori MAIN non toccato", pgm_extra["stato"], "da_fare")


def test_D1_riavvio_stesso_progetto():
    """Stesso progetto ripreso: nessun cambio drastico, continua."""
    print("\n[D1] Riavvio sullo stesso progetto → resta in_lavorazione")
    pA = mk_progetto("projA", "A", [
        mk_pgm("A_001", "completato", utensili=["T1"], utensili_visti=["T1"]),
        mk_pgm("A_002", "in_main", utensili=["T2"]),
    ], main_programmi=["A_001.MPF", "A_002.MPF"])
    pal1 = mk_pallet(1, "projA", "in_lavorazione")
    simula_tick([pA], [pal1], "A_002", 1, pallet_num=1, utensile_attivo="T2")
    check("D1 resta in_lavorazione", pal1["stato"], "in_lavorazione")


def test_E1_pallet_guasto_torna_in_macchina():
    """Pallet guasto rientra in macchina: diventa in_lavorazione."""
    print("\n[E1] Pallet guasto → entra in macchina → in_lavorazione")
    pA = mk_progetto("projA", "A", [
        mk_pgm("A_001", "in_main", utensili=["T1"]),
    ], main_programmi=["A_001.MPF"])
    pal1 = mk_pallet(1, "projA", "guasto")
    simula_tick([pA], [pal1], "A_001", 1, pallet_num=1, utensile_attivo="T1")
    check("E1 pallet guasto → in_lavorazione (entra)", pal1["stato"], "in_lavorazione")


def test_F2_fase2_interrotta():
    """Dopo rigenerazione MAIN per fase 2, se interrotta → GUASTO."""
    print("\n[F2] Fase 2 interrotta → GUASTO")
    # Simuliamo stato post-rigenerazione MAIN (fase 2)
    pA = mk_progetto("projA", "A", [
        mk_pgm("A_004", "in_lavorazione", utensili=["T4"], utensili_visti=["T4"]),
        mk_pgm("A_005", "in_main", utensili=["T5"]),  # interruzione
    ], main_programmi=["A_004.MPF", "A_005.MPF"])
    pB = mk_progetto("projB", "B", [mk_pgm("B_001", "in_main", utensili=["T9"])])
    pal1 = mk_pallet(1, "projA", "in_lavorazione")
    pal2 = mk_pallet(2, "projB", "grezzo")
    simula_tick([pA, pB], [pal1, pal2], "B_001", 1, pallet_num=2, utensile_attivo="T9")
    check("F2 fase 2 interrotta", pal1["stato"], "guasto")


def test_G4_pallet_num_null():
    """pallet_num null + stato 1 → nessuna azione sui pallet in_lavorazione."""
    print("\n[G4] pallet_num null, macchina esegue programma fuori progetti → aspetta")
    pA = mk_progetto("projA", "A", [mk_pgm("A_001", "in_lavorazione", utensili=["T1"], utensili_visti=["T1"])],
                     main_programmi=["A_001.MPF"])
    pal1 = mk_pallet(1, "projA", "in_lavorazione")
    # Tick con mpf non in nessun progetto, pallet_num=None
    simula_tick([pA], [pal1], "UNKNOWN_PGM", 1, pallet_num=None, utensile_attivo="T1")
    check("G4 pallet non toccato", pal1["stato"], "in_lavorazione")


def test_G5_programma_non_mappato():
    """Programma attivo non riconducibile a nessun progetto, ma pallet_num valido → pallet uscente guasto."""
    print("\n[G5] Programma non mappato + pallet_num valido → pallet uscente GUASTO (per simplicità)")
    pA = mk_progetto("projA", "A", [
        mk_pgm("A_001", "in_lavorazione", utensili=["T1"], utensili_visti=["T1"]),
        mk_pgm("A_002", "in_main", utensili=["T2"]),
    ], main_programmi=["A_001.MPF", "A_002.MPF"])
    pal1 = mk_pallet(1, "projA", "in_lavorazione")
    pal2 = mk_pallet(2, None, "vuoto")
    # Pallet 2 attivo, programma non mappato. Pallet 1 non più attivo → chiuso.
    simula_tick([pA], [pal1, pal2], "UNKNOWN_PGM", 1, pallet_num=2, utensile_attivo="T9")
    check("G5 pallet uscente → guasto", pal1["stato"], "guasto")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_A1_ciclo_completato_pulito()
    test_A2_ultimo_pgm_utensile_mancante()
    test_B1_interruzione_a_meta_main()
    test_B2_rottura_ultimo_programma()
    test_C1_timeout_1h()
    test_C2_stop_breve_poi_ripresa()
    test_C3_logica_sequenziale()
    test_D1_riavvio_stesso_progetto()
    test_E1_pallet_guasto_torna_in_macchina()
    test_F2_fase2_interrotta()
    test_G4_pallet_num_null()
    test_G5_programma_non_mappato()

    print(f"\n{'='*60}")
    passed = sum(_results)
    total = len(_results)
    print(f"RISULTATO: {passed}/{total} assertions passate")
    print(f"{'='*60}")
    sys.exit(0 if passed == total else 1)
