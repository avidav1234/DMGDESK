"""
sandbox/genera_dati_mock.py
============================
Genera dati realistici fittizi per la sandbox DMGDesk V2.
Crea tutti i file necessari in sandbox/data/ senza toccare dati reali.

Uso:
    python sandbox/genera_dati_mock.py
"""

import json, csv, random, os
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

random.seed(42)

# ─── Utensili mock ────────────────────────────────────────────────────────────

UTENSILI = [
    {"Alias": "FS16R2L80F100E4",  "Tipo": "Fresa-SGR-PIANI", "Diametro": 16, "Stato_Utensile": "IN_MACCHINA", "Life_Percent": 45},
    {"Alias": "FS10R0.5L50E3",    "Tipo": "Fresa-SGR-HSC",   "Diametro": 10, "Stato_Utensile": "IN_MACCHINA", "Life_Percent": 72},
    {"Alias": "FF6R3L30F35G1",    "Tipo": "Fresa-FIN-HSC",   "Diametro": 6,  "Stato_Utensile": "IN_MACCHINA", "Life_Percent": 88},
    {"Alias": "FS25R2L100F150E6", "Tipo": "Fresa-SGR-PIANI", "Diametro": 25, "Stato_Utensile": "IN_MACCHINA", "Life_Percent": 21},
    {"Alias": "FF10R0.5L60E3",    "Tipo": "Fresa-FIN-PIANI", "Diametro": 10, "Stato_Utensile": "IN_MACCHINA", "Life_Percent": 63},
    {"Alias": "CENTRINO-8-F50E3", "Tipo": "Punta",           "Diametro": 8,  "Stato_Utensile": "IN_MACCHINA", "Life_Percent": 55},
    {"Alias": "FS8R1L40E3",       "Tipo": "Fresa-SGR-HSC",   "Diametro": 8,  "Stato_Utensile": "SCAFFALE",    "Life_Percent": 30},
    {"Alias": "FF4R0.5L20E2",     "Tipo": "Fresa-FIN-HSC",   "Diametro": 4,  "Stato_Utensile": "SCAFFALE",    "Life_Percent": 95},
    {"Alias": "FS20R2L90F120E5",  "Tipo": "Fresa-SGR-PIANI", "Diametro": 20, "Stato_Utensile": "SMONTATO",    "Life_Percent": 5},
]

COLS_MACCHINA = ["Alias", "Tipo", "Diametro", "Stato_Utensile", "Life_Percent",
                 "Holder", "Lunghezza_Totale", "Note", "Data_Montaggio"]

