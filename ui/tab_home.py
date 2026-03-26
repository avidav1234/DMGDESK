"""
TabHome — Dashboard turno per DMGDesk desktop.
Classe autonoma: gestisce dati, render e click.
Usa Canvas+Scrollbar nativo (più veloce di CTkScrollableFrame).
"""
import tkinter as tk
import customtkinter as ctk
import threading
import urllib.request
import json
from datetime import datetime

# Import helper da tab_progetti
from .tab_progetti import (
    TC, get_progress, days_until, delivery_urgency,
    _load_progetti, _load_deliveries, _inject_pallet_assegnati
)

STATO_BG = {"grezzo": TC["grezzo_bg"], "finito": TC["finito_bg"],
            "guasto": TC["guasto_bg"], "vuoto":  TC["vuoto_bg"]}
STATO_FG = {"grezzo": TC["grezzo_fg"], "finito": TC["finito_fg"],
            "guasto": TC["guasto_fg"], "vuoto":  TC["vuoto_fg"]}


class TabHome:
    """
    Dashboard turno — layout B compresso.
    on_open_project(pid): callback per aprire un progetto nel tab Lavori.
    """
    def __init__(self, parent_frame, main_window):
        self._parent      = parent_frame
        self._mw          = main_window          # riferimento al main_window
        self._projects    = []
        self._deliveries  = []
        self._pallet_list = []
        self._setup_data  = {}
        self._after_id    = None
        self._last_hash   = None
        self._built       = False

        self._build_skeleton()
        self._load_async()

    # ══════════════════════════════════════════════════════════════════════════
    # Skeleton — frame con canvas scrollabile nativo
    # ══════════════════════════════════════════════════════════════════════════

    def _build_skeleton(self):
        self._frame = tk.Frame(self._parent, bg=TC["bg"])
        self._frame.pack(fill="both", expand=True, padx=4, pady=4)

        self._canvas = tk.Canvas(self._frame, bg=TC["bg"],
                                  highlightthickness=0, bd=0,
                                  width=600)  # larghezza minima iniziale
        self._vsb    = tk.Scrollbar(self._frame, orient="vertical",
                                     command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vsb.set)

        self._vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=TC["bg"])
        self._win_id = self._canvas.create_window((24, 16), window=self._inner,
                                                   anchor="nw")

        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(int(-e.delta/120), "units"))
        self._inner.bind("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(int(-e.delta/120), "units"))

    def _on_inner_configure(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        print(f"[DEBUG canvas] w={event.width} h={event.height}")
        inner_width = max(400, event.width - 48)
        self._canvas.itemconfig(self._win_id, width=inner_width)
        print(f"[DEBUG inner] width set to {inner_width}")

    # ══════════════════════════════════════════════════════════════════════════
    # Caricamento dati
    # ══════════════════════════════════════════════════════════════════════════

    def _load_async(self):
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        # Dati locali (veloci)
        try:
            projects   = _load_progetti()
            deliveries = _load_deliveries()
            projects   = _inject_pallet_assegnati(projects)
        except Exception:
            projects, deliveries = [], []

        # Pallet e setup via HTTP (richiede server)
        pallet_list, setup_data = [], {}
        try:
            r = urllib.request.urlopen("http://localhost:8000/api/pallet/", timeout=2)
            pallet_list = json.loads(r.read()).get("pallet", [])
        except Exception:
            pass
        try:
            r = urllib.request.urlopen(
                "http://localhost:8000/api/progetti/analisi-setup/non-utilizzati", timeout=2)
            setup_data = json.loads(r.read())
        except Exception:
            pass

        # Hash per evitare ridisegni inutili
        import hashlib as _hl
        h = _hl.md5(json.dumps(
            [projects, deliveries, pallet_list, setup_data],
            sort_keys=True, default=str).encode()).hexdigest()

        self._projects    = projects
        self._deliveries  = deliveries
        self._pallet_list = pallet_list
        self._setup_data  = setup_data

        if h == self._last_hash:
            self._schedule_next()
            return
        self._last_hash = h
        self._canvas.after(0, self._render)

    def _schedule_next(self):
        if self._after_id:
            try: self._canvas.after_cancel(self._after_id)
            except Exception: pass
        self._after_id = self._canvas.after(30000, self._load_async)

    def refresh(self):
        """Chiamato dall'esterno per forzare un refresh immediato."""
        if self._after_id:
            try: self._canvas.after_cancel(self._after_id)
            except Exception: pass
        self._load_async()

    # ══════════════════════════════════════════════════════════════════════════
    # Render
    # ══════════════════════════════════════════════════════════════════════════

    def _render(self):
        print(f"[DEBUG render] inner size: {self._inner.winfo_width()}x{self._inner.winfo_height()}")
        print(f"[DEBUG render] canvas size: {self._canvas.winfo_width()}x{self._canvas.winfo_height()}")
        for w in self._inner.winfo_children():
            w.destroy()

        today      = datetime.now().strftime("%Y-%m-%d")
        projects   = self._projects
        deliveries = self._deliveries
        pallet_list= self._pallet_list
        setup_data = self._setup_data

        in_progress = [p for p in projects if not p.get("archived") and get_progress(p) < 100]
        all_pgm = [pr for p in in_progress
                   for s in p.get("steps",[]) for t in s.get("tasks",[])
                   if t.get("text","").strip().lower() == "fresatura"
                   for pr in t.get("programs",[]) if pr.get("tipoGruppo") != "ipm"]

        da_fare    = [x for x in all_pgm if x.get("stato") == "da_fare"]
        in_mac     = [x for x in all_pgm if x.get("stato") == "in_macchina"]
        completati = [x for x in all_pgm if x.get("stato") == "completato"]
        oggi_pgm   = [x for x in all_pgm if (x.get("tempoFine") or "").startswith(today)]
        da_montare = len(setup_data.get("da_montare", []))
        fine_vita  = len(setup_data.get("fin_vita",   []))

        def get_del(pid):
            return next((d for d in deliveries if d.get("projectId") == pid), None)

        urgenti = sorted(
            [p for p in in_progress if (lambda d, dy: d and not d.get("delivered") and dy is not None and dy <= 7)(
                get_del(p["id"]),
                days_until(get_del(p["id"])["dueDate"])
                if get_del(p["id"]) and get_del(p["id"]).get("dueDate") else None)],
            key=lambda p: days_until(get_del(p["id"])["dueDate"]) if get_del(p["id"]) else 99
        )

        pad = self._inner
        BG  = TC["bg"]

        # ══ 1° PIANO — PALLET ═══════════════════════════════════════════════
        tk.Label(pad, text="PALLET MACCHINA", font=("Inter",9,"bold"),
                 fg=TC["muted"], bg=BG).pack(anchor="w", pady=(0,10))

        pg = tk.Frame(pad, bg=BG)
        pg.pack(fill="x", pady=(0,20))
        for i in range(3): pg.columnconfigure(i, weight=1)

        for idx in range(6):
            n    = idx + 1
            col  = idx % 3
            row  = idx // 3
            pd2  = next((x for x in pallet_list if x.get("numero") == n), {})
            stato= (pd2.get("stato") or "vuoto").lower()
            nome = pd2.get("progetto_nome") or ""
            pid  = pd2.get("progetto_id")
            proj = next((p for p in in_progress if p.get("id") == pid), None) if pid else None
            pct  = get_progress(proj) if proj else None
            d    = get_del(pid) if pid else None
            days = days_until(d.get("dueDate")) if d and d.get("dueDate") and not d.get("delivered") else None
            is_urg   = days is not None and days <= 3
            is_empty = stato == "vuoto" and not nome
            bg_c = STATO_BG.get(stato, TC["vuoto_bg"])
            fg_c = STATO_FG.get(stato, TC["vuoto_fg"])
            bd_c = "#c0392b" if is_urg else ("#e2e8f0" if is_empty else fg_c)

            card = tk.Frame(pg, bg=bg_c, highlightbackground=bd_c,
                            highlightthickness=2 if is_urg else 1,
                            cursor="hand2" if pid else "arrow")
            card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

            top = tk.Frame(card, bg=bg_c)
            top.pack(fill="x", padx=12, pady=(10,4))
            tk.Label(top, text=f"P{n}", font=("Inter",22,"bold"),
                     fg="#C8C5BE" if is_empty else fg_c, bg=bg_c).pack(side="left")
            tk.Label(top, text=stato, font=("Inter",9,"bold"),
                     fg="#C8C5BE" if is_empty else fg_c, bg=bg_c).pack(side="left", padx=6)
            if is_urg:
                tk.Label(top, text="OGGI" if days == 0 else f"{days}gg",
                         font=("Inter",9,"bold"), fg="#c0392b", bg="#fdf4f4", padx=4).pack(side="right")

            if nome:
                tk.Label(card, text=nome, font=("Inter",13,"bold"),
                         fg=TC["text"], bg=bg_c, anchor="w").pack(fill="x", padx=12, pady=(2,4))
                if pct is not None:
                    bf = tk.Frame(card, bg="#D0CFC8", height=6)
                    bf.pack(fill="x", padx=12, pady=(0,4))
                    bf.update_idletasks()
                    tk.Frame(bf, bg=fg_c, height=6).place(x=0, y=0, relwidth=pct/100, height=6)
                    tk.Label(card, text=f"{pct}%", font=("Inter",11,"bold"),
                             fg=fg_c, bg=bg_c, anchor="e").pack(fill="x", padx=12, pady=(0,8))

            if pid:
                self._bind_click(card, lambda p2=pid: self._open_project(p2))

        # ══ 2° PIANO — ALERT ════════════════════════════════════════════════
        if urgenti or da_montare or fine_vita:
            ar = tk.Frame(pad, bg=BG)
            ar.pack(fill="x", pady=(0, 16))
            for p in urgenti:
                d    = get_del(p["id"])
                days = days_until(d.get("dueDate")) if d else None
                txt  = "oggi" if days == 0 else (f"scaduta {abs(days)}gg fa" if days and days < 0 else f"tra {days}gg")
                af = tk.Frame(ar, bg="#fdf4f4", highlightbackground="#dda0a0", highlightthickness=1, cursor="hand2")
                af.pack(side="left", fill="x", expand=True, padx=(0,4))
                tk.Label(af, text=f"  {p['name']}  —  {txt}",
                         font=("Inter",10,"bold"), fg="#6b2929", bg="#fdf4f4", anchor="w").pack(side="left", padx=8, pady=6)
                tk.Label(af, text="OGGI" if days == 0 else (f"{abs(days)}gg fa" if days and days < 0 else f"{days}gg"),
                         font=("Inter",9,"bold"), fg="#c0392b", bg="#fff", padx=6, pady=2).pack(side="right", padx=8)
                self._bind_click(af, lambda p2=p["id"]: self._open_project(p2))
            if da_montare or fine_vita:
                msg = "🔧"
                if da_montare: msg += f"  {da_montare} da montare"
                if fine_vita:  msg += f"  {fine_vita} a fine vita"
                uf = tk.Frame(ar, bg="#fdf6e3", highlightbackground="#c8953a", highlightthickness=1)
                uf.pack(side="left", padx=(0,0))
                tk.Label(uf, text=msg, font=("Inter",10,"bold"), fg="#9a6b2e",
                         bg="#fdf6e3", anchor="w").pack(padx=10, pady=6)

        # ══ 3° PIANO — METRICHE + LAVORI ════════════════════════════════════
        bot = tk.Frame(pad, bg=BG)
        bot.pack(fill="both", expand=True)
        bot.columnconfigure(1, weight=1)

        # Metriche compatte
        mf = tk.Frame(bot, bg=BG)
        mf.grid(row=0, column=0, sticky="n", padx=(0,14))
        for mi, (val, label, sub, color, bg_m) in enumerate([
            (len(da_fare),    "Da fare",   f"{len(in_progress)} lavori", TC["muted"],  TC["surface2"]),
            (len(in_mac),     "In macchina","attivi",                    "#0d2d5e",    "#eef4fb"),
            (len(oggi_pgm),   "Oggi",       f"{len(completati)} tot.",   "#2d8a55",    "#f0f9f4"),
            (da_montare+fine_vita, "Critici",
             f"{da_montare} da montare" if da_montare else "ok",
             "#c0392b" if (da_montare+fine_vita) > 0 else "#2d8a55",
             "#fdf4f4" if (da_montare+fine_vita) > 0 else "#f0f9f4"),
        ]):
            mc = tk.Frame(mf, bg=bg_m, width=110, height=62)
            mc.grid(row=mi//2, column=mi%2, padx=3, pady=3, sticky="nsew")
            mc.grid_propagate(False)
            tk.Label(mc, text=str(val), font=("Inter",16,"bold"), fg=color, bg=bg_m).pack(anchor="w", padx=8, pady=(6,0))
            tk.Label(mc, text=label,    font=("Inter",8,"bold"),  fg=color, bg=bg_m).pack(anchor="w", padx=8)
            tk.Label(mc, text=sub,      font=("Inter",7),         fg=TC["muted"], bg=bg_m).pack(anchor="w", padx=8)

        # Lavori compatti
        lf = tk.Frame(bot, bg=BG)
        lf.grid(row=0, column=1, sticky="nsew")
        tk.Label(lf, text="LAVORI IN CORSO", font=("Inter",8,"bold"),
                 fg=TC["muted"], bg=BG).pack(anchor="w", pady=(0,4))

        for p in in_progress[:6]:
            pct2  = get_progress(p)
            d     = get_del(p.get("id",""))
            days2 = days_until(d.get("dueDate")) if d and d.get("dueDate") and not d.get("delivered") else None
            pnum  = next((x.get("numero") for x in pallet_list if x.get("progetto_id") == p.get("id")), None)
            color = p.get("color", TC["accent"])

            rf = tk.Frame(lf, bg=TC["surface"], highlightbackground="#dde3ec",
                          highlightthickness=1, cursor="hand2")
            rf.pack(fill="x", pady=2)
            tk.Frame(rf, bg=color, width=3).pack(side="left", fill="y")
            inn = tk.Frame(rf, bg=TC["surface"])
            inn.pack(fill="x", expand=True, padx=8, pady=4)

            tr = tk.Frame(inn, bg=TC["surface"])
            tr.pack(fill="x")
            tk.Label(tr, text=p.get("name","?"), font=("Inter",10,"bold"),
                     fg=TC["text"], bg=TC["surface"]).pack(side="left")
            if pnum:
                tk.Label(tr, text=f"P{pnum}", font=("Inter",7,"bold"),
                         fg="#0d2d5e", bg="#eef4fb", padx=3).pack(side="left", padx=3)

            bbar = tk.Frame(inn, bg=TC["surface2"], height=3)
            bbar.pack(fill="x", pady=(2,1))
            bbar.update_idletasks()
            tk.Frame(bbar, bg=color, height=3).place(x=0, y=0, relwidth=pct2/100, height=3)

            ir = tk.Frame(inn, bg=TC["surface"])
            ir.pack(fill="x")
            pct_c = "#2d8a55" if pct2 == 100 else color
            tk.Label(ir, text=f"{pct2}%", font=("Inter",9,"bold"),
                     fg=pct_c, bg=TC["surface"]).pack(side="right")
            if days2 is not None:
                dc = "#c0392b" if days2 <= 3 else ("#9a6b2e" if days2 <= 7 else TC["muted"])
                dt = "oggi" if days2 == 0 else (f"scaduta {abs(days2)}gg fa" if days2 < 0 else f"{days2}gg")
                tk.Label(ir, text=dt, font=("Inter",7,"bold"),
                         fg=dc, bg=TC["surface"]).pack(side="right", padx=4)

            self._bind_click(rf, lambda p2=p["id"]: self._open_project(p2))

        self._schedule_next()

