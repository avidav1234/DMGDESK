"""
Tab Progetti — WorkTrack integrato in DMGDesk desktop
Porting fedele completo: tutti i componenti della versione web inclusi.
"""

import customtkinter as ctk
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.simpledialog
import tkinter.messagebox as mb
import tkinter.filedialog as fd
import json, threading, os, sys, re
from pathlib import Path
from datetime import datetime, date

# ── Config helpers ─────────────────────────────────────────────────────────────

def _carica_config() -> dict:
    try:
        from database.db_handler import carica_configurazione
        cfg = carica_configurazione()
        if isinstance(cfg, dict):
            return cfg
    except Exception:
        pass
    try:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        with open(os.path.join(base, "config.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _progetti_path():
    cfg = _carica_config()
    base = (cfg.get("tools_toa_folder") or "").strip()
    return Path(base) / "worktrack_projects.json" if base else None

def _templates_path():
    cfg = _carica_config()
    base = (cfg.get("tools_toa_folder") or "").strip()
    return Path(base) / "worktrack_templates.json" if base else None

def _deliveries_path():
    cfg = _carica_config()
    base = (cfg.get("tools_toa_folder") or "").strip()
    return Path(base) / "worktrack_deliveries.json" if base else None

def _load_json(path) -> list:
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list): return data
            if isinstance(data, dict): return data.get("projects", [])
        except Exception:
            pass
    return []

def _load_progetti():
    path = _progetti_path()
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("projects", []) if isinstance(data, dict) else data
        except Exception: pass
    return []

def _load_templates():
    return _load_json(_templates_path())

def _load_deliveries():
    return _load_json(_deliveries_path())

def _save_progetti(projects: list):
    path = _progetti_path()
    if not path: return
    try:
        data = {"projects": projects, "ultimo_aggiornamento": datetime.now().isoformat()}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Errore salvataggio progetti: {e}")

def _save_templates(templates: list):
    path = _templates_path()
    if not path: return
    try:
        path.write_text(json.dumps(templates, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Errore salvataggio template: {e}")

def _save_deliveries(deliveries: list):
    path = _deliveries_path()
    if not path: return
    try:
        path.write_text(json.dumps(deliveries, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Errore salvataggio consegne: {e}")

# ── Utils ──────────────────────────────────────────────────────────────────────

def uid():
    import random, string
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))

def now_str():
    return datetime.now().strftime("%d/%m/%Y %H:%M")

def get_progress(project: dict) -> int:
    tasks = [t for s in project.get("steps", []) for t in s.get("tasks", [])]
    if not tasks: return 0
    return round(sum(1 for t in tasks if t.get("done")) / len(tasks) * 100)

def get_next_task(project: dict):
    for step in project.get("steps", []):
        for task in step.get("tasks", []):
            if not task.get("done"):
                return step, task
    return None, None

def get_mpf_list(project: dict) -> list:
    mpf = []
    for step in project.get("steps", []):
        for task in step.get("tasks", []):
            if task.get("text", "").strip().lower() == "fresatura":
                for pgm in task.get("programs", []):
                    if pgm.get("tipoGruppo") != "ipm":
                        mpf.append(pgm)
    return mpf

def days_until(date_str: str):
    if not date_str: return None
    try:
        today = date.today()
        target = date.fromisoformat(date_str)
        return (target - today).days
    except Exception:
        return None

def delivery_urgency(days):
    if days is None:    return ("Nessuna data", "#9A978E", "#F0EEE8", "⚪")
    if days < 0:        return ("SCADUTA",       "#FFFFFF", "#C0392B", "💀")
    if days == 0:       return ("OGGI",           "#FFFFFF", "#C0392B", "🚨")
    if days <= 3:       return (f"{days}gg",      "#C0392B", "#FDECEA", "🔴")
    if days <= 7:       return (f"{days}gg",      "#C2720A", "#FFF0DC", "🟠")
    if days <= 21:      return (f"{days}gg",      "#D4700A", "#FFF4E8", "🟡")
    return              (f"{days}gg",             "#1A7A4A", "#E8F5EE", "🟢")

def clone_template_to_steps(tmpl: dict) -> list:
    return [
        {"id": uid(), "title": s["title"],
         "tasks": [{"id": uid(), "text": t["text"], "done": False,
                    "notes": [], "note": "", "doneAt": None}
                   for t in s.get("tasks", [])]}
        for s in tmpl.get("steps", [])
    ]

# ── Colori tema ────────────────────────────────────────────────────────────────
TC = {
    "bg":      "#F5F4F0", "surface": "#FFFFFF", "surface2": "#F0EEE8",
    "border":  "#D8D5CC", "borderStrong": "#B0ADA4",
    "text":    "#1A1814", "sub":     "#5A5750",  "muted":   "#9A978E",
    "accent":  "#D4700A", "accentBg": "#FFF4E8",
    "green":   "#1A7A4A", "greenBg": "#E8F5EE",
    "red":     "#C0392B", "redBg":   "#FDECEA",
    "blue":    "#1D5FAD", "blueBg":  "#EAF1FB",
}

COLORS_LIST = ["#D4700A","#1A7A4A","#1D5FAD","#C0392B","#8B2FC9","#C2185B","#0097A7","#E65100"]
ICONS_LIST  = ["🌐","📱","📣","🏗️","📦","🎯","🔧","📊","✍️","🚀","💡","🎨"]

STATO_NEXT = {"da_fare":"in_macchina","in_macchina":"completato","completato":"da_fare"}
STATO_CFG  = {
    "da_fare":     ("○ Da fare",     "#9A978E","#F0EEE8"),
    "in_macchina": ("⚙ In macchina","#1D5FAD","#EAF1FB"),
    "completato":  ("✓ Completato",  "#1A7A4A","#E8F5EE"),
}

PRIORITY_CFG = {
    "alta":  ("Alta",  "#C0392B","#FDECEA","🔴"),
    "media": ("Media", "#D4700A","#FFF4E8","🟡"),
    "bassa": ("Bassa", "#1A7A4A","#E8F5EE","🟢"),
}

# ══════════════════════════════════════════════════════════════════════════════
class TabProgetti:
    """Tab Progetti — WorkTrack porting completo."""

    def __init__(self, parent, main_window):
        self.parent      = parent
        self.main        = main_window
        self._projects   = []
        self._templates  = []
        self._deliveries = []
        self._page       = "projects"   # projects | archived | templates | deliveries | backup
        self._selected_id = None
        self._editing_template = None
        self._active_detail_tab = "tasks"
        self._quick_tasks = []
        self._sidebar_collapsed = False
        self._create_ui()
        self._load()

    # ══════════════════════════════════════════════════════════════════════════
    # UI principale
    # ══════════════════════════════════════════════════════════════════════════

    def _create_ui(self):
        # Layout orizzontale: contenuto + quick tasks sidebar
        self._outer = ctk.CTkFrame(self.parent, fg_color=TC["bg"], corner_radius=0)
        self._outer.pack(fill="both", expand=True)

        self._content_area = ctk.CTkFrame(self._outer, fg_color=TC["bg"], corner_radius=0)
        self._content_area.pack(side="left", fill="both", expand=True)

        self._sidebar_frame = tk.Frame(self._outer, bg=TC["surface"],
                                        highlightbackground=TC["border"], highlightthickness=1)
        self._sidebar_frame.pack(side="right", fill="y")
        self._render_quick_sidebar()

        # Top bar
        self._topbar = tk.Frame(self._content_area, bg=TC["surface"], height=48)
        self._topbar.pack(fill="x")
        self._topbar.pack_propagate(False)
        self._build_topbar()

        tk.Frame(self._content_area, height=1, bg=TC["border"]).pack(fill="x")

        # Body
        self._body = ctk.CTkScrollableFrame(self._content_area, fg_color=TC["bg"], corner_radius=0)
        self._body.pack(fill="both", expand=True)

    def _build_topbar(self):
        for w in self._topbar.winfo_children():
            w.destroy()

        # Logo
        tk.Label(self._topbar, text="◈ WorkTrack",
                 font=("DM Sans",14,"bold"), fg=TC["text"], bg=TC["surface"]).pack(side="left", padx=12, pady=10)
        tk.Frame(self._topbar, width=1, bg=TC["border"]).pack(side="left", fill="y", pady=6)

        # Nav
        self._nav_btns = {}
        nav_items = [("projects","Progetti"),("archived","Archivio"),
                     ("templates","Template"),("deliveries","Consegne"),("backup","Backup")]
        for nav_id, label in nav_items:
            is_active = self._page == nav_id and not self._selected_id and not self._editing_template
            btn = tk.Label(self._topbar, text=label,
                           font=("DM Sans",11,"bold"),
                           fg=TC["accent"] if is_active else TC["sub"],
                           bg=TC["surface"], cursor="hand2", padx=12)
            btn.pack(side="left")
            btn.bind("<Button-1>", lambda e, nid=nav_id: self._set_page(nid))
            self._nav_btns[nav_id] = btn

        # Destra
        right = tk.Frame(self._topbar, bg=TC["surface"])
        right.pack(side="right", padx=8)

        self._btn_nuovo = ctk.CTkButton(right, text="+ Nuovo Progetto",
            command=self._nuovo_progetto, fg_color=TC["accent"], hover_color="#B5600A",
            font=("DM Sans",11,"bold"), height=30, corner_radius=6)
        self._btn_nuovo.pack(side="right", padx=4, pady=8)

        self._entry_search = ctk.CTkEntry(right, width=170, height=30,
            placeholder_text="Cerca...", corner_radius=6)
        self._entry_search.pack(side="right", padx=4, pady=8)
        self._entry_search.bind("<KeyRelease>", lambda e: self._refresh())

    def _set_page(self, page):
        self._page = page
        self._selected_id = None
        self._editing_template = None
        self._active_detail_tab = "tasks"
        self._build_topbar()
        self._refresh()

    def _clear_body(self):
        for w in self._body.winfo_children():
            w.destroy()

    # ══════════════════════════════════════════════════════════════════════════
    # Caricamento
    # ══════════════════════════════════════════════════════════════════════════

    def _load(self):
        def _worker():
            p = _load_progetti()
            t = _load_templates()
            d = _load_deliveries()
            self.parent.after(0, lambda: self._set_data(p, t, d))
        threading.Thread(target=_worker, daemon=True).start()

    def _set_data(self, projects, templates, deliveries):
        self._projects   = projects
        self._templates  = templates
        self._deliveries = deliveries
        self._refresh()

    def _save_all(self):
        threading.Thread(target=lambda: (
            _save_progetti(self._projects),
            _save_templates(self._templates),
            _save_deliveries(self._deliveries)
        ), daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # Render dispatcher
    # ══════════════════════════════════════════════════════════════════════════

    def _refresh(self):
        self._clear_body()
        if self._editing_template:
            self._render_template_editor(self._editing_template)
        elif self._selected_id:
            p = next((x for x in self._projects if x.get("id") == self._selected_id), None)
            if p:
                self._render_detail(p)
            else:
                self._selected_id = None
                self._render_lista()
        elif self._page == "archived":
            self._render_lista(archived=True)
        elif self._page == "templates":
            self._render_templates()
        elif self._page == "deliveries":
            self._render_deliveries()
        elif self._page == "backup":
            self._render_backup()
        else:
            self._render_lista()

    # ══════════════════════════════════════════════════════════════════════════
    # Lista progetti
    # ══════════════════════════════════════════════════════════════════════════

    def _render_lista(self, archived=False):
        q = (self._entry_search.get() if hasattr(self, '_entry_search') else "").strip().lower()
        projects = [p for p in self._projects
                    if p.get("archived", False) == archived
                    and (q == "" or q in p.get("name","").lower())]

        # Ordina per urgenza scadenza
        def sort_key(p):
            d = self._get_delivery(p.get("id",""))
            if d and d.get("dueDate") and not d.get("delivered"):
                days = days_until(d["dueDate"])
                return days if days is not None else 9999
            return 9999
        projects = sorted(projects, key=sort_key)

        in_progress = [p for p in projects if get_progress(p) < 100]
        completed   = [p for p in projects if get_progress(p) == 100]

        # Banner urgenza
        urgent = [p for p in in_progress if self._is_urgent(p)]
        if urgent:
            ub = tk.Frame(self._body, bg="#FDECEA",
                          highlightbackground="#C0392B", highlightthickness=1)
            ub.pack(fill="x", padx=20, pady=(12,0))
            tk.Label(ub, text=f"🎯 FOCUS — {len(urgent)} CONSEGN{'A' if len(urgent)==1 else 'E'} ENTRO 7 GIORNI",
                     font=("DM Sans",10,"bold"), fg="#C0392B", bg="#FDECEA").pack(side="left", padx=10, pady=6)
            names = " · ".join(p.get("name","?") for p in urgent[:4])
            tk.Label(ub, text=names, font=("DM Sans",10), fg="#5A5750", bg="#FDECEA").pack(side="left", padx=4)

        if not projects:
            txt = "Nessun progetto. Clicca '+ Nuovo Progetto' per iniziare." if not archived else "Nessun progetto archiviato."
            ctk.CTkLabel(self._body, text=txt,
                         font=("DM Sans",13), text_color=TC["muted"]).pack(pady=60)
            return

        for section_label, section_projects in [
            ("IN CORSO" if not archived else "ARCHIVIO", in_progress if not archived else projects),
            ("COMPLETATI", completed if not archived else []),
        ]:
            if not section_projects: continue

            hdr = tk.Frame(self._body, bg=TC["bg"])
            hdr.pack(fill="x", padx=20, pady=(16,4))
            tk.Label(hdr, text=f"{section_label} — {len(section_projects)}",
                     font=("DM Sans",10,"bold"), fg=TC["muted"], bg=TC["bg"]).pack(side="left")

            grid = tk.Frame(self._body, bg=TC["bg"])
            grid.pack(fill="x", padx=16, pady=0)
            grid.columnconfigure(0, weight=1)
            grid.columnconfigure(1, weight=1)

            for i, p in enumerate(section_projects):
                row, col = divmod(i, 2)
                self._project_card(grid, p, row, col)

    def _is_urgent(self, project):
        d = self._get_delivery(project.get("id",""))
        if d and d.get("dueDate") and not d.get("delivered"):
            days = days_until(d["dueDate"])
            return days is not None and days <= 7
        return False

    def _get_delivery(self, project_id):
        return next((d for d in self._deliveries if d.get("projectId") == project_id), None)

    def _project_card(self, parent, project, row, col):
        pct   = get_progress(project)
        color = project.get("color", TC["accent"])
        s_next, t_next = get_next_task(project)
        mpf   = get_mpf_list(project)
        delivery = self._get_delivery(project.get("id",""))

        # Urgenza bordo
        border_color = color
        if delivery and delivery.get("dueDate") and not delivery.get("delivered"):
            days = days_until(delivery["dueDate"])
            label, urg_color, urg_bg, urg_dot = delivery_urgency(days)
            if days is not None and days <= 7:
                border_color = urg_color

        card = tk.Frame(parent, bg=TC["surface"], cursor="hand2",
                        highlightbackground=border_color, highlightthickness=2)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

        # Bordo sinistro colorato
        lbar = tk.Frame(card, width=4, bg=border_color)
        lbar.pack(side="left", fill="y")

        body = tk.Frame(card, bg=TC["surface"])
        body.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        # Nome + badge pallet
        row1 = tk.Frame(body, bg=TC["surface"])
        row1.pack(fill="x", pady=(0,2))
        tk.Label(row1, text="●", fg=color, bg=TC["surface"], font=("Arial",9)).pack(side="left")
        tk.Label(row1, text=project.get("name","?"),
                 font=("DM Sans",12,"bold"), fg=TC["text"], bg=TC["surface"]).pack(side="left", padx=4)
        if project.get("pallet_assegnato"):
            tk.Label(row1, text=f"P{project['pallet_assegnato']}",
                     font=("DM Sans",10,"bold"), fg=color, bg=TC["surface"]).pack(side="left")

        if project.get("description"):
            tk.Label(body, text=project["description"],
                     font=("DM Sans",10), fg=TC["sub"], bg=TC["surface"]).pack(anchor="w")

        # Scadenza badge
        if delivery and delivery.get("dueDate"):
            days = days_until(delivery["dueDate"])
            label, urg_color, urg_bg, urg_dot = delivery_urgency(days)
            if delivery.get("delivered"):
                badge_text = f"✓ Consegnato"
                badge_fg, badge_bg = TC["green"], TC["greenBg"]
            else:
                badge_text = f"{urg_dot} {label}"
                badge_fg, badge_bg = urg_color, urg_bg
            tk.Label(body, text=badge_text,
                     font=("DM Sans",10,"bold"), fg=badge_fg, bg=badge_bg,
                     padx=6, pady=1).pack(anchor="w", pady=(2,0))

        # Barra progresso
        bar_bg = tk.Frame(body, height=4, bg=TC["surface2"])
        bar_bg.pack(fill="x", pady=(4,4))
        bar_bg.update_idletasks()
        w = bar_bg.winfo_width() or 200
        tk.Frame(bar_bg, width=max(1, int(w*pct/100)), height=4,
                 bg=TC["green"] if pct==100 else color).pack(side="left")

        # Stats
        stats = tk.Frame(body, bg=TC["surface"])
        stats.pack(fill="x")
        tasks_all  = [t for s in project.get("steps",[]) for t in s.get("tasks",[])]
        tasks_done = sum(1 for t in tasks_all if t.get("done"))
        tk.Label(stats, text=f"{tasks_done}/{len(tasks_all)} task",
                 font=("DM Sans",10), fg=TC["sub"], bg=TC["surface"]).pack(side="left")
        if mpf:
            mpf_done = sum(1 for p in mpf if p.get("stato")=="completato")
            tk.Label(stats, text=f"  ⚙ {mpf_done}/{len(mpf)} MPF",
                     font=("DM Sans",10,"bold"), fg=TC["blue"], bg=TC["surface"]).pack(side="left")

        status_color = TC["green"] if pct==100 else (TC["accent"] if pct>0 else TC["muted"])
        tk.Label(stats, text=("✓ Completato" if pct==100 else f"{pct}%"),
                 font=("DM Sans",10,"bold"), fg=status_color, bg=TC["surface"]).pack(side="right")

        # Prossimo step
        if t_next:
            nf = tk.Frame(body, bg="#FFF4E8")
            nf.pack(fill="x", pady=(4,0))
            tk.Label(nf, text="📍", bg="#FFF4E8", font=("Arial",10)).pack(side="left", padx=(4,2))
            tk.Label(nf, text=f"{s_next.get('title','?')} › {t_next.get('text','?')}",
                     font=("DM Sans",11), fg=TC["text"], bg="#FFF4E8").pack(side="left")

        # Click
        for w in [card, body, row1, stats]:
            w.bind("<Button-1>", lambda e, pid=project["id"]: self._open_project(pid))

    def _open_project(self, pid):
        self._selected_id = pid
        self._active_detail_tab = "tasks"
        self._build_topbar()
        self._refresh()

    # ══════════════════════════════════════════════════════════════════════════
    # Dettaglio progetto
    # ══════════════════════════════════════════════════════════════════════════

    def _get_tools_db(self) -> dict:
        """
        Carica tools_machine.json.
        Ritorna dict {t_num_str: tool_dict} — conserva tutti i gemelli.
        _classify_tool scansiona per nome e trova tutti i gemelli.
        """
        try:
            from pathlib import Path as _P
            cfg = _carica_config()
            folder = (cfg.get("tools_toa_folder") or "").strip()
            if not folder:
                return {}
            tm = _P(folder) / "tools_machine.json"
            if not tm.exists():
                return {}
            import json as _j
            raw = _j.loads(tm.read_text(encoding="utf-8"))
            # Indicizza per t_num (chiave unica) così i gemelli sono tutti presenti
            return {str(k): t for k, t in raw.get("tools", {}).items() if t.get("name")}
        except Exception:
            return {}


    def _classify_tool(self, alias: str, tools_db: dict) -> str | None:
        """Ritorna: ok | fin_vita | disabilitato | mancante | None (no alias/db)."""
        if not alias or not tools_db:
            return None
        t = tools_db.get(alias.upper().strip())
        if not t:
            return "mancante"
        if t.get("is_worn") or not t.get("is_enabled", True):
            return "disabilitato"
        lp = t.get("life_percent")
        if lp is not None and lp < 15:
            return "fin_vita"
        return "ok"

    def _render_detail(self, project):
        pct   = get_progress(project)
        color = project.get("color", TC["accent"])
        s_next, t_next = get_next_task(project)
        mpf   = get_mpf_list(project)

        # Header
        hdr = tk.Frame(self._body, bg=TC["surface"])
        hdr.pack(fill="x")

        # Row 1
        r1 = tk.Frame(hdr, bg=TC["surface"])
        r1.pack(fill="x", padx=20, pady=(12,4))

        tk.Button(r1, text="← Indietro", command=self._back,
                  font=("DM Sans",10), fg=TC["sub"], bg=TC["surface2"],
                  relief="flat", padx=10, pady=4, cursor="hand2").pack(side="left")

        nome_lbl = tk.Label(r1, text=f"● {project.get('name','?')}",
                 font=("DM Sans",16,"bold"), fg=TC["text"], bg=TC["surface"])
        nome_lbl.pack(side="left", padx=(8,2))

        def _rinomina():
            nuovo_nome = tk.simpledialog.askstring(
                "Rinomina progetto",
                f"Nuovo nome per '{project.get('name','')}':",
                initialvalue=project.get("name",""),
                parent=self.parent
            )
            if nuovo_nome and nuovo_nome.strip() and nuovo_nome.strip() != project.get("name"):
                project["name"] = nuovo_nome.strip()
                self._save_project(project)

        tk.Button(r1, text="✏️", command=_rinomina,
                  font=("DM Sans",10), fg=TC["muted"], bg=TC["surface"],
                  relief="flat", cursor="hand2").pack(side="left")

        # Pallet
        tk.Label(r1, text="Pallet:", font=("DM Sans",10), fg=TC["muted"], bg=TC["surface"]).pack(side="left", padx=(16,3))
        pallet_var = tk.StringVar(value=str(project.get("pallet_assegnato","—")))
        ttk.Combobox(r1, textvariable=pallet_var, values=["—","1","2","3","4","5","6"],
                     width=4, state="readonly").pack(side="left")
        pallet_var.trace_add("write", lambda *a: self._set_pallet(project, pallet_var.get()))

        # Lancia NC
        if mpf:
            tk.Button(r1, text=f"📄 Lancia in NC →",
                      command=lambda: self._apri_modal_lancio(project),
                      font=("DM Sans",10,"bold"), fg="#fff", bg=TC["blue"],
                      relief="flat", padx=10, pady=4, cursor="hand2").pack(side="left", padx=8)

        # Salva come template
        tk.Button(r1, text="💾 Salva come Template",
                  command=lambda: self._salva_come_template(project),
                  font=("DM Sans",10), fg=TC["blue"], bg=TC["blueBg"],
                  relief="flat", padx=8, pady=4, cursor="hand2").pack(side="left", padx=4)

        # Archivia / Elimina
        tk.Button(r1, text="📦 Archivia" if not project.get("archived") else "📤 Riattiva",
                  command=lambda: self._archivia(project),
                  font=("DM Sans",10), fg=TC["sub"], bg=TC["surface2"],
                  relief="flat", padx=8, pady=4, cursor="hand2").pack(side="right", padx=3)
        tk.Button(r1, text="🗑 Elimina",
                  command=lambda: self._elimina_id(project["id"]),
                  font=("DM Sans",10), fg=TC["red"], bg=TC["redBg"],
                  relief="flat", padx=8, pady=4, cursor="hand2").pack(side="right", padx=3)

        # Progress bar
        r2 = tk.Frame(hdr, bg=TC["surface"])
        r2.pack(fill="x", padx=20, pady=(0,4))
        all_tasks = [t for s in project.get("steps",[]) for t in s.get("tasks",[])]
        done_tasks = sum(1 for t in all_tasks if t.get("done"))
        tk.Label(r2, text=f"Avanzamento  {pct}% — {done_tasks} di {len(all_tasks)} task completati",
                 font=("DM Sans",11), fg=color, bg=TC["surface"]).pack(side="left")

        bar_bg = tk.Frame(hdr, height=5, bg=TC["surface2"])
        bar_bg.pack(fill="x", padx=20, pady=(0,6))
        bar_bg.update_idletasks()
        bw = bar_bg.winfo_width() or 600
        tk.Frame(bar_bg, width=max(1,int(bw*pct/100)), height=5,
                 bg=TC["green"] if pct==100 else color).pack(side="left")

        # Prossimo step
        if t_next:
            nf = tk.Frame(hdr, bg="#FFF4E8")
            nf.pack(fill="x", padx=20, pady=(0,8))
            tk.Label(nf, text="📍 RIPRENDI DA QUI",
                     font=("DM Sans",9,"bold"), fg=TC["accent"], bg="#FFF4E8").pack(anchor="w", padx=10, pady=(5,0))
            tk.Label(nf, text=f"{s_next.get('title','?')} › {t_next.get('text','?')}",
                     font=("DM Sans",12), fg=TC["text"], bg="#FFF4E8").pack(anchor="w", padx=10, pady=(0,6))

        # Tab switcher
        tab_row = tk.Frame(hdr, bg=TC["surface"])
        tab_row.pack(fill="x", padx=20)
        for tab_id, label in [("tasks","Task"), ("log",f"Log ({len(project.get('log',[]))})")]:
            active = self._active_detail_tab == tab_id
            lbl = tk.Label(tab_row, text=label,
                           font=("DM Sans",12,"bold"),
                           fg=color if active else TC["sub"],
                           bg=TC["surface"], cursor="hand2", padx=0, pady=8)
            lbl.pack(side="left", padx=(0,20))
            lbl.bind("<Button-1>", lambda e, t=tab_id: self._switch_detail_tab(project, t))
            if active:
                bar = tk.Frame(tab_row, height=2, bg=color)
                bar.place(in_=lbl, relx=0, rely=1.0, anchor="sw", relwidth=1.0)

        tk.Frame(hdr, height=1, bg=TC["border"]).pack(fill="x")

        # Tab content
        content = ctk.CTkFrame(self._body, fg_color=TC["bg"], corner_radius=0)
        content.pack(fill="both", expand=True, padx=16, pady=12)

        if self._active_detail_tab == "tasks":
            self._tools_db_cache = self._get_tools_db()
            self._render_tasks(content, project)
        else:
            self._render_log(content, project)

    def _back(self):
        self._selected_id = None
        self._active_detail_tab = "tasks"
        self._build_topbar()
        self._refresh()

    def _switch_detail_tab(self, project, tab):
        self._active_detail_tab = tab
        self._refresh()

    # ── Tasks ──────────────────────────────────────────────────────────────────

    def _render_tasks(self, parent, project):
        info_lbl = tk.Label(parent, text="Trascina ⣿ per riordinare · click checkbox per completare",
                            font=("DM Sans",9), fg=TC["muted"], bg=TC["bg"])
        info_lbl.pack(anchor="w", pady=(0,6))

        for step in project.get("steps", []):
            self._render_step(parent, project, step)

        # Aggiungi fase
        add_row = tk.Frame(parent, bg=TC["bg"])
        add_row.pack(fill="x", pady=4)
        entry = ctk.CTkEntry(add_row, width=280, height=30,
                             placeholder_text="Nome nuova fase... (Invio)", corner_radius=6)
        entry.pack(side="left")
        def _add_step(e=None):
            name = entry.get().strip()
            if not name: return
            project.setdefault("steps", []).append({"id":uid(),"title":name,"tasks":[]})
            self._save_project(project)
        entry.bind("<Return>", _add_step)
        ctk.CTkButton(add_row, text="+ Fase", command=_add_step,
                      fg_color=TC["accent"], hover_color="#B5600A",
                      font=("DM Sans",10,"bold"), height=30, width=70, corner_radius=6).pack(side="left", padx=5)

    def _render_step(self, parent, project, step):
        color = project.get("color", TC["accent"])
        done  = sum(1 for t in step.get("tasks",[]) if t.get("done"))
        total = len(step.get("tasks",[]))

        sf = tk.Frame(parent, bg=TC["surface"],
                      highlightbackground=color, highlightthickness=0)
        sf.pack(fill="x", pady=(0,8))

        lbar = tk.Frame(sf, width=4, bg=color)
        lbar.pack(side="left", fill="y")

        sc = tk.Frame(sf, bg=TC["surface"])
        sc.pack(side="left", fill="both", expand=True, padx=10, pady=8)

        # Header step
        sh = tk.Frame(sc, bg=TC["surface"])
        sh.pack(fill="x", pady=(0,6))
        tk.Label(sh, text=step.get("title",""), font=("DM Sans",12,"bold"),
                 fg=TC["text"], bg=TC["surface"]).pack(side="left")
        tk.Label(sh, text=f"  {done}/{total}",
                 font=("DM Sans",10), fg=TC["muted"], bg=TC["surface"]).pack(side="left")
        tk.Button(sh, text="🗑", command=lambda s=step: self._delete_step(project, s["id"]),
                  font=("DM Sans",9), fg=TC["red"], bg=TC["surface"],
                  relief="flat", cursor="hand2").pack(side="right")

        # Tasks
        for task in step.get("tasks", []):
            self._render_task(sc, project, step, task)

        # Aggiungi task
        ar = tk.Frame(sc, bg=TC["surface"])
        ar.pack(fill="x", pady=(3,0))
        te = ctk.CTkEntry(ar, width=300, height=26,
                          placeholder_text="Aggiungi task... (Invio)", corner_radius=6)
        te.pack(side="left")
        def _add_task(e=None, s=step):
            text = te.get().strip()
            if not text: return
            s["tasks"].append({"id":uid(),"text":text,"done":False,"notes":[],"note":"","doneAt":None})
            self._save_project(project)
        te.bind("<Return>", _add_task)
        tk.Button(ar, text="+ Task", command=_add_task,
                  font=("DM Sans",9), fg=TC["blue"], bg=TC["surface"],
                  relief="flat", cursor="hand2").pack(side="left", padx=5)

    def _render_task(self, parent, project, step, task):
        s_next, t_next = get_next_task(project)
        is_next = t_next is not None and t_next.get("id") == task.get("id")
        bg = "#FFF4E8" if is_next else TC["surface"]

        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", pady=1)

        if is_next:
            tk.Label(row, text="📍", bg=bg, font=("Arial",10)).pack(side="left")

        # Checkbox
        check_var = tk.BooleanVar(value=task.get("done", False))
        def _toggle(t=task, p=project):
            t["done"] = not t.get("done", False)
            t["doneAt"] = datetime.now().isoformat()[:10] if t["done"] else None
            self._save_project(p)
        tk.Checkbutton(row, variable=check_var, command=_toggle,
                       bg=bg, activebackground=bg, cursor="hand2",
                       relief="flat", borderwidth=0).pack(side="left")

        # Testo
        fg_col = TC["muted"] if task.get("done") else TC["text"]
        prefix = "✓ " if task.get("done") else ""
        tk.Label(row, text=prefix + task.get("text",""),
                 font=("DM Sans",11), fg=fg_col, bg=bg).pack(side="left", padx=3)

        if task.get("done") and task.get("doneAt"):
            tk.Label(row, text=task["doneAt"][:10],
                     font=("DM Sans",9), fg=TC["muted"], bg=bg).pack(side="left", padx=3)

        # Elimina
        tk.Button(row, text="✕",
                  command=lambda t=task, s=step: self._delete_task(project, s["id"], t["id"]),
                  font=("DM Sans",9), fg=TC["muted"], bg=bg,
                  relief="flat", cursor="hand2").pack(side="right", padx=3)

        # Note
        notes = task.get("notes", [])
        if not notes and task.get("note"):
            notes = [{"id": f"legacy_{task['id']}", "text": task["note"], "createdAt": ""}]
        for note in notes:
            nrow = tk.Frame(parent, bg="#FFF4E8")
            nrow.pack(fill="x", padx=(28,0), pady=1)
            tk.Label(nrow, text=f"💬 {note['text']}",
                     font=("DM Sans",9,"italic"), fg=TC["accent"], bg="#FFF4E8").pack(side="left", padx=6)

        # FresaturaPanel
        if task.get("text","").strip().lower() == "fresatura":
            self._render_fresatura(parent, project, task)

    def _render_fresatura(self, parent, project, task):
        programs = task.get("programs", [])
        ipm_pgm  = [p for p in programs if p.get("tipoGruppo") == "ipm"]
        fres_pgm = [p for p in programs if p.get("tipoGruppo") != "ipm"]
        done_tot = sum(1 for p in programs if p.get("stato") == "completato")
        in_mac   = sum(1 for p in programs if p.get("stato") == "in_macchina")

        pf = tk.Frame(parent, bg="#EAF1FB",
                      highlightbackground="#1D5FAD", highlightthickness=1)
        pf.pack(fill="x", padx=(28,0), pady=(3,6))

        # ── Header principale ─────────────────────────────────────────────────
        ph = tk.Frame(pf, bg="#EAF1FB")
        ph.pack(fill="x", padx=8, pady=5)
        tk.Label(ph, text="⚙️ PROGRAMMI FRESATURA",
                 font=("DM Sans",9,"bold"), fg=TC["blue"], bg="#EAF1FB").pack(side="left")
        if in_mac > 0:
            tk.Label(ph, text=f"⚙ {in_mac} in macchina",
                     font=("DM Sans",9,"bold"), fg=TC["blue"], bg="#EAF1FB").pack(side="left", padx=6)
        if programs:
            ck = TC["green"] if done_tot == len(programs) else TC["blue"]
            tk.Label(ph, text=f"{done_tot}/{len(programs)} completati",
                     font=("DM Sans",9,"bold"), fg=ck, bg="#EAF1FB").pack(side="left")

        # Badge anomalie (solo fresatura)
        tools_db = getattr(self, "_tools_db_cache", {})
        anomalie = [p for p in fres_pgm
                    if p.get("stato")=="in_macchina" and p.get("utensile")
                    and self._classify_tool(p.get("utensile",""), tools_db) in ("mancante","fin_vita","disabilitato")]
        if anomalie:
            tk.Label(ph, text=f"⚠ {len(anomalie)} utensili problematici",
                     font=("DM Sans",9,"bold"), fg="#DC2626", bg="#FEE2E2",
                     padx=6, pady=1).pack(side="left", padx=6)

        def _carica():
            files = fd.askopenfilenames(title="Carica file MPF",
                                         filetypes=[("MPF","*.MPF *.mpf"),("Tutti","*.*")])
            for fpath in files:
                fn = os.path.basename(fpath)
                if not any(p.get("filename")==fn for p in programs):
                    # Determina tipo automaticamente (IPM se contiene _IPM_)
                    is_ipm = "_IPM_" in fn.upper()
                    tokens = fn.replace(".MPF","").replace(".mpf","").split("_")
                    ipm_idx = next((i for i,t in enumerate(tokens) if t.upper()=="IPM"), -1)
                    num_pgm = tokens[ipm_idx+1] if ipm_idx >= 0 and ipm_idx+1 < len(tokens) else tokens[-1]
                    programs.append({
                        "id":uid(),"filename":fn,
                        "numPgm":num_pgm,
                        "tipoGruppo":"ipm" if is_ipm else "fresatura",
                        "utensile":"","diametro":"","tipoOp":"","dataPost":"",
                        "stato":"da_fare","operatore":"","tempoStimato":"",
                        "tempoInizio":None,"tempoFine":None,
                    })
            task["programs"] = programs
            self._save_project(project)

        tk.Button(ph, text="📂 Carica .MPF", command=_carica,
                  font=("DM Sans",9,"bold"), fg="#fff", bg=TC["blue"],
                  relief="flat", padx=6, pady=2, cursor="hand2").pack(side="right")

        # ── Sezione TASTATURA IPM (viola) ─────────────────────────────────────
        if ipm_pgm:
            ipm_header = tk.Frame(pf, bg="#F3E8FF")
            ipm_header.pack(fill="x")
            done_ipm = sum(1 for p in ipm_pgm if p.get("stato")=="completato")

            # Toggle collassa/espandi IPM
            ipm_collapsed = tk.BooleanVar(value=True)
            ipm_body = tk.Frame(pf, bg=pf.cget("bg"))

            def _toggle_ipm(b=ipm_body, v=ipm_collapsed):
                v.set(not v.get())
                if v.get():
                    b.pack_forget()
                    toggle_ipm_btn.configure(text="▼")
                else:
                    b.pack(fill="x")
                    toggle_ipm_btn.configure(text="▲")

            tk.Label(ipm_header, text="📏", font=("Arial",9),
                     bg="#F3E8FF").pack(side="left", padx=(6,2), pady=3)
            tk.Label(ipm_header, text="TASTATURA (IPM)",
                     font=("DM Sans",8,"bold"), fg="#6B21A8", bg="#F3E8FF").pack(side="left")
            tk.Label(ipm_header, text=f"{done_ipm}/{len(ipm_pgm)}",
                     font=("DM Sans",8), fg="#6B21A8", bg="#F3E8FF").pack(side="left", padx=4)
            toggle_ipm_btn = tk.Button(ipm_header, text="▼",
                     command=_toggle_ipm,
                     font=("DM Sans",8), fg="#6B21A8", bg="#F3E8FF",
                     relief="flat", cursor="hand2")
            toggle_ipm_btn.pack(side="right", padx=4)

            # IPM collassato di default — mostra solo se espanso
            for pgm in ipm_pgm:
                self._render_program_row(ipm_body, project, task, pgm, programs)

        # ── Sezione FRESATURA (blu) ────────────────────────────────────────────
        if fres_pgm and ipm_pgm:
            # Header separatore solo se ci sono entrambi i gruppi
            fres_header = tk.Frame(pf, bg="#E8F0FA")
            fres_header.pack(fill="x")
            done_fres = sum(1 for p in fres_pgm if p.get("stato")=="completato")

            fres_collapsed = tk.BooleanVar(value=False)
            fres_body = tk.Frame(pf, bg=pf.cget("bg"))
            fres_body.pack(fill="x")

            def _toggle_fres(b=fres_body, v=fres_collapsed):
                v.set(not v.get())
                if v.get():
                    b.pack_forget()
                    toggle_fres_btn.configure(text="▼")
                else:
                    b.pack(fill="x")
                    toggle_fres_btn.configure(text="▲")

            tk.Label(fres_header, text="⚙️", font=("Arial",9),
                     bg="#E8F0FA").pack(side="left", padx=(6,2), pady=3)
            tk.Label(fres_header, text="FRESATURA",
                     font=("DM Sans",8,"bold"), fg="#1D5FAD", bg="#E8F0FA").pack(side="left")
            tk.Label(fres_header, text=f"{done_fres}/{len(fres_pgm)}",
                     font=("DM Sans",8), fg="#1D5FAD", bg="#E8F0FA").pack(side="left", padx=4)
            toggle_fres_btn = tk.Button(fres_header, text="▲",
                     command=_toggle_fres,
                     font=("DM Sans",8), fg="#1D5FAD", bg="#E8F0FA",
                     relief="flat", cursor="hand2")
            toggle_fres_btn.pack(side="right", padx=4)

            for pgm in fres_pgm:
                self._render_program_row(fres_body, project, task, pgm, programs)

        elif fres_pgm:
            # Solo fresatura, nessun header separatore
            for pgm in fres_pgm:
                self._render_program_row(pf, project, task, pgm, programs)

    def _render_program_row(self, parent, project, task, pgm, programs):
        stato = pgm.get("stato","da_fare")
        lbl, fg, bg = STATO_CFG.get(stato, STATO_CFG["da_fare"])

        # Classifica utensile — solo se in_macchina
        tools_db = getattr(self, "_tools_db_cache", {})
        tool_status = None
        if stato == "in_macchina":
            tool_status = self._classify_tool(pgm.get("utensile",""), tools_db)

        # Colori riga in base allo stato utensile
        TOOL_BG = {
            "mancante":    "#FEE2E2",
            "fin_vita":    "#FEF9C3",
            "disabilitato":"#EDE9FE",
        }
        TOOL_FG = {
            "mancante":    "#DC2626",
            "fin_vita":    "#D97706",
            "disabilitato":"#7C3AED",
        }
        row_bg = TOOL_BG.get(tool_status, bg)

        row = tk.Frame(parent, bg=row_bg,
                       highlightbackground=TOOL_FG.get(tool_status, row_bg),
                       highlightthickness=2 if tool_status in TOOL_BG else 0)
        row.pack(fill="x", padx=4, pady=1)

        def _adv(p=pgm):
            p["stato"] = STATO_NEXT.get(p.get("stato","da_fare"), "da_fare")
            if p["stato"] == "in_macchina" and not p.get("tempoInizio"):
                p["tempoInizio"] = now_str()
            elif p["stato"] == "completato":
                p["tempoFine"] = now_str()
            task["programs"] = programs
            all_done = programs and all(x.get("stato")=="completato" for x in programs)
            task["done"] = all_done
            task["doneAt"] = datetime.now().isoformat()[:10] if all_done else None
            self._save_project(project)

        btn_bg = TOOL_BG.get(tool_status, bg)
        btn_fg = TOOL_FG.get(tool_status, fg)
        tk.Button(row, text=lbl, command=_adv,
                  font=("DM Sans",9,"bold"), fg=btn_fg, bg=btn_bg,
                  relief="flat", padx=6, pady=2, cursor="hand2", width=13).pack(side="left", padx=3)
        tk.Label(row, text=pgm.get("numPgm",""),
                 font=("Consolas",9,"bold"), fg=TC["blue"], bg=row_bg, width=5).pack(side="left")
        # Badge utensile con colore problema
        alias_txt = pgm.get("utensile","") or "—"
        badge_sfx = {"mancante":" ✗","fin_vita":" ⚠","disabilitato":" ⊘"}.get(tool_status,"")
        tk.Label(row, text=alias_txt+badge_sfx,
                 font=("Consolas",9,"bold" if tool_status else "normal"),
                 fg=TOOL_FG.get(tool_status, TC["text"]),
                 bg=row_bg, width=20, anchor="w").pack(side="left")
        op = (pgm.get("tipoOp","") or "").replace("- NESSUN TESTO","").strip()[:38]
        tk.Label(row, text=op or "—", font=("DM Sans",9), fg=TC["sub"], bg=row_bg).pack(side="left", padx=3)
        if pgm.get("tempoFine"):
            tk.Label(row, text=f"■{pgm['tempoFine']}", font=("Consolas",8), fg=TC["green"], bg=row_bg).pack(side="right", padx=3)
        elif pgm.get("tempoInizio"):
            tk.Label(row, text=f"▶{pgm['tempoInizio']}", font=("Consolas",8), fg=TC["blue"], bg=row_bg).pack(side="right", padx=3)

    # ── Log ────────────────────────────────────────────────────────────────────

    def _render_log(self, parent, project):
        log = project.get("log", [])
        color = project.get("color", TC["accent"])

        log_frame = ctk.CTkScrollableFrame(parent, fg_color=TC["bg"], height=280)
        log_frame.pack(fill="both", expand=True, pady=(0,8))

        if not log:
            ctk.CTkLabel(log_frame, text="Nessun aggiornamento ancora.",
                         font=("DM Sans",12), text_color=TC["muted"]).pack(pady=30)

        for entry in log:
            ef = tk.Frame(log_frame, bg=TC["surface"])
            ef.pack(fill="x", pady=2)
            tk.Frame(ef, width=3, bg=color).pack(side="left", fill="y")
            ec = tk.Frame(ef, bg=TC["surface"])
            ec.pack(side="left", fill="both", expand=True, padx=8, pady=6)

            # Header entry
            eh = tk.Frame(ec, bg=TC["surface"])
            eh.pack(fill="x")
            tk.Label(eh, text=entry.get("user","?"),
                     font=("DM Sans",10,"bold"), fg=color, bg=TC["surface"]).pack(side="left")
            tk.Label(eh, text=f"  {entry.get('time','')}",
                     font=("DM Sans",9), fg=TC["muted"], bg=TC["surface"]).pack(side="left")
            if entry.get("editedAt"):
                tk.Label(eh, text=f" · mod. {entry['editedAt']}",
                         font=("DM Sans",9,"italic"), fg=TC["muted"], bg=TC["surface"]).pack(side="left")

            # Azioni modifica/elimina
            def _edit_log(e=entry, p=project):
                new = tk.simpledialog.askstring("Modifica", "Testo:", initialvalue=e.get("text",""))
                if new and new.strip():
                    e["text"] = new.strip()
                    e["editedAt"] = now_str()
                    self._save_project(p)
            def _del_log(e=entry, p=project):
                if mb.askyesno("Elimina", "Eliminare questo aggiornamento?"):
                    p["log"] = [x for x in p.get("log",[]) if x.get("id") != e.get("id")]
                    self._save_project(p)

            tk.Button(eh, text="✏️", command=_edit_log,
                      font=("DM Sans",9), fg=TC["sub"], bg=TC["surface"],
                      relief="flat", cursor="hand2").pack(side="right")
            tk.Button(eh, text="🗑", command=_del_log,
                      font=("DM Sans",9), fg=TC["red"], bg=TC["surface"],
                      relief="flat", cursor="hand2").pack(side="right")

            tk.Label(ec, text=entry.get("text",""),
                     font=("DM Sans",11), fg=TC["text"], bg=TC["surface"],
                     wraplength=480, justify="left").pack(anchor="w", pady=(2,0))

        # Aggiungi entry
        add_frame = ctk.CTkFrame(parent, fg_color=TC["surface"], corner_radius=8)
        add_frame.pack(fill="x")
        user_e = ctk.CTkEntry(add_frame, width=80, height=32, placeholder_text="Tu", corner_radius=6)
        user_e.pack(side="left", padx=(8,4), pady=6)
        text_e = ctk.CTkEntry(add_frame, height=32, placeholder_text="Scrivi aggiornamento...", corner_radius=6)
        text_e.pack(side="left", fill="x", expand=True, padx=4, pady=6)

        def _add_log(e=None):
            text = text_e.get().strip()
            if not text: return
            project.setdefault("log",[]).append({
                "id":uid(),"user":user_e.get().strip() or "Tu",
                "text":text,"time":now_str()
            })
            self._save_project(project)
        text_e.bind("<Return>", _add_log)
        ctk.CTkButton(add_frame, text="→", command=_add_log,
                      fg_color=color, font=("DM Sans",12,"bold"),
                      height=32, width=38, corner_radius=6).pack(side="right", padx=6, pady=6)

    # ══════════════════════════════════════════════════════════════════════════
    # Templates
    # ══════════════════════════════════════════════════════════════════════════

    def _render_templates(self):
        hdr = tk.Frame(self._body, bg=TC["bg"])
        hdr.pack(fill="x", padx=20, pady=(14,8))
        tk.Label(hdr, text=f"TEMPLATE SALVATI — {len(self._templates)}",
                 font=("DM Sans",11,"bold"), fg=TC["sub"], bg=TC["bg"]).pack(side="left")
        ctk.CTkButton(hdr, text="+ Nuovo Template",
                      command=self._nuovo_template,
                      fg_color=TC["accent"], hover_color="#B5600A",
                      font=("DM Sans",10,"bold"), height=28, corner_radius=6).pack(side="right")

        if not self._templates:
            ctk.CTkLabel(self._body, text="Nessun template. Creane uno!",
                         font=("DM Sans",13), text_color=TC["muted"]).pack(pady=40)
            return

        grid = tk.Frame(self._body, bg=TC["bg"])
        grid.pack(fill="x", padx=16)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        for i, tmpl in enumerate(self._templates):
            row, col = divmod(i, 2)
            self._template_card(grid, tmpl, row, col)

    def _template_card(self, parent, tmpl, row, col):
        color = tmpl.get("color", TC["accent"])
        card = tk.Frame(parent, bg=TC["surface"],
                        highlightbackground=color, highlightthickness=2)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

        tbar = tk.Frame(card, bg=color, height=4)
        tbar.pack(fill="x")

        body = tk.Frame(card, bg=TC["surface"])
        body.pack(fill="both", expand=True, padx=12, pady=10)

        # Header
        hrow = tk.Frame(body, bg=TC["surface"])
        hrow.pack(fill="x", pady=(0,6))
        tk.Label(hrow, text=tmpl.get("icon","🚀"), font=("Arial",16), bg=TC["surface"]).pack(side="left")
        tk.Label(hrow, text=tmpl.get("name","?"),
                 font=("DM Sans",12,"bold"), fg=TC["text"], bg=TC["surface"]).pack(side="left", padx=6)

        if tmpl.get("description"):
            tk.Label(body, text=tmpl["description"],
                     font=("DM Sans",10), fg=TC["sub"], bg=TC["surface"]).pack(anchor="w")

        # Fasi preview
        pf = tk.Frame(body, bg=TC["surface2"])
        pf.pack(fill="x", pady=6)
        for j, step in enumerate(tmpl.get("steps",[])[:4]):
            tk.Label(pf, text=f"{j+1}. {step.get('title','')}  ({len(step.get('tasks',[]))} task)",
                     font=("DM Sans",10), fg=TC["text"], bg=TC["surface2"]).pack(anchor="w", padx=6, pady=1)

        total_t = sum(len(s.get("tasks",[])) for s in tmpl.get("steps",[]))
        tk.Label(body, text=f"{total_t} task totali · {len(tmpl.get('steps',[]))} fasi",
                 font=("DM Sans",9), fg=TC["muted"], bg=TC["surface"]).pack(anchor="w", pady=(0,6))

        # Azioni
        btn_row = tk.Frame(body, bg=TC["surface"])
        btn_row.pack(fill="x")
        tk.Button(btn_row, text="▶ Usa",
                  command=lambda t=tmpl: self._usa_template(t),
                  font=("DM Sans",10,"bold"), fg="#fff", bg=color,
                  relief="flat", padx=10, pady=4, cursor="hand2").pack(side="left")
        tk.Button(btn_row, text="⧉",
                  command=lambda t=tmpl: self._duplica_template(t),
                  font=("DM Sans",10), fg=TC["sub"], bg=TC["surface2"],
                  relief="flat", padx=6, pady=4, cursor="hand2").pack(side="left", padx=4)
        tk.Button(btn_row, text="✏️",
                  command=lambda t=tmpl: self._modifica_template(t),
                  font=("DM Sans",10), fg=TC["sub"], bg=TC["surface2"],
                  relief="flat", padx=6, pady=4, cursor="hand2").pack(side="left")
        tk.Button(btn_row, text="🗑️",
                  command=lambda t=tmpl: self._elimina_template(t["id"]),
                  font=("DM Sans",10), fg=TC["red"], bg=TC["redBg"],
                  relief="flat", padx=6, pady=4, cursor="hand2").pack(side="left", padx=4)

    def _render_template_editor(self, template):
        color = template.get("color", TC["accent"])

        # Header editor
        hdr = tk.Frame(self._body, bg=TC["surface"])
        hdr.pack(fill="x")
        hdr_inner = tk.Frame(hdr, bg=TC["surface"])
        hdr_inner.pack(fill="x", padx=20, pady=10)

        tk.Button(hdr_inner, text="← Annulla",
                  command=lambda: self._cancel_template_edit(),
                  font=("DM Sans",10), fg=TC["sub"], bg=TC["surface2"],
                  relief="flat", padx=10, pady=4, cursor="hand2").pack(side="left")
        tk.Label(hdr_inner, text="Nuovo Template" if template.get("id","").startswith("new_") else f"Modifica: {template.get('name','')}",
                 font=("DM Sans",14,"bold"), fg=TC["text"], bg=TC["surface"]).pack(side="left", padx=10)

        def _save():
            self._templates = [template if t["id"]==template["id"] else t for t in self._templates]
            if not any(t["id"]==template["id"] for t in self._templates):
                self._templates.append(template)
            _save_templates(self._templates)
            self._editing_template = None
            self._set_page("templates")

        ctk.CTkButton(hdr_inner, text="💾 Salva Template", command=_save,
                      fg_color=color, hover_color="#B5600A",
                      font=("DM Sans",11,"bold"), height=30, corner_radius=6).pack(side="right")

        tk.Frame(hdr, height=1, bg=TC["border"]).pack(fill="x")

        # Campi editor
        form = ctk.CTkScrollableFrame(self._body, fg_color=TC["bg"])
        form.pack(fill="both", expand=True, padx=16, pady=10)

        # Nome e descrizione
        fields = tk.Frame(form, bg=TC["bg"])
        fields.pack(fill="x", pady=(0,12))
        for label, key, w in [("NOME TEMPLATE","name",220),("DESCRIZIONE","description",280)]:
            f = tk.Frame(fields, bg=TC["bg"])
            f.pack(side="left", padx=(0,16))
            tk.Label(f, text=label, font=("DM Sans",9,"bold"), fg=TC["sub"], bg=TC["bg"]).pack(anchor="w")
            e = ctk.CTkEntry(f, width=w, height=30, corner_radius=6)
            e.insert(0, template.get(key,""))
            e.pack()
            def _update(event, k=key, entry=e):
                template[k] = entry.get()
            e.bind("<KeyRelease>", _update)

        # Colore
        tk.Label(form, text="COLORE", font=("DM Sans",9,"bold"), fg=TC["sub"], bg=TC["bg"]).pack(anchor="w")
        color_row = tk.Frame(form, bg=TC["bg"])
        color_row.pack(anchor="w", pady=(4,12))
        for c in COLORS_LIST:
            sel = c == template.get("color")
            btn = tk.Label(color_row, text="●", font=("Arial",18),
                           fg=c, bg=TC["bg"] if not sel else TC["surface2"],
                           cursor="hand2", padx=2)
            btn.pack(side="left")
            def _set_color(cc=c):
                template["color"] = cc
                self._refresh()
            btn.bind("<Button-1>", lambda e, cc=c: _set_color(cc))

        # Fasi
        tk.Label(form, text="FASI E TASK", font=("DM Sans",9,"bold"), fg=TC["sub"], bg=TC["bg"]).pack(anchor="w", pady=(0,6))

        for idx, step in enumerate(template.get("steps",[])):
            sf = tk.Frame(form, bg=TC["surface"],
                          highlightbackground=color, highlightthickness=1)
            sf.pack(fill="x", pady=(0,8))
            lbar = tk.Frame(sf, width=4, bg=color)
            lbar.pack(side="left", fill="y")
            sc = tk.Frame(sf, bg=TC["surface"])
            sc.pack(side="left", fill="both", expand=True, padx=8, pady=8)

            sh = tk.Frame(sc, bg=TC["surface"])
            sh.pack(fill="x", pady=(0,6))
            tk.Label(sh, text=f"FASE {idx+1}", font=("DM Sans",9,"bold"), fg=color, bg=TC["surface"]).pack(side="left")

            step_entry = ctk.CTkEntry(sh, height=26, corner_radius=6)
            step_entry.insert(0, step.get("title",""))
            step_entry.pack(side="left", fill="x", expand=True, padx=6)
            def _update_step(e, s=step, se=step_entry):
                s["title"] = se.get()
            step_entry.bind("<KeyRelease>", _update_step)

            # Up/Down
            move_col = tk.Frame(sh, bg=TC["surface"])
            move_col.pack(side="left")
            if idx > 0:
                tk.Button(move_col, text="▲",
                          command=lambda i=idx: self._move_template_step(template, i, -1),
                          font=("DM Sans",8), relief="flat", bg=TC["surface2"],
                          cursor="hand2", padx=3).pack()
            if idx < len(template.get("steps",[]))-1:
                tk.Button(move_col, text="▼",
                          command=lambda i=idx: self._move_template_step(template, i, 1),
                          font=("DM Sans",8), relief="flat", bg=TC["surface2"],
                          cursor="hand2", padx=3).pack()

            tk.Button(sh, text="✕", command=lambda s=step: self._remove_template_step(template, s["id"]),
                      font=("DM Sans",9), fg=TC["red"], bg=TC["surface"], relief="flat", cursor="hand2").pack(side="right")

            # Task del template
            for task in step.get("tasks",[]):
                tr = tk.Frame(sc, bg=TC["surface"])
                tr.pack(fill="x", pady=2)
                tk.Label(tr, text="◦", fg=color, bg=TC["surface"]).pack(side="left")
                te = ctk.CTkEntry(tr, height=24, corner_radius=6)
                te.insert(0, task.get("text",""))
                te.pack(side="left", fill="x", expand=True, padx=4)
                def _upd_task(e, t=task, entry=te):
                    t["text"] = entry.get()
                te.bind("<KeyRelease>", _upd_task)
                tk.Button(tr, text="✕",
                          command=lambda s=step, t=task: self._remove_template_task(template, s["id"], t["id"]),
                          font=("DM Sans",9), fg=TC["red"], bg=TC["surface"], relief="flat", cursor="hand2").pack(side="right")

            tk.Button(sc, text="+ Aggiungi task",
                      command=lambda s=step: self._add_template_task(template, s["id"]),
                      font=("DM Sans",9), fg=TC["muted"], bg=TC["surface"],
                      relief="flat", cursor="hand2").pack(anchor="w", pady=(3,0))

        # Aggiungi fase
        tk.Button(form, text="+ Aggiungi fase",
                  command=lambda: self._add_template_step(template),
                  font=("DM Sans",11), fg=color, bg=TC["bg"],
                  relief="flat", cursor="hand2", pady=8).pack(fill="x", pady=6)

    def _move_template_step(self, template, idx, direction):
        steps = template.get("steps", [])
        new_idx = idx + direction
        if 0 <= new_idx < len(steps):
            steps[idx], steps[new_idx] = steps[new_idx], steps[idx]
        self._refresh()

    def _add_template_step(self, template):
        template.setdefault("steps", []).append({"id": uid(), "title": "Nuova fase", "tasks": []})
        self._refresh()

    def _remove_template_step(self, template, step_id):
        template["steps"] = [s for s in template.get("steps",[]) if s["id"] != step_id]
        self._refresh()

    def _add_template_task(self, template, step_id):
        for s in template.get("steps",[]):
            if s["id"] == step_id:
                s["tasks"].append({"id": uid(), "text": "Nuovo task"})
        self._refresh()

    def _remove_template_task(self, template, step_id, task_id):
        for s in template.get("steps",[]):
            if s["id"] == step_id:
                s["tasks"] = [t for t in s.get("tasks",[]) if t["id"] != task_id]
        self._refresh()

    # ══════════════════════════════════════════════════════════════════════════
    # Consegne (Delivery)
    # ══════════════════════════════════════════════════════════════════════════

    def _render_deliveries(self):
        active_projects = [p for p in self._projects if not p.get("archived")]

        # Arricchisce consegne
        enriched = []
        for d in self._deliveries:
            proj = next((p for p in self._projects if p["id"]==d.get("projectId")), None)
            days = days_until(d.get("dueDate",""))
            label, urg_fg, urg_bg, urg_dot = delivery_urgency(days)
            progress = get_progress(proj) if proj else 0
            enriched.append({**d, "proj": proj, "days": days,
                              "urg_label": label, "urg_fg": urg_fg,
                              "urg_bg": urg_bg, "urg_dot": urg_dot, "progress": progress})

        enriched.sort(key=lambda d: (
            1 if d.get("delivered") else 0,
            d["days"] if d["days"] is not None else 9999
        ))

        pending   = [d for d in enriched if not d.get("delivered")]
        delivered = [d for d in enriched if d.get("delivered")]
        urgent    = [d for d in pending if d["days"] is not None and d["days"] <= 7]

        # Banner urgenza
        if urgent:
            ub = tk.Frame(self._body, bg="#FDECEA")
            ub.pack(fill="x", padx=20, pady=(14,4))
            tk.Label(ub, text=f"🎯 FOCUS DEL GIORNO — {len(urgent)} CONSEGN{'A' if len(urgent)==1 else 'E'} URGENTI",
                     font=("DM Sans",10,"bold"), fg="#C0392B", bg="#FDECEA").pack(anchor="w", padx=10, pady=6)

        # Header
        hdr = tk.Frame(self._body, bg=TC["bg"])
        hdr.pack(fill="x", padx=20, pady=(12,8))
        tk.Label(hdr, text=f"CONSEGNE — {len(pending)} IN ATTESA",
                 font=("DM Sans",11,"bold"), fg=TC["sub"], bg=TC["bg"]).pack(side="left")
        ctk.CTkButton(hdr, text="+ Nuova consegna",
                      command=lambda: self._nuovo_delivery(active_projects),
                      fg_color=TC["accent"], hover_color="#B5600A",
                      font=("DM Sans",10,"bold"), height=28, corner_radius=6).pack(side="right")

        if not pending:
            ctk.CTkLabel(self._body, text="📅  Nessuna consegna programmata",
                         font=("DM Sans",13), text_color=TC["muted"]).pack(pady=40)
        else:
            for d in pending:
                self._delivery_row(d)

        # Consegnate collassabili
        if delivered:
            show_delivered = tk.BooleanVar(value=False)
            def _toggle_delivered():
                show_delivered.set(not show_delivered.get())
                self._refresh()
            tk.Button(self._body,
                      text=f"▼ CONSEGNATE — {len(delivered)}" if not show_delivered.get() else f"▲ CONSEGNATE — {len(delivered)}",
                      command=_toggle_delivered,
                      font=("DM Sans",10,"bold"), fg=TC["sub"], bg=TC["bg"],
                      relief="flat", cursor="hand2").pack(anchor="w", padx=20, pady=(12,4))

    def _delivery_row(self, d):
        proj    = d.get("proj")
        color   = proj.get("color", TC["muted"]) if proj else TC["muted"]
        urg_bg  = d["urg_bg"]
        urg_fg  = d["urg_fg"]

        row = tk.Frame(self._body, bg=TC["surface"],
                       highlightbackground=urg_fg, highlightthickness=1)
        row.pack(fill="x", padx=20, pady=3)

        lbar = tk.Frame(row, width=4, bg=urg_fg)
        lbar.pack(side="left", fill="y")

        body = tk.Frame(row, bg=TC["surface"])
        body.pack(side="left", fill="both", expand=True, padx=10, pady=8)

        # Nome progetto
        nr = tk.Frame(body, bg=TC["surface"])
        nr.pack(fill="x")
        tk.Label(nr, text="●", fg=color, bg=TC["surface"], font=("Arial",9)).pack(side="left")
        tk.Label(nr, text=proj.get("name","Progetto eliminato") if proj else "Progetto eliminato",
                 font=("DM Sans",12,"bold"), fg=TC["text"] if proj else TC["muted"],
                 bg=TC["surface"]).pack(side="left", padx=4)

        if d.get("note"):
            tk.Label(nr, text=d["note"], font=("DM Sans",10), fg=TC["sub"], bg=TC["surface"]).pack(side="left", padx=4)

        # Badge urgenza
        if not d.get("delivered"):
            badge_text = f"{d['urg_dot']} {d['urg_label']}"
        else:
            badge_text = f"✓ Consegnato {d.get('deliveredAt','')}"
            urg_bg, urg_fg = TC["greenBg"], TC["green"]

        tk.Label(nr, text=badge_text,
                 font=("DM Sans",10,"bold"), fg=urg_fg, bg=urg_bg,
                 padx=6, pady=1).pack(side="right")

        # Data e azioni
        dr = tk.Frame(body, bg=TC["surface"])
        dr.pack(fill="x", pady=(4,0))
        if d.get("dueDate"):
            try:
                dt = datetime.fromisoformat(d["dueDate"])
                tk.Label(dr, text=dt.strftime("%d/%m/%Y"),
                         font=("DM Sans",10), fg=TC["muted"], bg=TC["surface"]).pack(side="left")
            except Exception:
                pass

        # Progress bar progetto
        if proj and not d.get("delivered"):
            pct = d["progress"]
            pb_bg = tk.Frame(dr, width=60, height=4, bg=TC["surface2"])
            pb_bg.pack(side="left", padx=8)
            pb_bg.update_idletasks()
            tk.Frame(pb_bg, width=max(1,int(60*pct/100)), height=4, bg=color).pack(side="left")
            tk.Label(dr, text=f"{pct}%", font=("DM Sans",9), fg=TC["sub"], bg=TC["surface"]).pack(side="left")

        # Toggle consegnato
        def _toggle(dd=d):
            dd["delivered"] = not dd.get("delivered", False)
            if dd["delivered"]:
                dd["deliveredAt"] = now_str()
            _save_deliveries(self._deliveries)
            self._refresh()

        tk.Button(dr, text="✓ Consegnato" if not d.get("delivered") else "↩ Riapri",
                  command=_toggle, font=("DM Sans",9,"bold"),
                  fg=TC["green"] if not d.get("delivered") else TC["sub"],
                  bg=TC["surface"], relief="flat", cursor="hand2").pack(side="right", padx=4)

        if proj:
            tk.Button(dr, text="Apri →",
                      command=lambda pid=proj["id"]: self._open_project(pid),
                      font=("DM Sans",9), fg=TC["blue"], bg=TC["surface"],
                      relief="flat", cursor="hand2").pack(side="right")

        tk.Button(dr, text="🗑",
                  command=lambda dd=d: self._elimina_delivery(dd.get("id","")),
                  font=("DM Sans",9), fg=TC["red"], bg=TC["surface"],
                  relief="flat", cursor="hand2").pack(side="right")

    def _nuovo_delivery(self, active_projects):
        win = tk.Toplevel(self.parent)
        win.title("Nuova consegna")
        win.geometry("420x280")
        win.grab_set()
        win.configure(bg=TC["bg"])

        tk.Label(win, text="PROGETTO", font=("DM Sans",10,"bold"), fg=TC["sub"], bg=TC["bg"]).pack(anchor="w", padx=20, pady=(14,2))
        proj_var = tk.StringVar()
        proj_names = [p.get("name","?") for p in active_projects]
        ttk.Combobox(win, textvariable=proj_var, values=proj_names, state="readonly", width=30).pack(anchor="w", padx=20)
        if proj_names: proj_var.set(proj_names[0])

        tk.Label(win, text="DATA DI CONSEGNA", font=("DM Sans",10,"bold"), fg=TC["sub"], bg=TC["bg"]).pack(anchor="w", padx=20, pady=(10,2))
        date_e = ctk.CTkEntry(win, width=200, height=30, placeholder_text="YYYY-MM-DD", corner_radius=6)
        date_e.pack(anchor="w", padx=20)

        tk.Label(win, text="NOTE (opzionale)", font=("DM Sans",10,"bold"), fg=TC["sub"], bg=TC["bg"]).pack(anchor="w", padx=20, pady=(10,2))
        note_e = ctk.CTkEntry(win, width=300, height=30, corner_radius=6)
        note_e.pack(anchor="w", padx=20)

        def _save():
            proj = next((p for p in active_projects if p.get("name")==proj_var.get()), None)
            if not proj or not date_e.get().strip(): return
            self._deliveries.append({
                "id": uid(), "projectId": proj["id"],
                "dueDate": date_e.get().strip(), "note": note_e.get().strip(),
                "delivered": False, "createdAt": now_str()
            })
            _save_deliveries(self._deliveries)
            win.destroy()
            self._refresh()

        ctk.CTkButton(win, text="Aggiungi", command=_save,
                      fg_color=TC["accent"], hover_color="#B5600A",
                      font=("DM Sans",11,"bold"), height=32, corner_radius=6).pack(pady=12)

    def _elimina_delivery(self, did):
        self._deliveries = [d for d in self._deliveries if d.get("id") != did]
        _save_deliveries(self._deliveries)
        self._refresh()

    # ══════════════════════════════════════════════════════════════════════════
    # Backup
    # ══════════════════════════════════════════════════════════════════════════

    def _render_backup(self):
        ctk.CTkLabel(self._body, text="🗄️ Backup & Importazione",
                     font=("DM Sans",18,"bold"), text_color=TC["text"]).pack(anchor="w", padx=24, pady=(18,4))
        ctk.CTkLabel(self._body, text="Importa backup da WorkTrack o esporta i dati correnti.",
                     font=("DM Sans",11), text_color=TC["muted"]).pack(anchor="w", padx=24, pady=(0,18))

        # Stato attuale
        state_f = ctk.CTkFrame(self._body, fg_color=TC["surface"], corner_radius=10)
        state_f.pack(fill="x", padx=24, pady=(0,12))
        stats_row = tk.Frame(state_f, bg=TC["surface"])
        stats_row.pack(fill="x", padx=16, pady=12)
        for icon, val, label in [
            ("📁", len([p for p in self._projects if not p.get("archived")]), "Progetti attivi"),
            ("📦", len([p for p in self._projects if p.get("archived")]),  "Archiviati"),
            ("🎯", len(self._templates), "Template"),
            ("📅", len(self._deliveries), "Consegne"),
        ]:
            sf = tk.Frame(stats_row, bg=TC["surface2"], width=100, height=70)
            sf.pack(side="left", padx=6)
            sf.pack_propagate(False)
            tk.Label(sf, text=icon, font=("Arial",16), bg=TC["surface2"]).pack(pady=(8,0))
            tk.Label(sf, text=str(val), font=("DM Sans",16,"bold"), fg=TC["text"], bg=TC["surface2"]).pack()
            tk.Label(sf, text=label, font=("DM Sans",8), fg=TC["muted"], bg=TC["surface2"]).pack()

        # Export
        exp_f = ctk.CTkFrame(self._body, fg_color=TC["surface"], corner_radius=10)
        exp_f.pack(fill="x", padx=24, pady=(0,12))
        ctk.CTkLabel(exp_f, text="📤 ESPORTA FILE DI BACKUP",
                     font=("DM Sans",12,"bold"), text_color=TC["sub"]).pack(anchor="w", padx=16, pady=(12,4))
        ctk.CTkLabel(exp_f, text="Salva tutti i progetti e template come file .json compatibile con WorkTrack.",
                     font=("DM Sans",11), text_color=TC["muted"]).pack(anchor="w", padx=16)
        ctk.CTkButton(exp_f, text=f"📤 Scarica backup completo ({len(self._projects)} progetti · {len(self._templates)} template)",
                      command=self._export_file,
                      fg_color=TC["accent"], hover_color="#B5600A",
                      font=("DM Sans",11,"bold"), height=32, corner_radius=6).pack(anchor="w", padx=16, pady=12)

        # Import
        imp_f = ctk.CTkFrame(self._body, fg_color=TC["surface"], corner_radius=10)
        imp_f.pack(fill="x", padx=24, pady=(0,20))
        ctk.CTkLabel(imp_f, text="📥 IMPORTA DA FILE",
                     font=("DM Sans",12,"bold"), text_color=TC["sub"]).pack(anchor="w", padx=16, pady=(12,4))
        ctk.CTkLabel(imp_f, text="Carica un file .json esportato da WorkTrack. Puoi unire o sostituire i dati.",
                     font=("DM Sans",11), text_color=TC["muted"]).pack(anchor="w", padx=16)

        self._import_status = ctk.CTkLabel(imp_f, text="",
                                            font=("DM Sans",11), text_color=TC["green"])
        self._import_status.pack(anchor="w", padx=16, pady=(4,0))

        btn_row = ctk.CTkFrame(imp_f, fg_color="transparent")
        btn_row.pack(anchor="w", padx=16, pady=12)
        ctk.CTkButton(btn_row, text="+ Importa (merge)",
                      command=lambda: self._import_file("merge"),
                      fg_color=TC["accent"], hover_color="#B5600A",
                      font=("DM Sans",11,"bold"), height=32, corner_radius=6).pack(side="left", padx=(0,8))
        ctk.CTkButton(btn_row, text="Sostituisci tutto",
                      command=lambda: self._import_file("replace"),
                      fg_color="transparent", hover_color=TC["surface2"],
                      border_width=1, border_color=TC["border"], text_color=TC["sub"],
                      font=("DM Sans",11), height=32, corner_radius=6).pack(side="left")
        ctk.CTkLabel(imp_f,
                     text="Merge: aggiunge senza cancellare (consigliato)\nSostituisci: cancella tutto e importa il backup",
                     font=("DM Sans",10), text_color=TC["muted"]).pack(anchor="w", padx=16, pady=(0,14))

    def _import_file(self, mode):
        path = fd.askopenfilename(title="Seleziona backup WorkTrack",
                                   filetypes=[("JSON","*.json"),("Tutti","*.*")])
        if not path: return
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            if not d.get("_worktrack") and not d.get("_worktrack_backup"):
                raise ValueError("File non riconosciuto (_worktrack mancante)")
            if not isinstance(d.get("projects"), list) or not isinstance(d.get("templates"), list):
                raise ValueError("Struttura backup non valida")

            if mode == "replace":
                self._projects  = d["projects"]
                self._templates = d["templates"]
            else:
                existing_ids = {p["id"] for p in self._projects}
                for p in d["projects"]:
                    if p["id"] in existing_ids:
                        self._projects = [p if x["id"]==p["id"] else x for x in self._projects]
                    else:
                        self._projects.append(p)
                existing_tmpl = {t["id"] for t in self._templates}
                for t in d["templates"]:
                    if t["id"] in existing_tmpl:
                        self._templates = [t if x["id"]==t["id"] else x for x in self._templates]
                    else:
                        self._templates.append(t)

            _save_progetti(self._projects)
            _save_templates(self._templates)

            msg = f"✓ {len(d['projects'])} progetti e {len(d['templates'])} template importati ({mode})"
            if hasattr(self, '_import_status'):
                self._import_status.configure(text=msg, text_color=TC["green"])
            else:
                mb.showinfo("Import completato", msg)
            self._refresh()

        except Exception as e:
            err = f"Errore: {e}"
            if hasattr(self, '_import_status'):
                self._import_status.configure(text=err, text_color=TC["red"])
            else:
                mb.showerror("Errore importazione", err)

    def _export_file(self):
        path = fd.asksaveasfilename(
            title="Salva backup WorkTrack",
            defaultextension=".json",
            initialfile=f"worktrack_backup_{datetime.now().strftime('%Y-%m-%d')}.json",
            filetypes=[("JSON","*.json")])
        if not path: return
        try:
            payload = {
                "_worktrack": True, "version": 2,
                "exportedAt": datetime.now().isoformat(),
                "label": f"Backup DMGDesk {datetime.now().strftime('%Y-%m-%d')}",
                "projects": self._projects, "templates": self._templates,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            mb.showinfo("Export completato", f"Backup salvato in:\n{path}")
        except Exception as e:
            mb.showerror("Errore export", str(e))

    # ══════════════════════════════════════════════════════════════════════════
    # Quick Tasks Sidebar
    # ══════════════════════════════════════════════════════════════════════════

    def _render_quick_sidebar(self):
        for w in self._sidebar_frame.winfo_children():
            w.destroy()

        pending = sum(1 for t in self._quick_tasks if not t.get("done"))

        if self._sidebar_collapsed:
            self._sidebar_frame.configure(width=28)
            lbl = tk.Label(self._sidebar_frame, text="⚡",
                           font=("Arial",14), bg=TC["surface"],
                           cursor="hand2")
            lbl.pack(pady=10)
            lbl.bind("<Button-1>", lambda e: self._toggle_sidebar())
            if pending > 0:
                tk.Label(self._sidebar_frame, text=str(pending),
                         font=("DM Sans",9,"bold"), fg="#fff", bg=TC["accent"],
                         padx=4, pady=1).pack()
            return

        self._sidebar_frame.configure(width=240)

        # Header
        sh = tk.Frame(self._sidebar_frame, bg=TC["surface"])
        sh.pack(fill="x", padx=8, pady=(8,4))
        tk.Label(sh, text="⚡ Task Rapidi",
                 font=("DM Sans",11,"bold"), fg=TC["text"], bg=TC["surface"]).pack(side="left")
        if pending > 0:
            tk.Label(sh, text=str(pending),
                     font=("DM Sans",9,"bold"), fg="#fff", bg=TC["accent"],
                     padx=5, pady=1).pack(side="left", padx=4)
        tk.Button(sh, text="✕", command=self._toggle_sidebar,
                  font=("DM Sans",9), fg=TC["muted"], bg=TC["surface"],
                  relief="flat", cursor="hand2").pack(side="right")

        # Input nuovo task
        inp = tk.Frame(self._sidebar_frame, bg=TC["surface"])
        inp.pack(fill="x", padx=8, pady=4)
        entry = ctk.CTkEntry(inp, width=180, height=26,
                             placeholder_text="Nuovo task...", corner_radius=5)
        entry.pack(fill="x")

        # Priorità
        prio_var = tk.StringVar(value="media")
        prio_row = tk.Frame(inp, bg=TC["surface"])
        prio_row.pack(fill="x", pady=3)
        for key, (label, fg, bg, dot) in PRIORITY_CFG.items():
            sel = key == prio_var.get()
            btn = tk.Label(prio_row, text=f"{dot} {label}",
                           font=("DM Sans",9,"bold" if sel else "normal"),
                           fg=fg, bg=bg if sel else TC["surface"],
                           cursor="hand2", padx=4, pady=2)
            btn.pack(side="left", padx=1)
            def _set_prio(k=key, b=btn, pv=prio_var):
                pv.set(k)
                self._render_quick_sidebar()
            btn.bind("<Button-1>", lambda e, f=_set_prio: f())

        def _add_qt(e=None):
            text = entry.get().strip()
            if not text: return
            self._quick_tasks.insert(0, {
                "id": uid(), "text": text,
                "priority": prio_var.get(), "done": False,
                "createdAt": datetime.now().isoformat()
            })
            entry.delete(0, "end")
            self._render_quick_sidebar()
        entry.bind("<Return>", _add_qt)
        ctk.CTkButton(inp, text="+ Aggiungi", command=_add_qt,
                      fg_color=TC["accent"], hover_color="#B5600A",
                      font=("DM Sans",10,"bold"), height=26, corner_radius=5).pack(fill="x", pady=3)

        # Lista task
        tasks_frame = ctk.CTkScrollableFrame(self._sidebar_frame, fg_color=TC["surface"],
                                              height=300, corner_radius=0)
        tasks_frame.pack(fill="both", expand=True, padx=4)

        for task in self._quick_tasks:
            label, fg, bg, dot = PRIORITY_CFG.get(task.get("priority","media"),
                                                    PRIORITY_CFG["media"])
            tr = tk.Frame(tasks_frame, bg=bg if not task.get("done") else TC["surface2"],
                          highlightbackground=fg, highlightthickness=1)
            tr.pack(fill="x", pady=2)

            check_var = tk.BooleanVar(value=task.get("done", False))
            def _toggle_qt(t=task):
                t["done"] = not t.get("done", False)
                self._render_quick_sidebar()
            tk.Checkbutton(tr, variable=check_var, command=_toggle_qt,
                           bg=tr.cget("bg"), relief="flat", cursor="hand2").pack(side="left", padx=2)

            tk.Label(tr, text=task.get("text",""),
                     font=("DM Sans",10), fg=TC["muted"] if task.get("done") else TC["text"],
                     bg=tr.cget("bg"),
                     wraplength=160, justify="left").pack(side="left", fill="x", expand=True, padx=2)

            def _del_qt(t=task):
                self._quick_tasks = [x for x in self._quick_tasks if x["id"] != t["id"]]
                self._render_quick_sidebar()
            tk.Button(tr, text="✕", command=_del_qt,
                      font=("DM Sans",8), fg=TC["red"], bg=tr.cget("bg"),
                      relief="flat", cursor="hand2").pack(side="right", padx=2)

    def _toggle_sidebar(self):
        self._sidebar_collapsed = not self._sidebar_collapsed
        self._render_quick_sidebar()

    # ══════════════════════════════════════════════════════════════════════════
    # Azioni
    # ══════════════════════════════════════════════════════════════════════════

    def _save_project(self, project):
        self._projects = [project if p["id"]==project["id"] else p for p in self._projects]
        threading.Thread(target=lambda: _save_progetti(self._projects), daemon=True).start()
        self.parent.after(0, self._refresh)

    def _set_pallet(self, project, value):
        project["pallet_assegnato"] = None if value == "—" else int(value)
        threading.Thread(target=lambda: _save_progetti(self._projects), daemon=True).start()

    def _archivia(self, project):
        project["archived"] = not project.get("archived", False)
        self._projects = [project if p["id"]==project["id"] else p for p in self._projects]
        _save_progetti(self._projects)
        self._selected_id = None
        self._refresh()

    def _elimina_id(self, pid):
        if not mb.askyesno("Elimina", "Eliminare il progetto? L'operazione è irreversibile."):
            return
        self._projects = [p for p in self._projects if p["id"] != pid]
        _save_progetti(self._projects)
        self._selected_id = None
        self._refresh()

    def _delete_step(self, project, step_id):
        project["steps"] = [s for s in project.get("steps",[]) if s["id"] != step_id]
        self._save_project(project)

    def _delete_task(self, project, step_id, task_id):
        for s in project.get("steps",[]):
            if s["id"] == step_id:
                s["tasks"] = [t for t in s.get("tasks",[]) if t["id"] != task_id]
        self._save_project(project)

    def _salva_come_template(self, project):
        """Dialog per salvare il progetto come template."""
        name = tk.simpledialog.askstring(
            "Salva come Template",
            f"Nome template:\n(Le fasi di '{project.get('name','')}' verranno copiate)",
            initialvalue=project.get("name","")
        )
        if not name or not name.strip(): return

        steps = [
            {"id": uid(), "title": s["title"],
             "tasks": [{"id": uid(), "text": t["text"]} for t in s.get("tasks",[])]}
            for s in project.get("steps",[])
        ]
        # Scegli icona
        icon = "🔧"
        tmpl = {
            "id": uid(), "name": name.strip(),
            "description": project.get("description",""),
            "icon": icon, "color": project.get("color", TC["accent"]),
            "steps": steps,
        }
        self._templates.append(tmpl)
        _save_templates(self._templates)
        mb.showinfo("Template salvato", f"Template '{name}' salvato con {len(steps)} fasi.")

    def _apri_modal_lancio(self, project):
        """Modal di selezione programmi prima del lancio in NC — identico alla versione web."""
        all_pgm = [pgm
                   for step in project.get("steps", [])
                   for task in step.get("tasks", [])
                   if task.get("text","").strip().lower() == "fresatura"
                   for pgm in task.get("programs", [])
                   if pgm.get("tipoGruppo") != "ipm"]

        if not all_pgm:
            mb.showwarning("Nessun programma", "Nessun programma MPF nel progetto.")
            return

        tools_db = self._get_tools_db()
        da_fare     = [p for p in all_pgm if p.get("stato") == "da_fare"]
        in_macchina = [p for p in all_pgm if p.get("stato") == "in_macchina"]
        completati  = [p for p in all_pgm if p.get("stato") == "completato"]

        win = tk.Toplevel(self.parent)
        win.title("Lancia in Analisi NC")
        win.geometry("660x560")
        win.grab_set()
        win.configure(bg=TC["bg"])

        # Header
        hdr = tk.Frame(win, bg=TC["surface"])
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"📄 Lancia in Analisi NC — {project.get('name','')}",
                 font=("DM Sans",13,"bold"), fg=TC["text"], bg=TC["surface"]).pack(side="left", padx=14, pady=10)
        tk.Button(hdr, text="✕", command=win.destroy,
                  font=("DM Sans",10), fg=TC["sub"], bg=TC["surface"],
                  relief="flat", cursor="hand2").pack(side="right", padx=8)
        tk.Frame(win, height=1, bg=TC["border"]).pack(fill="x")

        # Bottoni selezione rapida
        sel_frame = tk.Frame(win, bg=TC["surface"])
        sel_frame.pack(fill="x", padx=12, pady=8)

        selected = {}  # filename → BooleanVar
        check_widgets = {}  # filename → widget per aggiornare colori

        def _aggiorna_counter():
            n = sum(1 for v in selected.values() if v.get())
            problemi = sum(1 for fn, v in selected.items() if v.get() and
                           any(p.get("filename")==fn for p in all_pgm
                               if p.get("stato")=="in_macchina" and
                               self._classify_tool(p.get("utensile",""), tools_db)
                               in ("mancante","fin_vita","disabilitato")))
            btn_lancia.configure(
                text=f"📄 Lancia {n} in NC →" if n > 0 else "📄 Lancia in NC →",
                state="normal" if n > 0 else "disabled",
                fg_color=TC["blue"] if n > 0 else TC["border"]
            )
            lbl_counter.configure(
                text=f"{n} selezionati{'  ·  ⚠ ' + str(problemi) + ' problematici' if problemi else '  ·  ✓ tutti ok' if n > 0 else ''}",
                text_color="#DC2626" if problemi else (TC["green"] if n > 0 else TC["muted"])
            )

        def _sel_da_fare():
            for fn, var in selected.items():
                var.set(any(p.get("filename")==fn and p.get("stato")=="da_fare"
                            for p in all_pgm))
            _aggiorna_counter()

        def _sel_tutti():
            for var in selected.values(): var.set(True)
            _aggiorna_counter()

        def _desel_tutti():
            for var in selected.values(): var.set(False)
            _aggiorna_counter()

        ctk.CTkButton(sel_frame, text=f"☑ Seleziona da fare ({len(da_fare)})",
                      command=_sel_da_fare,
                      fg_color=TC["blue"], hover_color="#1552A0",
                      font=("DM Sans",10,"bold"), height=28, corner_radius=6).pack(side="left", padx=3)
        if in_macchina:
            ctk.CTkButton(sel_frame, text=f"Seleziona tutti ({len(da_fare)+len(in_macchina)})",
                          command=_sel_tutti,
                          fg_color=TC["surface2"], hover_color=TC["border"],
                          text_color=TC["sub"],
                          font=("DM Sans",10), height=28, corner_radius=6).pack(side="left", padx=3)
        ctk.CTkButton(sel_frame, text="Deseleziona",
                      command=_desel_tutti,
                      fg_color="transparent", hover_color=TC["surface2"],
                      text_color=TC["muted"], border_width=1, border_color=TC["border"],
                      font=("DM Sans",10), height=28, corner_radius=6).pack(side="left", padx=3)

        # Lista programmi
        TOOL_BG = {"mancante":"#FEE2E2","fin_vita":"#FEF9C3","disabilitato":"#EDE9FE"}
        TOOL_FG = {"mancante":"#DC2626","fin_vita":"#D97706","disabilitato":"#7C3AED"}

        list_frame = ctk.CTkScrollableFrame(win, fg_color=TC["bg"], corner_radius=0)
        list_frame.pack(fill="both", expand=True, padx=4)

        def _render_section(label, color, items, dimmed=False):
            if not items: return
            sh = tk.Frame(list_frame, bg=color)
            sh.pack(fill="x", pady=(4,0))
            tk.Label(sh, text=f"  {label} — {len(items)}",
                     font=("DM Sans",8,"bold"), fg=TC["text"], bg=color).pack(side="left", pady=3)

            for pgm in items:
                fn = pgm.get("filename","")
                var = tk.BooleanVar(value=False)
                selected[fn] = var

                ts = self._classify_tool(pgm.get("utensile",""), tools_db)                      if pgm.get("stato")=="in_macchina" else None
                row_bg = TOOL_BG.get(ts, TC["surface"] if not dimmed else "#F8F8F8")

                row = tk.Frame(list_frame, bg=row_bg,
                               highlightbackground=TOOL_FG.get(ts, TC["border"]),
                               highlightthickness=1)
                row.pack(fill="x", pady=1, padx=2)

                cb = tk.Checkbutton(row, variable=var, command=_aggiorna_counter,
                                    bg=row_bg, activebackground=row_bg,
                                    cursor="hand2", relief="flat")
                cb.pack(side="left", padx=4)
                row.bind("<Button-1>", lambda e, v=var: [v.set(not v.get()), _aggiorna_counter()])

                alias = pgm.get("utensile","") or "—"
                badge = {"mancante":" ✗","fin_vita":" ⚠","disabilitato":" ⊘"}.get(ts,"")
                tk.Label(row, text=alias+badge,
                         font=("Consolas",9,"bold" if ts else "normal"),
                         fg=TOOL_FG.get(ts, TC["text"] if not dimmed else TC["muted"]),
                         bg=row_bg, width=22, anchor="w").pack(side="left", padx=2)
                op = (pgm.get("tipoOp","") or "").replace("- NESSUN TESTO","").strip()[:40]
                tk.Label(row, text=op or pgm.get("filename",""),
                         font=("DM Sans",9), fg=TC["sub"] if not dimmed else TC["muted"],
                         bg=row_bg).pack(side="left", padx=4)
                tk.Label(row, text=f"#{pgm.get('numPgm','')}",
                         font=("Consolas",9), fg=TC["blue"], bg=row_bg).pack(side="right", padx=6)

        _render_section("DA FARE", "#F0F4FF", da_fare)
        _render_section("IN MACCHINA", "#E8F0FA", in_macchina, dimmed=True)
        # Completati collassati
        if completati:
            show_comp = tk.BooleanVar(value=False)
            comp_frame = tk.Frame(list_frame, bg=TC["bg"])
            def _toggle_comp():
                show_comp.set(not show_comp.get())
                if show_comp.get():
                    _render_section("COMPLETATI", "#F0EEE8", completati, dimmed=True)
                    toggle_btn.configure(text=f"▲ COMPLETATI — {len(completati)}")
                else:
                    toggle_btn.configure(text=f"▼ COMPLETATI — {len(completati)}")
            toggle_btn = tk.Button(list_frame, text=f"▼ COMPLETATI — {len(completati)}",
                                   command=_toggle_comp,
                                   font=("DM Sans",8,"bold"), fg=TC["muted"], bg=TC["bg"],
                                   relief="flat", cursor="hand2")
            toggle_btn.pack(anchor="w", padx=8, pady=4)

        # Footer
        tk.Frame(win, height=1, bg=TC["border"]).pack(fill="x")
        footer = tk.Frame(win, bg="#F5F4F0")
        footer.pack(fill="x", padx=12, pady=8)

        lbl_counter = ctk.CTkLabel(footer, text="Nessun programma selezionato",
                                    font=("DM Sans",11), text_color=TC["muted"])
        lbl_counter.pack(side="left")

        tk.Button(footer, text="Annulla", command=win.destroy,
                  font=("DM Sans",11), fg=TC["sub"], bg=TC["surface2"],
                  relief="flat", padx=12, pady=6, cursor="hand2").pack(side="right", padx=4)

        btn_lancia = ctk.CTkButton(footer, text="📄 Lancia in NC →",
                                    command=lambda: self._esegui_lancio(
                                        project,
                                        [p for p in all_pgm if selected.get(p.get("filename","")) and selected[p.get("filename","")].get()],
                                        win),
                                    fg_color=TC["border"], state="disabled",
                                    font=("DM Sans",11,"bold"), height=34, corner_radius=6)
        btn_lancia.pack(side="right", padx=4)

        # Seleziona da fare di default
        _sel_da_fare()

    def _esegui_lancio(self, project, pgm_selezionati, win):
        """Esegue il lancio in NC con i programmi selezionati."""
        if win:
            win.destroy()
        self._lancia_nc(project, pgm_selezionati)

    def _lancia_nc(self, project, pgm_selezionati=None):
        # Se pgm_selezionati è passato dal modal, usa quelli; altrimenti da_fare
        if pgm_selezionati is not None:
            mpf = [p for p in pgm_selezionati if p.get("tipoGruppo") != "ipm"]
        else:
            mpf = [p for p in get_mpf_list(project) if p.get("stato") == "da_fare"]
        if not mpf:
            mb.showwarning("Nessun programma", "Nessun programma selezionato.")
            return
        cfg    = _carica_config()
        base_nc = (cfg.get("percorso_nc_base") or "").strip()
        filenames = [p.get("filename","") for p in mpf if p.get("filename")]
        found_paths = []
        if base_nc:
            for fn in filenames:
                for root, _, files in os.walk(base_nc):
                    if fn in files:
                        found_paths.append(os.path.join(root, fn))
                        break
        if found_paths:
            try:
                nc_tab = self.main.tab_analisi_nc
                for fp in found_paths:
                    if fp not in nc_tab.file_paths:
                        nc_tab.file_paths.append(fp)
                nc_tab._aggiorna_lista()
                nc_tab._confronta()
                # Nome cartella: progetto come fonte primaria, file MPF come fallback
                import re as _re
                nome = project.get("name","").replace(" ","_").upper()
                if not nome:
                    first_fn = (filenames[0] if filenames else "").replace(".MPF","").replace(".mpf","")
                    tokens = first_fn.split("_")
                    if len(tokens) >= 2 and _re.match(r'^\d+$', tokens[0]):
                        nome = f"{tokens[0]}_{tokens[1]}" 
                nc_tab.entry_nome.delete(0,"end")
                nc_tab.entry_nome.insert(0, nome)
                self.main.tabview.set("📄 Analisi NC")
                mb.showinfo("Caricato", f"{len(found_paths)} file MPF caricati in Analisi NC")
            except Exception as e:
                mb.showerror("Errore", str(e))
        else:
            mb.showwarning("File non trovati",
                           f"{len(filenames)} file MPF non trovati in:\n{base_nc or '(percorso non configurato)'}\n\n"
                           + "\n".join(filenames[:5]))

    def _nuovo_progetto(self):
        win = tk.Toplevel(self.parent)
        win.title("Nuovo Progetto")
        win.geometry("480x380")
        win.grab_set()
        win.configure(bg=TC["bg"])

        tk.Label(win, text="NOME PROGETTO *", font=("DM Sans",10,"bold"), fg=TC["sub"], bg=TC["bg"]).pack(anchor="w", padx=20, pady=(14,2))
        name_e = ctk.CTkEntry(win, width=400, height=32, corner_radius=6)
        name_e.pack(anchor="w", padx=20)
        name_e.focus()

        tk.Label(win, text="TEMPLATE", font=("DM Sans",10,"bold"), fg=TC["sub"], bg=TC["bg"]).pack(anchor="w", padx=20, pady=(10,2))
        tmpl_var = tk.StringVar(value="(nessuno)")
        tmpl_names = ["(nessuno)"] + [t.get("name","?") for t in self._templates]
        ttk.Combobox(win, textvariable=tmpl_var, values=tmpl_names, state="readonly", width=35).pack(anchor="w", padx=20)

        tk.Label(win, text="COLORE", font=("DM Sans",10,"bold"), fg=TC["sub"], bg=TC["bg"]).pack(anchor="w", padx=20, pady=(10,2))
        color_var = tk.StringVar(value=COLORS_LIST[0])
        color_row = tk.Frame(win, bg=TC["bg"])
        color_row.pack(anchor="w", padx=20)
        for c in COLORS_LIST:
            btn = tk.Label(color_row, text="●", font=("Arial",18), fg=c, bg=TC["bg"], cursor="hand2", padx=2)
            btn.pack(side="left")
            def _set(cc=c, b=btn, cv=color_var):
                cv.set(cc)
                for child in color_row.winfo_children():
                    child.configure(bg=TC["bg"])
                b.configure(bg=TC["surface2"])
            btn.bind("<Button-1>", lambda e, f=_set: f())

        def _create():
            name = name_e.get().strip()
            if not name: return
            tmpl_name = tmpl_var.get()
            tmpl = next((t for t in self._templates if t.get("name")==tmpl_name), None)
            steps = clone_template_to_steps(tmpl) if tmpl else [{"id":uid(),"title":"Step 1","tasks":[]}]
            project = {
                "id": uid(), "name": name, "description": "",
                "color": color_var.get(), "steps": steps,
                "createdAt": datetime.now().isoformat()[:10],
                "archived": False, "pallet_assegnato": None, "log": []
            }
            self._projects.append(project)
            _save_progetti(self._projects)
            win.destroy()
            self._selected_id = project["id"]
            self._refresh()

        ctk.CTkButton(win, text="Crea Progetto", command=_create,
                      fg_color=COLORS_LIST[0], hover_color="#B5600A",
                      font=("DM Sans",12,"bold"), height=36, corner_radius=6).pack(pady=16, padx=20)

    # Template actions
    def _nuovo_template(self):
        tmpl = {"id": f"new_{uid()}", "name": "Nuovo Template",
                "description": "", "icon": "🚀", "color": TC["accent"], "steps": []}
        self._templates.append(tmpl)
        self._editing_template = tmpl
        self._refresh()

    def _modifica_template(self, tmpl):
        self._editing_template = tmpl
        self._refresh()

    def _cancel_template_edit(self):
        # Se era nuovo e non salvato, rimuovilo
        if self._editing_template and self._editing_template.get("id","").startswith("new_"):
            self._templates = [t for t in self._templates if t["id"] != self._editing_template["id"]]
        self._editing_template = None
        self._set_page("templates")

    def _usa_template(self, tmpl):
        self._set_page("projects")
        self._nuovo_progetto()

    def _duplica_template(self, tmpl):
        import copy
        copy_tmpl = copy.deepcopy(tmpl)
        copy_tmpl["id"] = uid()
        copy_tmpl["name"] = f"{tmpl['name']} (copia)"
        for s in copy_tmpl.get("steps",[]):
            s["id"] = uid()
            for t in s.get("tasks",[]): t["id"] = uid()
        idx = next((i for i,t in enumerate(self._templates) if t["id"]==tmpl["id"]), len(self._templates)-1)
        self._templates.insert(idx+1, copy_tmpl)
        _save_templates(self._templates)
        self._refresh()

    def _elimina_template(self, tid):
        if mb.askyesno("Elimina", "Eliminare questo template?"):
            self._templates = [t for t in self._templates if t["id"] != tid]
            _save_templates(self._templates)
            self._refresh()

    def refresh(self):
        self._load()
