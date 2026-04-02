"""
constants.py — costanti operative DMGDesk
Centralizza tutti i valori hardcoded per facilitare la configurazione.
"""

# ── Turno di lavoro ───────────────────────────────────────────────────────────
ORE_TURNO_SEC = 28800          # 8 ore in secondi (turno standard)
INIZIO_TURNO_ORA  = 7          # turno inizia alle 07:30
INIZIO_TURNO_MIN  = 30
FINE_TURNO_ORA    = 16         # turno finisce alle 16:30
FINE_TURNO_MIN    = 30
# Finestre fisse per riepilogo giornaliero
# Notte: 16:30 → 07:30 (macchina in autonomia)
# Giorno: 07:30 → 16:30 (operatore presente, CAM attivo)

# ── Watchdog MchnSrv ──────────────────────────────────────────────────────────
WATCHDOG_SOGLIA_SEC = 300      # log stale dopo 300s senza aggiornamenti
                               # (era 120s — aumentato per tollerare ritardi rete)
WATCHDOG_ISTERESI_TICK = 3     # tick consecutivi stale prima di segnalare
                               # (evita falsi positivi da picchi momentanei)

# ── Database cicli utensile ───────────────────────────────────────────────────
CICLI_FINESTRA = 50            # campioni massimi per finestra scorrevole
CICLI_MIN_ANOMALIA = 3         # campioni minimi per rilevare anomalie
CICLI_ANOMALIA_SIGMA = 2       # soglia: media + N*sigma = ciclo anomalo

# ── OEE ───────────────────────────────────────────────────────────────────────
OEE_QUALITA_DEFAULT = 0.98     # proxy qualità CNC stampi (rarissimi scarti)
OEE_SOGLIA_VERDE = 75.0        # OEE% verde ≥ 75
OEE_SOGLIA_ARANCIO = 50.0      # OEE% arancio ≥ 50, rosso < 50

# ── Override feed/mandrino ────────────────────────────────────────────────────
OVERRIDE_SOGLIA_NORMALE = 90   # % — sopra: normale
OVERRIDE_SOGLIA_RIDOTTO = 50   # % — tra 50-89: ridotto, sotto: basso

# ── Report e storico ──────────────────────────────────────────────────────────
LOG_RETENTION_DAYS = 90        # giorni da mantenere in lavorazioni_log.json
STORICO_GIORNI_DEFAULT = 7     # giorni default per grafico storico
TEMPI_CICLO_MIN_DURATA = 10    # secondi — cicli più corti = bug di timing
TEMPI_CICLO_MAX_DURATA = 28800 # secondi — cicli più lunghi = bug di timing (8h)

# ── Cache ─────────────────────────────────────────────────────────────────────
CONFIG_CACHE_TTL = 30          # secondi — TTL cache carica_configurazione
ANALISI_SETUP_TTL = 120        # secondi — TTL cache analisi-setup
