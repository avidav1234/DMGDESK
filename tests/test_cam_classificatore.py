"""
Test del motore di classificazione ibrido (logic/cam_classificatore.py).
I casi replicano le regole DETTATE (R1, R2, R4) e il caso ambiguo reale
osservato sul 4388/0015 (strategia Finitura su fresa SGR).
"""

from logic.cam_classificatore import (carica_regole, classifica_procedura,
                                      famiglia_utensile)

REGOLE = carica_regole()


def _proc(nome_ut, parete=None, fondo=None, parte=None, commento=None,
          pu=None, strategia=None, sotto=None, fz=None, toll=None,
          alias=None, tipo=None, superfici_mw=None):
    return {
        "numero": 1, "nome": f"{sotto or 'X'}_1",
        "strategia": strategia, "sotto_strategia": sotto,
        "commento": commento, "pu": pu,
        "utensile": {"nome": nome_ut, "alias": alias, "tipo": tipo},
        "offset": {"parete": parete, "fondo": fondo, "parte": parte,
                   "superfici_mw": superfici_mw},
        "tolleranze": {"superfici": toll},
        "macchina": {"fz": fz},
    }


# ── famiglie ────────────────────────────────────────────────────────────────

def test_famiglia_da_nome_completo():
    assert famiglia_utensile(_proc("FRESA-SGR-PIANI-25R2-L85"), REGOLE) == "SGROSSATURA"
    assert famiglia_utensile(_proc("FRESA-PREF-SPA-16R2"), REGOLE) == "PREFINITURA"
    assert famiglia_utensile(_proc("FRESA-FIN-PIANI-42R0.8"), REGOLE) == "FINITURA_PIANI"
    assert famiglia_utensile(_proc("FRESA-FIN-HSC-10R5"), REGOLE) == "FINITURA"
    assert famiglia_utensile(_proc("ALESATORE-12H7"), REGOLE) == "ALESATORE"


def test_famiglia_fallback_alias_ffpi_prima_di_ff():
    assert famiglia_utensile(_proc("", alias="FFPI42R0.8L114"), REGOLE) == "FINITURA_PIANI"
    assert famiglia_utensile(_proc("", alias="FF10R5L50"), REGOLE) == "FINITURA"
    # FS ambigua per catalogo (sgr/pref/rip): NON deve dire SGROSSATURA
    assert famiglia_utensile(_proc("", alias="FS25R2L85"), REGOLE) == "FS_AMBIGUA"


# ── R1: sgrossatura ─────────────────────────────────────────────────────────

def test_r1_sgrossatura_offset_combinato():
    """Modo Base: offset combinato 0.2 vale per parete E fondo (dettatura)."""
    r = classifica_procedura(_proc("FRESA-SGR-PIANI-25R2-L85", parte=0.2,
                                   strategia="Sgrossatura", sotto="Sgrossatura Spirale",
                                   commento="sgr sopra", pu="SGR_PIANI_F1",
                                   fz=1.0, toll=0.02), REGOLE)
    assert r["esito"] == "classificato" and r["riga"] == "R1"
    assert r["operazione"] == "SGROSSATURA"
    assert r["tolleranza"] == "OFF" and r["presidio"] == "NO"
    assert r["confidenza"] >= 99   # tutte le conferme concordi


def test_r3_offset_01_e_prefinitura():
    """Round2 #1 (completa la vecchia R3 troncata): fresa sgr + offset 0.1
    = offset DA PREFINITURA → PREFINITURA, non sgrossatura né buco."""
    r = classifica_procedura(_proc("FRESA-SGR-HSC-10R2", parte=0.1, pu="PREF",
                                   commento="sgr sopra"), REGOLE)
    assert r["esito"] == "classificato" and r["riga"] == "R3-PREFINITURA"
    assert r["operazione"] == "PREFINITURA"


# ── R2: finitura piani / chiusure ───────────────────────────────────────────

def test_r2_finitura_piani():
    r = classifica_procedura(_proc("FRESA-FIN-PIANI-42R0.8-L114", parete=0.2, fondo=0.0,
                                   strategia="Finitura", sotto="Finitura Aree Orizzontali",
                                   commento="fin piano sopra", pu="FIN_PIANI_F1",
                                   fz=0.12, toll=0.01), REGOLE)
    assert r["esito"] == "classificato" and r["riga"] == "R2"
    assert r["operazione"] == "FINITURA_PIANI" and r["tolleranza"] == "ON"


def test_r2_specializza_chiusure_con_presidio():
    r = classifica_procedura(_proc("FRESA-FIN-PIANI-42R0.8", parete=0.1, fondo=0.0,
                                   commento="fin chiusure stampo"), REGOLE)
    assert r["operazione"] == "FINITURA_CHIUSURE"
    assert r["presidio"] == "SI"    # R4: finiture tarate in presenza


