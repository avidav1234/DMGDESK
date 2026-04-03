"""
cam_tracker_gui.py — Finestra di stato per CAMTracker
=====================================================
Mostra in tempo reale:
  - Progetto attivo in Cimatron
  - Stato connessione DMGDesk
  - Ore accumulate oggi per progetto
  - Log ultimi eventi

Avvio automatico da cam_tracker.py se disponibile tkinter.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime
import threading
import queue


class TrackerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CAM Tracker")
        self.root.geometry("420x380")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e2530")

        # Coda thread-safe per aggiornamenti dall'esterno
        self.queue = queue.Queue()

        # Stato interno
        self._progetto    = "—"
        self._attivo      = False
        self._dmgdesk     = False
        self._ore_oggi    = {}   # {project_id: seconds}
        self._ultimo_inv  = "—"
        self._log_lines   = []

        self._build_ui()
        self._poll_queue()

    def _build_ui(self):
        root = self.root
        PAD = 10
        BG  = "#1e2530"
        BG2 = "#252d3a"
        BLU = "#378ADD"
        GRN = "#1D9E75"
        RED = "#E24B4A"
        AMB = "#EF9F27"
        GRY = "#888780"
        TXT = "#d0d8e8"
        SML = "#8a93a8"

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(root, bg=BG2, height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="CAM", font=("Segoe UI", 14, "bold"),
                 bg=BG2, fg=BLU).pack(side="left", padx=14, pady=10)
        tk.Label(hdr, text="Tracker", font=("Segoe UI", 14),
                 bg=BG2, fg=TXT).pack(side="left", pady=10)

        # Pallino DMGDesk
        self._dot_dmg = tk.Label(hdr, text="●", font=("Segoe UI", 14),
                                  bg=BG2, fg=RED)
        self._dot_dmg.pack(side="right", padx=6)
        tk.Label(hdr, text="DMGDesk", font=("Segoe UI", 9),
                 bg=BG2, fg=SML).pack(side="right")

        # ── Progetto attivo ───────────────────────────────────────────────────
        f1 = tk.Frame(root, bg=BG2, pady=8)
        f1.pack(fill="x", padx=PAD, pady=(PAD, 4))

        tk.Label(f1, text="PROGETTO ATTIVO", font=("Segoe UI", 8, "bold"),
                 bg=BG2, fg=SML).pack(anchor="w", padx=10)

        row = tk.Frame(f1, bg=BG2)
        row.pack(fill="x", padx=10, pady=(2, 6))

        self._dot_att = tk.Label(row, text="●", font=("Segoe UI", 11),
                                  bg=BG2, fg=GRY)
        self._dot_att.pack(side="left")

        self._lbl_prog = tk.Label(row, text="—",
                                   font=("Segoe UI", 13, "bold"),
                                   bg=BG2, fg=TXT)
        self._lbl_prog.pack(side="left", padx=6)

        self._lbl_stato = tk.Label(row, text="",
                                    font=("Segoe UI", 9),
                                    bg=BG2, fg=GRY)
        self._lbl_stato.pack(side="right", padx=6)

        # ── Ore oggi ──────────────────────────────────────────────────────────
        f2 = tk.Frame(root, bg=BG2, pady=4)
        f2.pack(fill="x", padx=PAD, pady=4)

        tk.Label(f2, text="ORE ACCUMULATE OGGI", font=("Segoe UI", 8, "bold"),
                 bg=BG2, fg=SML).pack(anchor="w", padx=10, pady=(4, 2))

        self._ore_frame = tk.Frame(f2, bg=BG2)
        self._ore_frame.pack(fill="x", padx=10, pady=(0, 6))

        self._lbl_ore_vuote = tk.Label(self._ore_frame, text="nessuna sessione oggi",
                                        font=("Segoe UI", 9), bg=BG2, fg=GRY)
        self._lbl_ore_vuote.pack(anchor="w")

        # ── Ultimo invio ──────────────────────────────────────────────────────
        f3 = tk.Frame(root, bg=BG2)
        f3.pack(fill="x", padx=PAD, pady=4)

        row3 = tk.Frame(f3, bg=BG2)
        row3.pack(fill="x", padx=10, pady=6)

        tk.Label(row3, text="Ultimo invio:", font=("Segoe UI", 9),
                 bg=BG2, fg=SML).pack(side="left")
        self._lbl_inv = tk.Label(row3, text="—", font=("Segoe UI", 9),
                                  bg=BG2, fg=GRY)
        self._lbl_inv.pack(side="left", padx=6)

        # ── Log ───────────────────────────────────────────────────────────────
        f4 = tk.Frame(root, bg=BG)
        f4.pack(fill="both", expand=True, padx=PAD, pady=(4, PAD))

        tk.Label(f4, text="LOG", font=("Segoe UI", 8, "bold"),
                 bg=BG, fg=SML).pack(anchor="w")

        self._log_text = tk.Text(f4, height=7, bg="#141a22", fg=SML,
                                  font=("Consolas", 8), relief="flat",
                                  state="disabled", wrap="word",
                                  insertbackground=TXT)
        self._log_text.pack(fill="both", expand=True, pady=2)

        # Tag colori log
        self._log_text.tag_config("ok",   foreground=GRN)
        self._log_text.tag_config("warn", foreground=AMB)
        self._log_text.tag_config("err",  foreground=RED)
        self._log_text.tag_config("info", foreground=SML)

        # Colori salvati
        self._c = {"bg2": BG2, "blu": BLU, "grn": GRN, "red": RED,
                   "amb": AMB, "gry": GRY, "txt": TXT, "sml": SML}

    # ── API pubblica (thread-safe) ─────────────────────────────────────────────

    def set_progetto(self, project_id: str, attivo: bool):
        self.queue.put(("progetto", project_id, attivo))

    def set_dmgdesk(self, online: bool):
        self.queue.put(("dmgdesk", online))

    def set_ore(self, ore_dict: dict):
        """ore_dict = {project_id: seconds}"""
        self.queue.put(("ore", dict(ore_dict)))

    def set_ultimo_invio(self, ts: str, n_record: int):
        self.queue.put(("invio", ts, n_record))

    def add_log(self, msg: str, level: str = "info"):
        """level: 'ok' | 'warn' | 'err' | 'info'"""
        self.queue.put(("log", msg, level))

    # ── Loop interno ──────────────────────────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                item = self.queue.get_nowait()
                self._apply(item)
        except queue.Empty:
            pass
        self.root.after(300, self._poll_queue)

    def _apply(self, item):
        c = self._c
        kind = item[0]

        if kind == "progetto":
            _, pid, attivo = item
            self._lbl_prog.config(text=pid or "—")
            if attivo:
                self._dot_att.config(fg=c["grn"])
                self._lbl_stato.config(text="● ATTIVO", fg=c["grn"])
            elif pid and pid != "—":
                self._dot_att.config(fg=c["amb"])
                self._lbl_stato.config(text="in pausa", fg=c["amb"])
            else:
                self._dot_att.config(fg=c["gry"])
                self._lbl_stato.config(text="", fg=c["gry"])

        elif kind == "dmgdesk":
            _, online = item
            self._dot_dmg.config(fg=c["grn"] if online else c["red"])

        elif kind == "ore":
            _, ore = item
            for w in self._ore_frame.winfo_children():
                w.destroy()
            if not ore:
                tk.Label(self._ore_frame, text="nessuna sessione oggi",
                         font=("Segoe UI", 9), bg=c["bg2"], fg=c["gry"]).pack(anchor="w")
            else:
                for pid, sec in sorted(ore.items(), key=lambda x: -x[1]):
                    h = int(sec // 3600)
                    m = int((sec % 3600) // 60)
                    s = int(sec % 60)
                    t = f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"
                    row = tk.Frame(self._ore_frame, bg=c["bg2"])
                    row.pack(fill="x", pady=1)
                    tk.Label(row, text=pid, font=("Segoe UI", 9, "bold"),
                             bg=c["bg2"], fg=c["txt"]).pack(side="left")
                    tk.Label(row, text=t, font=("Consolas", 9),
                             bg=c["bg2"], fg=c["blu"]).pack(side="right")

        elif kind == "invio":
            _, ts, n = item
            self._lbl_inv.config(
                text=f"{ts}  ({n} record)" if n else ts,
                fg=c["grn"]
            )

        elif kind == "log":
            _, msg, level = item
            ts = datetime.now().strftime("%H:%M:%S")
            line = f"{ts}  {msg}\n"
            self._log_text.config(state="normal")
            self._log_text.insert("end", line, level)
            # Mantieni max 50 righe
            lines = int(self._log_text.index("end-1c").split(".")[0])
            if lines > 50:
                self._log_text.delete("1.0", f"{lines-50}.0")
            self._log_text.see("end")
            self._log_text.config(state="disabled")

    def run(self):
        self.root.mainloop()

    def close(self):
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