def _write_csv(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            row = {c: r.get(c, "") for c in cols}
            w.writerow(row)

def genera_utensili():
    holders = ["Idraulico_D16", "Idraulico_D10", "Pinza_ER32", "Forte_Serraggio_D25", "Caletto_D8"]
    in_macchina, scaffale, smontati = [], [], []
    for u in UTENSILI:
        u["Holder"] = random.choice(holders)
        u["Lunghezza_Totale"] = random.randint(80, 200)
        u["Note"] = ""
        u["Data_Montaggio"] = (datetime.now() - timedelta(days=random.randint(1, 60))).strftime("%Y-%m-%d")
        if u["Stato_Utensile"] == "IN_MACCHINA":
            in_macchina.append(u)
        elif u["Stato_Utensile"] == "SCAFFALE":
            scaffale.append(u)
        else:
            smontati.append(u)

    _write_csv(DATA_DIR / "DMGDesk_principale.csv", in_macchina, COLS_MACCHINA)
    _write_csv(DATA_DIR / "DMGDesk_scaffale.csv", scaffale, COLS_MACCHINA)
    _write_csv(DATA_DIR / "DMGDesk_smontati.csv", smontati, COLS_MACCHINA)
    _write_csv(DATA_DIR / "DMGDesk_holder.csv", [], ["Alias", "Tipo", "Diametro", "Note"])
    print(f"  Utensili: {len(in_macchina)} in macchina, {len(scaffale)} scaffale, {len(smontati)} smontati")

# ─── Progetti mock ───────────────────────────────────────────────────────────

MATERIALI = ["1.2343", "1.2311", "42CrMo4", "C45", "1.2379"]
CLIENTI   = ["VETIMEC SRL", "CLIENTE_A", "CLIENTE_B", "CLIENTE_C"]

def genera_progetti():
    progetti = []
    sessioni = []
    oggi = datetime.now()

    for i in range(1, 9):
        pid  = f"sandbox_{i:04d}"
        comm = f"SANDBOX-{4200+i}"
        mat  = random.choice(MATERIALI)
        giorni_fa = random.randint(5, 60)
        data_apertura = (oggi - timedelta(days=giorni_fa)).isoformat()
        scadenza = (oggi + timedelta(days=random.randint(-5, 30))).strftime("%Y-%m-%d")
        consegnato = i <= 3

        steps = []
        for fase_n, fase_nome in enumerate(["Sgrossatura", "Semifinitura", "Finitura"], 1):
            tasks = []
            for pgm_n in range(1, random.randint(2, 5)):
                nome_pgm = f"{comm.replace('-','_')}_{fase_n:02d}_{pgm_n:03d}.MPF"
                stato_pgm = "completato" if (fase_n < 3 or consegnato) else random.choice(["da_fare", "in_macchina", "completato"])
                stima = random.randint(15, 120)
                tasks.append({
                    "text": "Fresatura",
                    "programs": [{
                        "filename": nome_pgm,
                        "stato": stato_pgm,
                        "tipoGruppo": "fresatura",
                        "tempoStimato": stima
                    }]
                })
            steps.append({"title": fase_nome, "tasks": tasks})

        proj = {
            "id": pid,
            "name": comm,
            "cliente": random.choice(CLIENTI),
            "materiale": mat,
            "createdAt": data_apertura,
            "status": "consegnato" if consegnato else "in_lavorazione",
            "pallet_assegnato": f"P{random.randint(1,6)}" if not consegnato else None,
            "steps": steps,
            "note": f"Sandbox mock — {mat}"
        }
        progetti.append(proj)

        # Sessioni macchina per questo progetto
        n_sess = random.randint(2, 8)
        t = oggi - timedelta(days=giorni_fa)
        for s in range(n_sess):
            durata = random.randint(1800, 14400)
            t += timedelta(hours=random.randint(1, 6))
            sess = {
                "id": f"sess_{pid}_{s}",
                "progetto": comm,
                "progetto_id": pid,
                "inizio": t.isoformat(),
                "fine": (t + timedelta(seconds=durata)).isoformat(),
                "durata_sec": durata,
                "programma_attivo": f"{comm.replace('-','_')}_01_001.MPF",
                "utensili": {
                    u["Alias"]: random.randint(300, 3600)
                    for u in random.sample(UTENSILI[:6], 3)
                },
                "n_fermi_anomali": random.randint(0, 2),
                "n_fermi_pianificati": random.randint(0, 3),
                "gap_sec": random.randint(0, 600),
            }
            sessioni.append(sess)

    json.dump({"projects": progetti}, open(DATA_DIR / "worktrack_projects.json", "w"), indent=2, ensure_ascii=False)
    json.dump({"sessioni": sessioni}, open(DATA_DIR / "lavorazioni_log.json", "w"), indent=2, ensure_ascii=False)
    print(f"  Progetti: {len(progetti)}, Sessioni: {len(sessioni)}")

# ─── Stato pallet mock ───────────────────────────────────────────────────────

def genera_pallet():
    stati = ["vuoto", "grezzo", "in_lavorazione", "finito", "vuoto", "vuoto"]
    pallet = {}
    for i, stato in enumerate(stati, 1):
        pallet[f"P{i}"] = {
            "stato": stato,
            "commessa": f"SANDBOX-{4200+i}" if stato == "in_lavorazione" else None,
            "programma": None,
            "ts_cambio": (datetime.now() - timedelta(hours=random.randint(0, 8))).isoformat()
        }
    json.dump(pallet, open(DATA_DIR / "pallet_state.json", "w"), indent=2)
    print(f"  Pallet: {len(pallet)} configurati")

# ─── OpcUaLegacy.log mock ────────────────────────────────────────────────────

PROG_STATI = [1, 1, 1, 1, 1, 3, 3, 3, 0, 5]  # pesi: per lo più in esecuzione

def genera_opcua_log():
    """
    Genera un OpcUaLegacy.log fittizio con formato identico al reale.
    Il mock_opcua_generator.py lo aggiorna ogni 10s per simulare la macchina live.
    """
    now = datetime.now()
    utensile = random.choice([u["Alias"] for u in UTENSILI[:6]])
    prog_status = random.choice(PROG_STATI)
    prog_name = "SANDBOX_4201_01_001.MPF"
    t = now.strftime("%m/%d/%y %H:%M:%S")

    lines = [
        f"T {t} MchnSrv: ReadPlVar: VarName= actToolIdent; read Value= {utensile}\n",
        f"T {t} MchnSrv: ReadPlVar: VarName= workPandProgName; read Value= /_N_WKS_DIR/_N_SANDBOX_4201_WPD/_N_SANDBOX_4201_01_001_MPF\n",
        f"T {t} MchnSrv: ReadPlVar: VarName= progStatus; read Value= {prog_status}\n",
        f"T {t} MchnSrv: ReadPlVar: VarName= actFeedRate; read Value= {random.randint(300, 800)}\n",
        f"T {t} MchnSrv: ReadPlVar: VarName= actSpeedRate; read Value= {random.randint(3000, 12000)}\n",
    ]
    with open(DATA_DIR / "OpcUaLegacy.log", "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"  OpcUaLegacy.log: progStatus={prog_status}, utensile={utensile}")

# ─── Tool replacements mock ──────────────────────────────────────────────────

def genera_tool_replacements():
    replacements = []
    for i in range(5):
        u = random.choice(UTENSILI[:6])
        ts = (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat()
        replacements.append({
            "alias": u["Alias"],
            "life_at_replacement": random.randint(5, 25),
            "timestamp": ts,
            "commessa": f"SANDBOX-{4200+random.randint(1,5)}",
            "motivo": random.choice(["usura_normale", "rottura", "fine_vita"])
        })
    json.dump(replacements, open(DATA_DIR / "tool_replacements.json", "w"), indent=2)
    print(f"  Tool replacements: {len(replacements)}")

# ─── Step features mock ──────────────────────────────────────────────────────

def genera_step_features():
    features = {}
    for i in range(1, 6):
        comm = f"SANDBOX-{4200+i}"
        features[comm] = {
            "commessa": comm,
            "path_step": f"./sandbox/data/{comm}.stp",
            "file_hash": f"mock_hash_{i:04d}",
            "analizzato": (datetime.now() - timedelta(days=i*3)).isoformat(),
            "ore_macchina": round(random.uniform(4, 40), 1),
            "lead_time_giorni": random.randint(3, 15),
            "features": {
                "bb_x": round(random.uniform(50, 300), 2),
                "bb_y": round(random.uniform(50, 200), 2),
                "bb_z": round(random.uniform(20, 100), 2),
                "bb_volume": round(random.uniform(50000, 5000000), 2),
                "volume": round(random.uniform(20000, 2000000), 2),
                "area": round(random.uniform(10000, 500000), 2),
                "compattezza": round(random.uniform(0.3, 0.8), 5),
                "sfericita": round(random.uniform(0.1, 0.6), 5),
                "rapporto_area_vol": round(random.uniform(0.1, 1.5), 5),
                "n_facce": random.randint(20, 200),
                "n_spigoli": random.randint(40, 400),
                "n_vertici": random.randint(20, 200),
                "n_piani": random.randint(10, 100),
                "n_cilindri": random.randint(2, 30),
                "n_conici": random.randint(0, 5),
                "n_sferici": random.randint(0, 2),
                "ratio_cilindri_facce": round(random.uniform(0.05, 0.3), 4),
                "ratio_piani_facce": round(random.uniform(0.4, 0.8), 4),
                "dim_x_norm": round(random.uniform(0.5, 1.0), 4),
                "dim_y_norm": round(random.uniform(0.3, 0.9), 4),
                "dim_z_norm": round(random.uniform(0.1, 0.5), 4),
            },
            "note": f"Mock sandbox commessa {i}"
        }
    json.dump(features, open(DATA_DIR / "step_features.json", "w"), indent=2)
    print(f"  Step features: {len(features)} commesse")

# ─── NC programs mock ────────────────────────────────────────────────────────

def genera_nc_programs():
    nc_dir = DATA_DIR / "nc_programs" / "SANDBOX_4201_WPD"
    nc_dir.mkdir(parents=True, exist_ok=True)
    for fase in range(1, 3):
        for pgm in range(1, 4):
            nome = nc_dir / f"SANDBOX_4201_{fase:02d}_{pgm:03d}.MPF"
            utensile = random.choice([u["Alias"] for u in UTENSILI[:6]])
            nome.write_text(
                f"; Programma sandbox mock\n"
                f"; Commessa: SANDBOX-4201 Fase {fase} Pgm {pgm}\n"
                f"T=\"{utensile}\" M6\n"
                f"G54\n"
                f"S{random.randint(3000,12000)} M3\n"
                f"F{random.randint(300,800)}\n"
                f"G0 X0 Y0 Z50\n"
                f"M30\n",
                encoding="utf-8"
            )
    print(f"  NC programs: generati in {nc_dir}")

# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== Generatore dati mock DMGDesk V2 Sandbox ===\n")
    genera_utensili()
    genera_progetti()
    genera_pallet()
    genera_opcua_log()
    genera_tool_replacements()
    genera_step_features()
    genera_nc_programs()
    print(f"\n✅ Tutti i dati mock generati in: {DATA_DIR.resolve()}\n")