def test_r2b_fondo_negativo_quota_scarsa():
    """Dettatura #5 (2026-07-13): fondo negativo su finitura piani = quota
    richiesta SCARSA rispetto al nominale — è comunque FINITURA_PIANI."""
    r = classifica_procedura(_proc("FRESA-FIN-PIANI-42R0.8", parete=0.2, fondo=-0.02), REGOLE)
    assert r["esito"] == "classificato" and r["riga"] == "R2b-QUOTA-SCARSA"
    assert r["operazione"] == "FINITURA_PIANI" and r["tolleranza"] == "ON"


def test_dettatura_13lug_nuove_regole():
    """Casi reali del labeling #1-16."""
    # #10: contorno -0.015..-0.025 = compensazione flessione → FINITURA_PARETI
    p = _proc("FRESA-FIN-HPC-10R0.5", commento="fin chiavetta B-90", fz=0.064)
    p["offset"]["contorno"] = -0.015
    r = classifica_procedura(p, REGOLE)
    assert r["riga"] == "R-FLESSIONE" and r["operazione"] == "FINITURA_PARETI"

    # #11: «40 H7» → FINITURA_TOLLERANZA (testo vince, riga prima della flessione)
    p = _proc("FRESA-FIN-HPC-10R0.5", commento="40 H7", fz=0.065)
    p["offset"]["contorno"] = -0.035
    r = classifica_procedura(p, REGOLE)
    assert r["operazione"] == "FINITURA_TOLLERANZA" and r["tolleranza"] == "ON"

    # #8/#12: FRESA-RIP con offset sgr = volate di sgrossatura
    r = classifica_procedura(_proc("FRESA-RIP-16R2-L80", parte=0.2, pu="SGR_V2",
                                   commento="sgr b-90", fz=1.0, toll=0.02), REGOLE)
    assert r["riga"] == "R1b-RIPRESA-SGR" and r["operazione"] == "SGROSSATURA"

    # #13: PU SMS + offset finitura (anche con fresa SGR) → finitura smusso veloce
    # (matcha R-SGR-FIN-VELOCE che specializza da testo, o R-SMS: stesso esito)
    r = classifica_procedura(_proc("FRESA-SGR-HSC-6R0.5", parete=0.0, pu="SMS",
                                   fz=0.12, toll=0.01), REGOLE)
    assert (r["operazione"], r["tolleranza"]) == ("FINITURA_SMUSSO", "OFF")
    assert r["esito"] == "classificato"

    # #2/#6: fresa FIN + offset ~0 → FINITURA (l'offset prevale sul PU)
    r = classifica_procedura(_proc("FRESA-FIN-HPC-4R2", parete=0.0, fondo=0.0,
                                   pu="PREFIN_FIGURA", fz=0.08, toll=0.01), REGOLE)
    assert r["riga"] == "R-FIN-BASE" and r["operazione"].startswith("FINITURA")

    # #1: Multi Asse in PU PREFIN → PREFINITURA_FIGURA (in attesa offset MW)
    r = classifica_procedura(_proc("FRESA-FIN-HSC-10R5", pu="PREFIN_FIGURA",
                                   strategia="Multi Asse Adv.",
                                   sotto="Multi Asse Adv.-Adv."), REGOLE)
    assert r["operazione"] == "PREFINITURA_FIGURA"

    # #16: smussatore riconosciuto anche dal solo alias
    r = classifica_procedura(_proc("", alias="SMUSSO-12"), REGOLE)
    assert r["operazione"] == "SMUSSO"


# ── ModuleWorks: offset è il discriminatore primario (dettatura 2026-07-17) ──

def _mw(sotto, superfici_mw, pu="TEST", nome="FRESA-FIN-HSC-10R5-L50-F55"):
    strat = sotto.split("-")[0].strip()
    return _proc(nome, strategia=strat, sotto=sotto, pu=pu, superfici_mw=superfici_mw)


def test_mw_multiasse_offset_guida_la_classe():
    """Esperimento controllato utente (proc 219-222): stessa procedura/utensile,
    cambia SOLO l'offset → cambia la classe. Fasce = quelle base."""
    casi = {0.0: "FINITURA_FIGURA", 0.1: "PREFINITURA_FIGURA",
            0.2: "SGROSSATURA_FIGURA", 1.0: "SGROSSATURA_FIGURA"}
    for off, atteso in casi.items():
        r = classifica_procedura(_mw("Multi Asse Adv.-Adv.", off), REGOLE)
        assert r["esito"] == "classificato", (off, r)
        assert r["operazione"] == atteso, (off, r["operazione"])


def test_mw_operazioni_locali_stesse_fasce_del_multiasse():
    """Proc 223-226: Operazioni Locali con le STESSE fasce di offset (prima
    del fix restavano da_classificare/None)."""
    casi = {0.0: "FINITURA_FIGURA", 0.1: "PREFINITURA_FIGURA",
            0.2: "SGROSSATURA_FIGURA", 1.0: "SGROSSATURA_FIGURA"}
    for off, atteso in casi.items():
        r = classifica_procedura(_mw("Operazioni Locali-Locale 3X", off), REGOLE)
        assert r["esito"] == "classificato", (off, r)
        assert r["operazione"] == atteso, (off, r["operazione"])


