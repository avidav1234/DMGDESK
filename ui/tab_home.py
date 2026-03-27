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
        inner_width = max(400, event.width - 48)
        self._canvas.itemconfig(self._win_id, width=inner_width)

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

    def _bind_click(self, widget, fn):
        """Applica click ricorsivamente a tutti i figli."""
        widget.bind("<Button-1>", lambda e: fn())
        for child in widget.winfo_children():
            child.bind("<Button-1>", lambda e, f=fn: f())

    def _open_project(self, pid):
        """Naviga a Lavori e apre il progetto."""
        tp = getattr(self._mw, "tab_progetti", None)
        if tp:
            tp._selected_id = pid
            tp._page        = "projects"
            tp._build_topbar()
            tp._refresh()
        try:
            sw = getattr(self._mw, '_switch', None)
            if sw: sw("lavori")
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # Render
    # ══════════════════════════════════════════════════════════════════════════

    def _render(self):
        for w in self._inner.winfo_children():
            w.destroy()

        today      = datetime.now()
        today_str  = today.strftime("%Y-%m-%d")
        projects   = self._projects
        deliveries = self._deliveries
        pallet_list= self._pallet_list
        setup_data = self._setup_data

        in_progress = [p for p in projects if not p.get("archived")]
        all_pgm = [pr for p in in_progress
                   for s in p.get("steps",[]) for t in s.get("tasks",[])
                   if t.get("text","").strip().lower() == "fresatura"
                   for pr in t.get("programs",[]) if pr.get("tipoGruppo") != "ipm"]

        da_fare_n   = sum(1 for x in all_pgm if x.get("stato") == "da_fare")
        in_mac_n    = sum(1 for x in all_pgm if x.get("stato") == "in_macchina")
        oggi_n      = sum(1 for x in all_pgm if (x.get("tempoFine","") or "").startswith(today_str))

        def get_del(pid):
            return next((d for d in deliveries if d.get("projectId") == pid), None)

        def pallet_info(pnum):
            pd2  = next((x for x in pallet_list if x.get("numero") == pnum), {})
            stato= (pd2.get("stato") or "vuoto").lower().replace("_"," ")
            pid  = pd2.get("progetto_id")
            proj = next((p for p in in_progress if p.get("id") == pid), None) if pid else None
            pct  = get_progress(proj) if proj else None
            pgms = []
            if proj:
                pgms = [pr for s in proj.get("steps",[]) for t in s.get("tasks",[])
                        if t.get("text","").strip().lower()=="fresatura"
                        for pr in t.get("programs",[]) if pr.get("tipoGruppo")!="ipm"]
            tot  = len(pgms)
            done = sum(1 for p in pgms if p.get("stato")=="completato")
            return {"stato":stato,"pid":pid,"proj":proj,"pct":pct,"tot":tot,"done":done,
                    "nome":pd2.get("progetto_nome",""),"colore":proj.get("color","#1D5FAD") if proj else "#1D5FAD"}

        def pallet_colors(stato, has_proj, pct):
            if stato == "in lavorazione": return {"bg":"#dbeafe","fg":"#0d2d5e","bd":"#1D5FAD"}
            if pct is not None and pct >= 100: return {"bg":"#dcfce7","fg":"#14532d","bd":"#16a34a"}
            if has_proj: return {"bg":"#fefce8","fg":"#854d0e","bd":"#eab308"}
            return {"bg":"#f1f5f9","fg":"#94a3b8","bd":"#e2e8f0"}

        # Pallet IN LAVORAZIONE
        pal_lav  = next((x for x in pallet_list if (x.get("stato","")).lower().replace("_"," ")=="in lavorazione"), None)
        proj_lav = next((p for p in in_progress if p.get("id")==pal_lav.get("progetto_id")), None) if pal_lav else None
        lav_pgms = []
        if proj_lav:
            lav_pgms = [pr for s in proj_lav.get("steps",[]) for t in s.get("tasks",[])
                        if t.get("text","").strip().lower()=="fresatura"
                        for pr in t.get("programs",[]) if pr.get("tipoGruppo")!="ipm"]

        # Scadenze tutti i progetti con scadenza
        con_scad = []
        for p in in_progress:
            d = get_del(p.get("id",""))
            if d and d.get("dueDate") and not d.get("delivered"):
                dy = days_until(d.get("dueDate"))
                if dy is not None:
                    pnum = next((x.get("numero") for x in pallet_list if x.get("progetto_id")==p.get("id")), None)
                    con_scad.append({"p":p,"days":dy,"pnum":pnum})
        con_scad.sort(key=lambda x: x["days"])

        critici_n = sum(1 for x in con_scad if x["days"] <= 0)

        # Utensili con problemi
        mancanti  = [u for u in setup_data.get("non_utilizzati",[]) if u.get("provenienza")=="richiesto_da_progetto"]
        da_mont   = setup_data.get("da_montare",[])
        fin_vita  = setup_data.get("fin_vita",[])
        a_rischio = setup_data.get("previsione_vita",{}).get("utensili_critici",[]) if isinstance(setup_data.get("previsione_vita"),dict) else []
        ut_map = {}
        for u in mancanti:
            ut_map[u["alias"]] = {"alias":u["alias"],"tipo":"mancante","label":"MANCANTE","color":"#dc2626","bg":"#fef2f2","bd":"#fca5a5","detail":""}
        for u in da_mont:
            if u["alias"] not in ut_map:
                ut_map[u["alias"]] = {"alias":u["alias"],"tipo":"da_montare","label":"DA MONTARE","color":"#d97706","bg":"#fffbeb","bd":"#fcd34d","detail":f"pos.{u.get('posizione','')}"}
        for u in fin_vita:
            if u["alias"] not in ut_map:
                pct_u = u.get("life_percent")
                label = f"{pct_u:.0f}%" if isinstance(pct_u, (int,float)) else "FINE VITA"
                ut_map[u["alias"]] = {"alias":u["alias"],"tipo":"fin_vita","label":label,"color":"#c2410c","bg":"#fff7ed","bd":"#fdba74","detail":f"pos.{u.get('posizione','')}"}
        for u in a_rischio:
            if u.get("alias","") not in ut_map:
                ut_map[u["alias"]] = {"alias":u["alias"],"tipo":"rischio","label":f"pgm {u.get('programma_critico','?')}","color":"#7c3aed","bg":"#f5f3ff","bd":"#c4b5fd","detail":u.get("progetto","")}
        ut_list = sorted(ut_map.values(), key=lambda x: {"mancante":0,"da_montare":1,"fin_vita":2,"rischio":3}.get(x["tipo"],9))

        pad = self._inner
        BG  = TC["bg"]

        # ── Layout 3 colonne ────────────────────────────────────────────────
        body = tk.Frame(pad, bg=BG)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, minsize=280)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, minsize=190)

        # ══ COL 0 — PALLET ══════════════════════════════════════════════════
        col0 = tk.Frame(body, bg=BG)
        col0.grid(row=0, column=0, sticky="nsew", padx=(0,10), pady=0)
        tk.Label(col0, text="PALLET", font=("Inter",8,"bold"),
                 fg="#0d2d5e", bg=BG).pack(anchor="w", pady=(0,6))

        pg = tk.Frame(col0, bg=BG)
        pg.pack(fill="x")
        pg.columnconfigure(0, weight=1)
        pg.columnconfigure(1, weight=1)

        for idx in range(6):
            n   = idx + 1
            col = idx % 2
            row = idx // 2
            inf = pallet_info(n)
            c   = pallet_colors(inf["stato"], bool(inf["proj"]), inf["pct"])
            is_lav = inf["stato"] == "in lavorazione"

            card = tk.Frame(pg, bg=c["bg"], highlightbackground=c["bd"], highlightthickness=2)
            card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew", ipadx=2, ipady=2)

            top = tk.Frame(card, bg=c["bg"])
            top.pack(fill="x", padx=8, pady=(8,2))
            tk.Label(top, text=f"P{n}", font=("Inter",22,"bold"),
                     fg=c["fg"], bg=c["bg"]).pack(side="left")
            if is_lav:
                tk.Label(top, text="● LIVE", font=("Inter",7,"bold"),
                         fg="#1D5FAD", bg="#eff6ff", padx=3).pack(side="right")

            if inf["proj"]:
                nome = inf["proj"].get("name","")
                tk.Label(card, text=nome, font=("Inter",9,"bold"),
                         fg=c["fg"], bg=c["bg"], anchor="w",
                         wraplength=110).pack(fill="x", padx=8)
                # Barra
                bf = tk.Frame(card, bg="#e2e8f0", height=4)
                bf.pack(fill="x", padx=8, pady=(2,1))
                bf.update_idletasks()
                tk.Frame(bf, bg=inf["colore"], height=4).place(
                    x=0, y=0, relwidth=(inf["pct"] or 0)/100, height=4)
                foot = tk.Frame(card, bg=c["bg"])
                foot.pack(fill="x", padx=8, pady=(0,6))
                tk.Label(foot, text=f"{inf['done']}/{inf['tot']}", font=("Inter",8),
                         fg=c["fg"], bg=c["bg"]).pack(side="left")
                tk.Label(foot, text=f"{inf['pct']}%", font=("Inter",9,"bold"),
                         fg=c["fg"], bg=c["bg"]).pack(side="right")
            else:
                tk.Label(card, text="VUOTO", font=("Inter",8,"bold"),
                         fg=c["fg"], bg=c["bg"]).pack(anchor="w", padx=8, pady=(0,8))

            if inf["pid"]:
                self._bind_click(card, lambda p2=inf["pid"]: self._open_project(p2))

        # ══ COL 1 — CENTRO ══════════════════════════════════════════════════
        col1 = tk.Frame(body, bg=BG)
        col1.grid(row=0, column=1, sticky="nsew", padx=(0,10))

        # Progetto IN LAVORAZIONE
        lav_frame = tk.Frame(col1, bg="#fff", highlightbackground="#e2e8f0", highlightthickness=1)
        lav_frame.pack(fill="x", pady=(0,8))
        tk.Label(lav_frame, text="PROGETTO IN LAVORAZIONE", font=("Inter",8,"bold"),
                 fg="#0d2d5e", bg="#fff").pack(anchor="w", padx=14, pady=(10,6))
        if proj_lav:
            lav_tot  = len(lav_pgms)
            lav_done = sum(1 for x in lav_pgms if x.get("stato")=="completato")
            lav_mac  = sum(1 for x in lav_pgms if x.get("stato")=="in_macchina")
            lav_pct  = round(lav_done/lav_tot*100) if lav_tot else 0
            lav_col  = proj_lav.get("color","#1D5FAD")

            nr = tk.Frame(lav_frame, bg="#fff")
            nr.pack(fill="x", padx=14, pady=(0,4))
            tk.Label(nr, text=proj_lav.get("name",""), font=("Inter",13,"bold"),
                     fg="#0d2d5e", bg="#fff").pack(side="left")
            tk.Label(nr, text=f"P{pal_lav['numero']}", font=("Inter",8,"bold"),
                     fg="#fff", bg="#1D5FAD", padx=4).pack(side="left", padx=6)

            bf2 = tk.Frame(lav_frame, bg="#e2e8f0", height=8)
            bf2.pack(fill="x", padx=14, pady=(0,4))
            bf2.update_idletasks()
            tk.Frame(bf2, bg=lav_col, height=8).place(
                x=0, y=0, relwidth=lav_pct/100, height=8)

            sr = tk.Frame(lav_frame, bg="#fff")
            sr.pack(fill="x", padx=14, pady=(0,10))
            tk.Label(sr, text=f"{lav_done}/{lav_tot} completati", font=("Inter",9), fg="#475569", bg="#fff").pack(side="left")
            tk.Label(sr, text=f"{lav_mac} in mac.", font=("Inter",9), fg="#1D5FAD", bg="#fff").pack(side="left", padx=10)
            tk.Label(sr, text=f"{lav_pct}%", font=("Inter",10,"bold"), fg=lav_col, bg="#fff").pack(side="right")
        else:
            tk.Label(lav_frame, text="Nessun pallet in lavorazione",
                     font=("Inter",10,"italic"), fg="#94a3b8", bg="#fff").pack(
                     anchor="w", padx=14, pady=(0,10))

        # Scadenze
        sc_frame = tk.Frame(col1, bg="#fff", highlightbackground="#e2e8f0", highlightthickness=1)
        sc_frame.pack(fill="x", pady=(0,8))
        tk.Label(sc_frame, text="SCADENZE PROGETTI", font=("Inter",8,"bold"),
                 fg="#0d2d5e", bg="#fff").pack(anchor="w", padx=14, pady=(10,6))
        if not con_scad:
            tk.Label(sc_frame, text="Nessun progetto con scadenza",
                     font=("Inter",10,"italic"), fg="#94a3b8", bg="#fff").pack(
                     anchor="w", padx=14, pady=(0,10))
        else:
            for item in con_scad:
                dy   = item["days"]
                p    = item["p"]
                pnum = item["pnum"]
                over = dy < 0; tod = dy == 0; soon = 0 < dy <= 3
                color= "#dc2626" if over else ("#d97706" if tod else ("#c2410c" if soon else "#475569"))
                bg_r = "#fef2f2" if over else ("#fffbeb" if tod else ("#fff7ed" if soon else "#f8fafc"))
                badge= f"{abs(dy)}gg fa" if over else ("OGGI" if tod else f"{dy}gg")

                rf = tk.Frame(sc_frame, bg=bg_r, highlightbackground=color, highlightthickness=1, cursor="hand2")
                rf.pack(fill="x", padx=10, pady=2)
                tk.Label(rf, text="●", fg=color, bg=bg_r, font=("Inter",8)).pack(side="left", padx=(6,2), pady=4)
                tk.Label(rf, text=p.get("name",""), font=("Inter",9,"bold"), fg="#1e293b", bg=bg_r).pack(side="left")
                if pnum:
                    tk.Label(rf, text=f"P{pnum}", font=("Inter",7,"bold"),
                             fg="#0d2d5e", bg="#eff6ff", padx=2).pack(side="left", padx=4)
                tk.Label(rf, text=badge, font=("Inter",8,"bold"), fg=color,
                         bg="#fff", padx=4, pady=1,
                         highlightbackground=color, highlightthickness=1).pack(side="right", padx=6, pady=3)
                self._bind_click(rf, lambda p2=p["id"]: self._open_project(p2))
            tk.Frame(sc_frame, bg="#fff", height=4).pack()

        # Utensili
        ut_frame = tk.Frame(col1, bg="#fff", highlightbackground="#e2e8f0", highlightthickness=1)
        ut_frame.pack(fill="x", pady=(0,0))
        hut = tk.Frame(ut_frame, bg="#fff")
        hut.pack(fill="x", padx=14, pady=(10,6))
        tk.Label(hut, text="UTENSILI — ATTENZIONE", font=("Inter",8,"bold"),
                 fg="#0d2d5e", bg="#fff").pack(side="left")
        if ut_list:
            tk.Label(hut, text=str(len(ut_list)), font=("Inter",8,"bold"),
                     fg="#dc2626", bg="#fef2f2", padx=4).pack(side="left", padx=6)
        if not ut_list:
            tk.Label(ut_frame, text="✓ Nessun problema rilevato",
                     font=("Inter",10), fg="#22c55e", bg="#fff").pack(
                     anchor="w", padx=14, pady=(0,10))
        else:
            for u in ut_list:
                ur = tk.Frame(ut_frame, bg=u["bg"],
                              highlightbackground=u["bd"], highlightthickness=1)
                ur.pack(fill="x", padx=10, pady=2)
                tk.Label(ur, text=u["label"], font=("Inter",7,"bold"),
                         fg=u["color"], bg="#fff",
                         highlightbackground=u["bd"], highlightthickness=1,
                         padx=4, width=10).pack(side="left", padx=(6,4), pady=4)
                tk.Label(ur, text=u["alias"], font=("Consolas",9,"bold"),
                         fg="#1e293b", bg=u["bg"]).pack(side="left")
                if u["detail"]:
                    tk.Label(ur, text=u["detail"], font=("Inter",7),
                             fg=u["color"], bg=u["bg"]).pack(side="right", padx=6)
            tk.Frame(ut_frame, bg="#fff", height=4).pack()

        # ══ COL 2 — METRICHE ════════════════════════════════════════════════
        col2 = tk.Frame(body, bg=BG)
        col2.grid(row=0, column=2, sticky="n")
        tk.Label(col2, text="METRICHE TURNO", font=("Inter",8,"bold"),
                 fg="#0d2d5e", bg=BG).pack(anchor="w", pady=(0,6))

        for val, label, sub, color, bg_m in [
            (da_fare_n,  "Da fare",         f"{len(in_progress)} lavori attivi", "#0d2d5e", "#eff6ff"),
            (in_mac_n,   "In macchina",      "programmi attivi",                 "#1D5FAD", "#dbeafe"),
            (oggi_n,     "Completati oggi",  "nel turno corrente",               "#166534", "#dcfce7"),
            (critici_n,  "Critici",          "scaduti o in ritardo",
             "#dc2626" if critici_n else "#166534",
             "#fef2f2" if critici_n else "#dcfce7"),
        ]:
            mc = tk.Frame(col2, bg=bg_m, highlightbackground=color, highlightthickness=1)
            mc.pack(fill="x", pady=4, ipadx=8, ipady=6)
            tk.Label(mc, text=str(val), font=("Inter",26,"bold"), fg=color, bg=bg_m).pack(anchor="w", padx=12, pady=(8,0))
            tk.Label(mc, text=label,    font=("Inter",9,"bold"),  fg=color, bg=bg_m).pack(anchor="w", padx=12)
            tk.Label(mc, text=sub,      font=("Inter",7),         fg=color, bg=bg_m, wraplength=160).pack(anchor="w", padx=12, pady=(0,8))

        self._schedule_next()