def test_mw_offset_negativo_e_flessione():
    """Offset MW negativo = compensazione flessione → finitura (a zero reale)."""
    r = classifica_procedura(_mw("Multi Asse Adv.-Adv.", -0.015), REGOLE)
    assert r["esito"] == "classificato"
    assert r["operazione"] in ("FINITURA_PARETI", "FINITURA_FIGURA")


def test_ripresa_mantiene_classe_qualificata_da_offset():
    """Q2 utente: la Ripresa Guidata dà la classe 'ripresa', l'offset la
    qualifica in sgrossatura/prefinitura/finitura."""
    casi = {1.0: "RIPRESA_SGROSSATURA", 0.1: "RIPRESA_PREFINITURA",
            0.0: "RIPRESA_FINITURA"}
    for off, atteso in casi.items():
        r = classifica_procedura(_mw("Ripresa Guidata", off), REGOLE)
        assert r["operazione"] == atteso, (off, r["operazione"])
    # anche la Ripresa Guidata Multi Asse (contiene 'MULTI ASSE') resta ripresa
    r = classifica_procedura(_mw("Ripresa Guidata Multi Asse", 0.1), REGOLE)
    assert r["operazione"] == "RIPRESA_PREFINITURA"


def test_ripresa_senza_offset_almeno_classe_ripresa():
    """Ripresa senza offset leggibile: mai declassata a sgrossatura, resta 'ripresa'."""
    p = _proc("FRESA-RIP-16R2-L80", strategia="Ripresa Guidata", sotto="Ripresa Guidata")
    r = classifica_procedura(p, REGOLE)
    assert r["operazione"] == "RIPRESA"


def test_mw_fallback_pu_quando_offset_assente():
    """Multi Asse senza offset MW → fallback sul P.U. (retro-compat #1)."""
    r = classifica_procedura(_proc("FRESA-FIN-HSC-10R5", pu="PREFIN_FIGURA",
                                   strategia="Multi Asse Adv.",
                                   sotto="Multi Asse Adv.-Adv."), REGOLE)
    assert r["operazione"] == "PREFINITURA_FIGURA"


# ── R4: famiglie a esito diretto ───────────────────────────────────────────

def test_r4_alesatore_tolleranza_on_presidio_no():
    r = classifica_procedura(_proc("ALESATORE-40H7"), REGOLE)
    assert (r["operazione"], r["tolleranza"], r["presidio"]) == ("ALESATURA", "ON", "NO")


def test_r4_coda_rondine_e_smusso():
    r = classifica_procedura(_proc("CODA-RONDINE-15"), REGOLE)
    assert (r["operazione"], r["tolleranza"], r["presidio"]) == ("SEDE_GUARNIZIONE", "OFF", "NO")
    r = classifica_procedura(_proc("SMUSSO-12"), REGOLE)
    assert (r["operazione"], r["tolleranza"], r["presidio"]) == ("SMUSSO", "OFF", "NO")


def test_misura_renishaw():
    r = classifica_procedura(_proc("RENISHAW", tipo="Tastatore",
                                   strategia="Misura", sotto="Misurazione Nel Processo-Punto",
                                   commento="tast Z"), REGOLE)
    assert r["operazione"] == "MISURA" and r["esito"] == "classificato"


def test_foratura_auto_lista_utensili():
    """Foratura auto multi-tool: utensile 'Lista Utensili' → riga per strategia."""
    r = classifica_procedura(_proc("Lista Utensili",
                                   strategia="Foratura", sotto="Foratura Auto 3X"), REGOLE)
    assert r["operazione"] == "FORATURA" and r["presidio"] == "NO"


# ── conflitti e onestà ──────────────────────────────────────────────────────

def test_conflitto_strategia_finitura_su_fresa_sgr():
    """Caso REALE 4388/0015: 'Finitura Singola Strategia' con fresa FRESA-SGR.
    La riga R1 matcha (famiglia SGR + offset alti) ma strategia e fz dicono
    finitura → DA_VERIFICARE, mai una scelta silenziosa."""
    r = classifica_procedura(_proc("FRESA-SGR-HSC-10R5-L50", parte=0.15,
                                   strategia="Finitura", sotto="Finitura Singola Strategia",
                                   fz=0.25, toll=0.02), REGOLE)
    assert r["esito"] == "da_verificare"
    assert r["riga"] == "R1"
    assert "strategia" in (r["motivo"] or "")


def test_prefinitura_senza_regole_da_classificare():
    """FRESA-PREF: famiglia nota ma regole offset NON ancora dettate."""
    r = classifica_procedura(_proc("FRESA-PREF-SPA-16R2", parte=0.15), REGOLE)
    assert r["esito"] == "da_classificare"
    assert r["famiglia_utensile"] == "PREFINITURA"


def test_utensile_sconosciuto_da_classificare():
    r = classifica_procedura(_proc("UTENSILE-MISTERIOSO-99"), REGOLE)
    assert r["esito"] == "da_classificare"
    assert r["famiglia_utensile"] is None
