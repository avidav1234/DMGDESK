"""Tab Progetti — WorkTrack integrato in DMGDesk desktop (porting fedele)"""

import customtkinter as ctk
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox as mb
import tkinter.filedialog as fd
import json, threading, os, sys
from pathlib import Path
from datetime import datetime

from config.theme import *
from config.constants import *

# ── Helpers config ────────────────────────────────────────────────────────────

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

def _progetti_path() -> Path | None:
    cfg = _carica_config()
    base = (cfg.get("tools_toa_folder") or "").strip()
    return Path(base) / "worktrack_projects.json" if base else None

def _templates_path() -> Path | None:
    cfg = _carica_config()
    base = (cfg.get("tools_toa_folder") or "").strip()
    return Path(base) / "worktrack_templates.json" if base else None

def _load_progetti() -> list:
    path = _progetti_path()
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("projects", [])
        except Exception:
            pass
    return []

def _load_templates() -> list:
    path = _templates_path()
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []

def _save_progetti(projects: list):
    path = _progetti_path()
    if not path:
        return
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = {}
        data["projects"] = projects
        data["ultimo_aggiornamento"] = datetime.now().isoformat()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Errore salvataggio: {e}")

def _save_templates(templates: list):
    path = _templates_path()
    if not path:
        return
    try:
        path.write_text(json.dumps(templates, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Errore salvataggio template: {e}")

# ── Utils ─────────────────────────────────────────────────────────────────────

def uid():
    import random, string
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))

def now_str():
    return datetime.now().strftime("%d/%m/%Y %H:%M")

def get_progress(project: dict) -> int:
    tasks = [t for s in project.get("steps", []) for t in s.get("tasks", [])]
    if not tasks:
        return 0
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

# ── Colori tema (caldo, coerente con web) ─────────────────────────────────────
TC = {
    "bg":      "#F5F4F0",
    "surface": "#FFFFFF",
    "surface2":"#F0EEE8",
    "border":  "#D8D5CC",
    "text":    "#1A1814",
    "sub":     "#5A5750",
    "muted":   "#9A978E",
    "accent":  "#D4700A",
    "green":   "#1A7A4A",
    "red":     "#C0392B",
    "blue":    "#1D5FAD",
}

STATO_NEXT = {"da_fare": "in_macchina", "in_macchina": "completato", "completato": "da_fare"}
STATO_CFG  = {
    "da_fare":     ("○ Da fare",     "#9A978E", "#F0EEE8"),
    "in_macchina": ("⚙ In macchina", "#1D5FAD", "#EAF1FB"),
    "completato":  ("✓ Completato",  "#1A7A4A", "#E8F5EE"),
}

# ══════════════════════════════════════════════════════════════════════════════
class TabProgetti:
    """Tab Progetti — porting fedele di WorkTrack."""

    def __init__(self, parent, main_window):
        self.parent     = parent
        self.main       = main_window
        self._projects  = []
        self._templates = []
        self._page      = "projects"   # projects | archived | backup
        self._selected_id = None
        self._create_ui()
        self._load()

    # ══════════════════════════════════════════════════════════════════════════
    # UI principale
    # ══════════════════════════════════════════════════════════════════════════

    def _create_ui(self):
        # ── Top bar ───────────────────────────────────────────────────────────
        self.topbar = ctk.CTkFrame(self.parent, fg_color=TC["surface"],
                                   height=48, corner_radius=0)
        self.topbar.pack(fill="x")
        self.topbar.pack_propagate(False)

        # Logo / titolo
        ctk.CTkLabel(self.topbar, text="◈ WorkTrack",
                     font=("DM Sans", 16, "bold"),
                     text_color=TC["text"]).pack(side="left", padx=14, pady=10)

        sep = tk.Frame(self.topbar, width=1, bg=TC["border"])
        sep.pack(side="left", fill="y", pady=8)

        # Nav buttons
        self._nav_btns = {}
        for nav_id, label in [("projects","Progetti"), ("archived","Archivio"), ("backup","Backup")]:
            btn = tk.Label(self.topbar, text=label,
                           font=("DM Sans", 11, "bold"),
                           fg=TC["accent"] if nav_id=="projects" else TC["sub"],
                           bg=TC["surface"], cursor="hand2", padx=14)
            btn.pack(side="left")
            btn.bind("<Button-1>", lambda e, nid=nav_id: self._set_page(nid))
            self._nav_btns[nav_id] = btn

        # Destra: cerca + nuovo
        right = tk.Frame(self.topbar, bg=TC["surface"])
        right.pack(side="right", padx=10)

        self._btn_nuovo = ctk.CTkButton(right, text="+ Nuovo Progetto",
                                         command=self._nuovo_progetto,
                                         fg_color=TC["accent"], hover_color="#B5600A",
                                         font=("DM Sans", 12, "bold"),
                                         height=30, corner_radius=6)
        self._btn_nuovo.pack(side="right", padx=4, pady=8)

        self._entry_search = ctk.CTkEntry(right, width=180, height=30,
                                           placeholder_text="Cerca progetto...",
                                           corner_radius=6)
        self._entry_search.pack(side="right", padx=4, pady=8)
        self._entry_search.bind("<KeyRelease>", lambda e: self._refresh())

        # ── Separatore ────────────────────────────────────────────────────────
        tk.Frame(self.parent, height=1, bg=TC["border"]).pack(fill="x")

        # ── Corpo scrollabile ─────────────────────────────────────────────────
        self._body = ctk.CTkScrollableFrame(self.parent, fg_color=TC["bg"],
                                             corner_radius=0)
        self._body.pack(fill="both", expand=True)

    def _set_page(self, page):
        self._page = page
        self._selected_id = None
        for nid, btn in self._nav_btns.items():
            btn.configure(fg=TC["accent"] if nid==page else TC["sub"])
        self._refresh()

    def _clear_body(self):
        for w in self._body.winfo_children():
            w.destroy()

    # ══════════════════════════════════════════════════════════════════════════
    # Caricamento dati
    # ══════════════════════════════════════════════════════════════════════════

    def _load(self):
        def _worker():
            projects  = _load_progetti()
            templates = _load_templates()
            self.parent.after(0, lambda: self._set_data(projects, templates))
        threading.Thread(target=_worker, daemon=True).start()

    def _set_data(self, projects, templates):
        self._projects  = projects
        self._templates = templates
        self._refresh()

    def _save(self):
        threading.Thread(target=lambda: _save_progetti(self._projects), daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # Render pagine
    # ══════════════════════════════════════════════════════════════════════════

    def _refresh(self):
        self._clear_body()
        if self._page == "backup":
            self._render_backup()
        elif self._selected_id:
            project = next((p for p in self._projects if p.get("id") == self._selected_id), None)
            if project:
                self._render_detail(project)
            else:
                self._selected_id = None
                self._render_lista()
        elif self._page == "archived":
            self._render_lista(archived=True)
        else:
            self._render_lista(archived=False)

    # ── Lista progetti ─────────────────────────────────────────────────────────

    def _render_lista(self, archived=False):
        q = (self._entry_search.get() if hasattr(self, '_entry_search') else "").strip().lower()
        projects = [p for p in self._projects
                    if p.get("archived", False) == archived
                    and (q == "" or q in p.get("name","").lower()
                         or q in p.get("description","").lower())]

        in_progress = [p for p in projects if get_progress(p) < 100]
        completed   = [p for p in projects if get_progress(p) == 100]

        if not projects:
            lbl = ctk.CTkLabel(self._body,
                               text="Nessun progetto. Usa '+ Nuovo Progetto' per iniziare." if not archived else "Nessun progetto archiviato.",
                               font=("DM Sans", 14), text_color=TC["muted"])
            lbl.pack(pady=60)
            return

        for section_label, section_projects in [
            ("IN CORSO" if not archived else "ARCHIVIO", in_progress + (completed if archived else [])),
            ("COMPLETATI", completed if not archived else []),
        ]:
            if not section_projects:
                continue
            # Intestazione sezione
            hdr = ctk.CTkFrame(self._body, fg_color="transparent")
            hdr.pack(fill="x", padx=24, pady=(16, 6))
            ctk.CTkLabel(hdr,
                         text=f"{section_label} — {len(section_projects)}",
                         font=("DM Sans", 11, "bold"),
                         text_color=TC["muted"]).pack(side="left")

            # Griglia card 2 colonne
            grid = ctk.CTkFrame(self._body, fg_color="transparent")
            grid.pack(fill="x", padx=20, pady=0)
            grid.columnconfigure(0, weight=1)
            grid.columnconfigure(1, weight=1)

            for i, p in enumerate(section_projects):
                row, col = divmod(i, 2)
                self._project_card(grid, p, row, col)

    def _project_card(self, parent, project, row, col):
        pct    = get_progress(project)
        color  = project.get("color", TC["accent"])
        s_next, t_next = get_next_task(project)
        mpf    = get_mpf_list(project)
        pallet = project.get("pallet_assegnato")

        card = tk.Frame(parent, bg=TC["surface"],
                        highlightbackground=color,
                        highlightthickness=3, bd=0,
                        cursor="hand2")
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        card.bind("<Button-1>", lambda e, pid=project["id"]: self._open_project(pid))

        # Nome + pallet badge
        top_row = tk.Frame(card, bg=TC["surface"])
        top_row.pack(fill="x", padx=14, pady=(12,4))
        dot = tk.Label(top_row, text="●", fg=color, bg=TC["surface"], font=("Arial",10))
        dot.pack(side="left")
        tk.Label(top_row, text=project.get("name","?"),
                 font=("DM Sans",13,"bold"), fg=TC["text"], bg=TC["surface"],
                 anchor="w").pack(side="left", padx=6)
        if pallet:
            tk.Label(top_row, text=f"P{pallet}",
                     font=("DM Sans",10,"bold"), fg=color, bg=TC["surface"]).pack(side="left")

        # Descrizione
        if project.get("description"):
            tk.Label(card, text=project["description"],
                     font=("DM Sans",11), fg=TC["sub"], bg=TC["surface"],
                     anchor="w").pack(fill="x", padx=20, pady=(0,4))

        # Barra progresso
        bar_bg = tk.Frame(card, height=5, bg=TC["surface2"])
        bar_bg.pack(fill="x", padx=14, pady=(2,6))
        bar_bg.pack_propagate(False)
        bar_bg.update_idletasks()
        w = bar_bg.winfo_width() or 200
        bar_fill = tk.Frame(bar_bg, width=int(w * pct / 100),
                            height=5, bg=TC["green"] if pct==100 else color)
        bar_fill.pack(side="left")

        # Stats row
        stats_row = tk.Frame(card, bg=TC["surface"])
        stats_row.pack(fill="x", padx=14, pady=(0,4))
        tasks_all  = [t for s in project.get("steps",[]) for t in s.get("tasks",[])]
        tasks_done = sum(1 for t in tasks_all if t.get("done"))
        tk.Label(stats_row, text=f"{tasks_done}/{len(tasks_all)} task",
                 font=("DM Sans",11), fg=TC["sub"], bg=TC["surface"]).pack(side="left")
        if mpf:
            mpf_done = sum(1 for p in mpf if p.get("stato")=="completato")
            tk.Label(stats_row, text=f"  ⚙ {mpf_done}/{len(mpf)} MPF",
                     font=("DM Sans",11,"bold"), fg=TC["blue"], bg=TC["surface"]).pack(side="left")
        status_color = TC["green"] if pct==100 else (TC["accent"] if pct>0 else TC["muted"])
        status_text  = "✓ Completato" if pct==100 else (f"{pct}% In corso" if pct>0 else "Non iniziato")
        tk.Label(stats_row, text=status_text,
                 font=("DM Sans",11,"bold"), fg=status_color, bg=TC["surface"]).pack(side="right")

        # Prossimo step
        if t_next:
            next_frame = tk.Frame(card, bg="#FFF4E8", bd=0)
            next_frame.pack(fill="x", padx=14, pady=(0,12))
            tk.Label(next_frame, text="📍 PROSSIMO",
                     font=("DM Sans",9,"bold"), fg=TC["accent"], bg="#FFF4E8").pack(anchor="w", padx=8, pady=(6,0))
            tk.Label(next_frame, text=f"{s_next.get('title','?')} › {t_next.get('text','?')}",
                     font=("DM Sans",12), fg=TC["text"], bg="#FFF4E8").pack(anchor="w", padx=8, pady=(0,6))
        elif pct == 100:
            done_frame = tk.Frame(card, bg="#E8F5EE", bd=0)
            done_frame.pack(fill="x", padx=14, pady=(0,12))
            tk.Label(done_frame, text="✓ Progetto completato",
                     font=("DM Sans",12,"bold"), fg=TC["green"], bg="#E8F5EE").pack(anchor="w", padx=8, pady=6)

        # Click su tutto il card
        for w in [card, top_row, stats_row]:
            w.bind("<Button-1>", lambda e, pid=project["id"]: self._open_project(pid))

    def _open_project(self, pid):
        self._selected_id = pid
        self._refresh()

    # ── Dettaglio progetto ────────────────────────────────────────────────────

    def _render_detail(self, project):
        pct   = get_progress(project)
        color = project.get("color", TC["accent"])
        s_next, t_next = get_next_task(project)
        mpf   = get_mpf_list(project)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self._body, fg_color=TC["surface"], corner_radius=0)
        hdr.pack(fill="x")

        # Riga 1: pulsanti + titolo
        row1 = tk.Frame(hdr, bg=TC["surface"])
        row1.pack(fill="x", padx=20, pady=(14,6))

        tk.Button(row1, text="← Indietro", command=lambda: self._back(),
                  font=("DM Sans",11), fg=TC["sub"], bg=TC["surface2"],
                  relief="flat", padx=12, pady=5, cursor="hand2").pack(side="left")

        tk.Frame(row1, width=8, bg=TC["surface"]).pack(side="left")
        tk.Label(row1, text="●", fg=color, bg=TC["surface"], font=("Arial",12)).pack(side="left")
        tk.Frame(row1, width=6, bg=TC["surface"]).pack(side="left")
        tk.Label(row1, text=project.get("name","?"),
                 font=("DM Sans",18,"bold"), fg=TC["text"], bg=TC["surface"]).pack(side="left")

        # Pallet
        pallet_var = tk.StringVar(value=str(project.get("pallet_assegnato","—")))
        tk.Label(row1, text="  Pallet:", font=("DM Sans",11), fg=TC["muted"], bg=TC["surface"]).pack(side="left", padx=(20,4))
        pallet_opt = ttk.Combobox(row1, textvariable=pallet_var,
                                  values=["—","1","2","3","4","5","6"],
                                  width=4, state="readonly")
        pallet_opt.pack(side="left")
        pallet_opt.bind("<<ComboboxSelected>>", lambda e: self._set_pallet(project, pallet_var.get()))

        # Lancia NC
        if mpf:
            tk.Button(row1, text=f"📄 Lancia {len(mpf)} file in NC →",
                      command=lambda: self._lancia_nc(project),
                      font=("DM Sans",11,"bold"), fg="#fff", bg=TC["blue"],
                      relief="flat", padx=12, pady=5, cursor="hand2").pack(side="left", padx=12)

        # Archivia / Elimina
        tk.Button(row1, text="📦 Archivia" if not project.get("archived") else "📤 Riattiva",
                  command=lambda: self._archivia(project),
                  font=("DM Sans",10), fg=TC["sub"], bg=TC["surface2"],
                  relief="flat", padx=8, pady=4, cursor="hand2").pack(side="right", padx=4)
        tk.Button(row1, text="🗑 Elimina",
                  command=lambda: self._elimina_id(project["id"]),
                  font=("DM Sans",10), fg=TC["red"], bg="#FDECEA",
                  relief="flat", padx=8, pady=4, cursor="hand2").pack(side="right", padx=4)

        # Progress
        row2 = tk.Frame(hdr, bg=TC["surface"])
        row2.pack(fill="x", padx=20, pady=(0,8))
        tasks_all  = [t for s in project.get("steps",[]) for t in s.get("tasks",[])]
        tasks_done = sum(1 for t in tasks_all if t.get("done"))
        tk.Label(row2, text="Avanzamento",
                 font=("DM Sans",11,"bold"), fg=TC["sub"], bg=TC["surface"]).pack(side="left")
        tk.Label(row2, text=f"  {pct}% — {tasks_done} di {len(tasks_all)} task completati",
                 font=("DM Sans",11,"bold"), fg=color, bg=TC["surface"]).pack(side="left")

        bar_bg = tk.Frame(hdr, height=6, bg=TC["surface2"])
        bar_bg.pack(fill="x", padx=20, pady=(0,8))
        bar_bg.update_idletasks()
        bw = bar_bg.winfo_width() or 600
        tk.Frame(bar_bg, width=int(bw*pct/100), height=6,
                 bg=TC["green"] if pct==100 else color).pack(side="left")

        # Prossimo step
        if t_next:
            next_f = tk.Frame(hdr, bg="#FFF4E8", bd=0)
            next_f.pack(fill="x", padx=20, pady=(0,10))
            tk.Label(next_f, text="📍 RIPRENDI DA QUI",
                     font=("DM Sans",10,"bold"), fg=TC["accent"], bg="#FFF4E8").pack(anchor="w", padx=10, pady=(6,0))
            tk.Label(next_f, text=f"{s_next.get('title','?')} › {t_next.get('text','?')}",
                     font=("DM Sans",13), fg=TC["text"], bg="#FFF4E8").pack(anchor="w", padx=10, pady=(0,6))

        # ── Tab task / log ────────────────────────────────────────────────────
        tab_row = tk.Frame(hdr, bg=TC["surface"])
        tab_row.pack(fill="x", padx=20)
        self._active_tab = getattr(self, '_active_tab', 'tasks')

        def _switch_tab(t):
            self._active_tab = t
            self._render_detail(project)

        for tab_id, label in [("tasks","Task"), ("log",f"Log ({len(project.get('log',[]))})")]:
            active = self._active_tab == tab_id
            lbl = tk.Label(tab_row, text=label,
                           font=("DM Sans",13,"bold"),
                           fg=color if active else TC["sub"],
                           bg=TC["surface"], cursor="hand2", padx=0, pady=10)
            lbl.pack(side="left", padx=(0,20))
            if active:
                # sottolineatura
                tk.Frame(tab_row, height=3, bg=color, width=len(label)*8).place(in_=lbl, relx=0, rely=1.0, anchor="sw")
            lbl.bind("<Button-1>", lambda e, t=tab_id: _switch_tab(t))

        tk.Frame(hdr, height=1, bg=TC["border"]).pack(fill="x")

        # ── Body tab ──────────────────────────────────────────────────────────
        body = ctk.CTkFrame(self._body, fg_color=TC["bg"], corner_radius=0)
        body.pack(fill="both", expand=True, padx=20, pady=16)

        if self._active_tab == "tasks":
            self._render_tasks(body, project)
        else:
            self._render_log(body, project)

    def _back(self):
        self._selected_id = None
        self._active_tab  = 'tasks'
        self._refresh()

    # ── Tasks ──────────────────────────────────────────────────────────────────

    def _render_tasks(self, parent, project):
        for step in project.get("steps", []):
            self._render_step(parent, project, step)

        # Aggiungi fase
        add_step_frame = ctk.CTkFrame(parent, fg_color="transparent")
        add_step_frame.pack(fill="x", pady=4)

        add_entry = ctk.CTkEntry(add_step_frame, width=280, height=32,
                                 placeholder_text="Nome nuova fase... (Invio per creare)",
                                 corner_radius=6)
        add_entry.pack(side="left")

        def _add_step(e=None):
            name = add_entry.get().strip()
            if not name:
                return
            project["steps"].append({"id": uid(), "title": name, "tasks": []})
            self._save_and_refresh(project)

        add_entry.bind("<Return>", _add_step)
        ctk.CTkButton(add_step_frame, text="+ Fase", command=_add_step,
                      fg_color=TC["accent"], hover_color="#B5600A",
                      font=("DM Sans",11,"bold"), height=32, width=80,
                      corner_radius=6).pack(side="left", padx=6)

    def _render_step(self, parent, project, step):
        color = project.get("color", TC["accent"])
        done  = sum(1 for t in step.get("tasks", []) if t.get("done"))
        total = len(step.get("tasks", []))

        # Step frame con bordo sinistro colorato
        sf = tk.Frame(parent, bg=TC["surface"],
                      highlightbackground=color, highlightthickness=2, bd=0)
        sf.pack(fill="x", pady=(0,10))
        sf.configure(highlightthickness=0)
        left_bar = tk.Frame(sf, width=4, bg=color)
        left_bar.pack(side="left", fill="y")

        content = tk.Frame(sf, bg=TC["surface"])
        content.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        # Header step
        step_hdr = tk.Frame(content, bg=TC["surface"])
        step_hdr.pack(fill="x", pady=(0,6))
        tk.Label(step_hdr, text=step.get("title",""),
                 font=("DM Sans",13,"bold"), fg=TC["text"], bg=TC["surface"]).pack(side="left")
        tk.Label(step_hdr, text=f"  {done}/{total} completati",
                 font=("DM Sans",11), fg=TC["muted"], bg=TC["surface"]).pack(side="left")
        tk.Button(step_hdr, text="🗑",
                  command=lambda s=step: self._delete_step(project, s["id"]),
                  font=("DM Sans",10), fg=TC["red"], bg=TC["surface"],
                  relief="flat", cursor="hand2").pack(side="right", padx=4)

        # Task
        for task in step.get("tasks", []):
            self._render_task(content, project, step, task)

        # Aggiungi task
        add_row = tk.Frame(content, bg=TC["surface"])
        add_row.pack(fill="x", pady=(4,0))
        entry = ctk.CTkEntry(add_row, width=320, height=28,
                             placeholder_text="Aggiungi task... (Invio)",
                             corner_radius=6)
        entry.pack(side="left")

        def _add_task(e=None, s=step):
            text = entry.get().strip()
            if not text:
                return
            s["tasks"].append({"id": uid(), "text": text, "done": False,
                                "notes": [], "note": "", "doneAt": None})
            self._save_and_refresh(project)

        entry.bind("<Return>", _add_task)
        tk.Button(add_row, text="+ Task", command=_add_task,
                  font=("DM Sans",10), fg=TC["blue"], bg=TC["surface"],
                  relief="flat", cursor="hand2").pack(side="left", padx=6)

    def _render_task(self, parent, project, step, task):
        is_next_step, is_next_task = get_next_task(project)
        is_next = (is_next_task is not None and is_next_task.get("id") == task.get("id"))
        bg = "#FFF4E8" if is_next else TC["surface"]

        row = tk.Frame(parent, bg=bg, bd=0)
        row.pack(fill="x", pady=2)

        # Indicatore prossimo
        if is_next:
            tk.Label(row, text="📍", bg=bg, font=("Arial",11)).pack(side="left", padx=(0,4))

        # Checkbox
        check_var = tk.BooleanVar(value=task.get("done", False))
        def _toggle(t=task, p=project):
            t["done"] = not t.get("done", False)
            t["doneAt"] = datetime.now().isoformat()[:10] if t["done"] else None
            self._save_and_refresh(p)
        check = tk.Checkbutton(row, variable=check_var, command=_toggle,
                               bg=bg, activebackground=bg, cursor="hand2",
                               relief="flat", borderwidth=0)
        check.pack(side="left")

        # Testo task
        text_color = TC["muted"] if task.get("done") else TC["text"]
        font_style = ("DM Sans",12) if task.get("done") else ("DM Sans",12)
        tk.Label(row, text=("✓ " if task.get("done") else "") + task.get("text",""),
                 font=font_style, fg=text_color, bg=bg).pack(side="left", padx=4)

        # Data completamento
        if task.get("done") and task.get("doneAt"):
            tk.Label(row, text=task["doneAt"][:10],
                     font=("DM Sans",10), fg=TC["muted"], bg=bg).pack(side="left", padx=4)

        # Elimina task
        tk.Button(row, text="✕",
                  command=lambda t=task, s=step, p=project: self._delete_task(p, s["id"], t["id"]),
                  font=("DM Sans",9), fg=TC["muted"], bg=bg,
                  relief="flat", cursor="hand2").pack(side="right", padx=4)

        # Note (mostra se presenti)
        notes = task.get("notes", [])
        if isinstance(task.get("note"), str) and task.get("note") and not notes:
            notes = [{"id": f"legacy_{task['id']}", "text": task["note"], "createdAt": ""}]

        for note in notes:
            note_row = tk.Frame(parent, bg="#FFF4E8", bd=0)
            note_row.pack(fill="x", padx=(32,0), pady=1)
            tk.Label(note_row, text=f"💬 {note['text']}",
                     font=("DM Sans",10,"italic"), fg=TC["accent"], bg="#FFF4E8").pack(side="left", padx=8)

        # FresaturaPanel se il task è "fresatura"
        if task.get("text","").strip().lower() == "fresatura":
            self._render_fresatura_panel(parent, project, step, task)

    def _render_fresatura_panel(self, parent, project, step, task):
        programs = task.get("programs", [])
        fres_pgm = [p for p in programs if p.get("tipoGruppo") != "ipm"]
        done_tot  = sum(1 for p in programs if p.get("stato") == "completato")
        in_mac    = sum(1 for p in programs if p.get("stato") == "in_macchina")
        total     = len(programs)

        panel = tk.Frame(parent, bg="#EAF1FB", bd=0)
        panel.pack(fill="x", padx=(32,0), pady=(4,8))

        # Header
        ph = tk.Frame(panel, bg="#EAF1FB")
        ph.pack(fill="x", padx=10, pady=6)
        tk.Label(ph, text="⚙️ PROGRAMMI FRESATURA",
                 font=("DM Sans",10,"bold"), fg=TC["blue"], bg="#EAF1FB").pack(side="left")
        if in_mac > 0:
            tk.Label(ph, text=f"⚙ {in_mac} in macchina",
                     font=("DM Sans",10,"bold"), fg=TC["blue"], bg="#EAF1FB").pack(side="left", padx=8)
        if total > 0:
            color = TC["green"] if done_tot == total else TC["blue"]
            tk.Label(ph, text=f"{done_tot}/{total} completati",
                     font=("DM Sans",10,"bold"), fg=color, bg="#EAF1FB").pack(side="left")

        # Pulsante carica MPF
        def _carica_mpf():
            files = fd.askopenfilenames(
                title="Carica file MPF",
                filetypes=[("Programmi MPF", "*.MPF *.mpf"), ("Tutti", "*.*")])
            for fpath in files:
                fname = os.path.basename(fpath)
                if not any(p.get("filename") == fname for p in programs):
                    programs.append({
                        "id": uid(), "filename": fname,
                        "numPgm": fname.replace(".MPF","").replace(".mpf","").split("_")[-1],
                        "tipoGruppo": "fresatura", "utensile": "", "diametro": "",
                        "tipoOp": "", "dataPost": "", "stato": "da_fare",
                        "operatore": "", "tempoStimato": "",
                        "tempoInizio": None, "tempoFine": None,
                    })
            task["programs"] = programs
            self._save_and_refresh(project)

        tk.Button(ph, text="📂 Carica .MPF", command=_carica_mpf,
                  font=("DM Sans",10,"bold"), fg="#fff", bg=TC["blue"],
                  relief="flat", padx=8, pady=3, cursor="hand2").pack(side="right")

        # Lista programmi
        for pgm in fres_pgm:
            self._render_program_row(panel, project, task, pgm, programs)

    def _render_program_row(self, parent, project, task, pgm, programs):
        stato     = pgm.get("stato", "da_fare")
        cfg_label, cfg_color, cfg_bg = STATO_CFG.get(stato, STATO_CFG["da_fare"])

        row = tk.Frame(parent, bg=cfg_bg, bd=0)
        row.pack(fill="x", padx=6, pady=2)

        # Bottone stato (click avanza)
        def _adv(p=pgm):
            p["stato"] = STATO_NEXT[p.get("stato","da_fare")]
            if p["stato"] == "in_macchina" and not p.get("tempoInizio"):
                p["tempoInizio"] = now_str()
            elif p["stato"] == "completato":
                p["tempoFine"] = now_str()
            task["programs"] = programs
            all_done = programs and all(x.get("stato")=="completato" for x in programs)
            task["done"] = all_done
            task["doneAt"] = datetime.now().isoformat()[:10] if all_done else None
            self._save_and_refresh(project)

        tk.Button(row, text=cfg_label, command=_adv,
                  font=("DM Sans",10,"bold"), fg=cfg_color, bg=cfg_bg,
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  width=12).pack(side="left", padx=(6,4))

        # Info
        tk.Label(row, text=pgm.get("numPgm",""),
                 font=("Consolas",10,"bold"), fg=TC["blue"], bg=cfg_bg, width=5).pack(side="left")
        tk.Label(row, text=pgm.get("utensile","—"),
                 font=("Consolas",10), fg=TC["text"], bg=cfg_bg, width=18, anchor="w").pack(side="left")
        tk.Label(row, text=(pgm.get("tipoOp","—") or "—")[:40],
                 font=("DM Sans",10), fg=TC["sub"], bg=cfg_bg).pack(side="left", padx=4)

        # Timestamp
        if pgm.get("tempoInizio"):
            tk.Label(row, text=f"▶{pgm['tempoInizio']}",
                     font=("Consolas",9), fg=TC["blue"], bg=cfg_bg).pack(side="right", padx=4)
        if pgm.get("tempoFine"):
            tk.Label(row, text=f"■{pgm['tempoFine']}",
                     font=("Consolas",9), fg=TC["green"], bg=cfg_bg).pack(side="right", padx=4)

    # ── Log ────────────────────────────────────────────────────────────────────

    def _render_log(self, parent, project):
        log = project.get("log", [])

        # Area log
        log_frame = ctk.CTkScrollableFrame(parent, fg_color=TC["bg"],
                                            height=300, corner_radius=6)
        log_frame.pack(fill="both", expand=True, pady=(0,10))

        if not log:
            ctk.CTkLabel(log_frame, text="Nessun aggiornamento ancora.",
                         font=("DM Sans",13), text_color=TC["muted"]).pack(pady=30)
        for entry in log:
            ef = tk.Frame(log_frame, bg=TC["surface"], bd=0)
            ef.pack(fill="x", pady=3)
            tk.Frame(ef, width=3, bg=project.get("color", TC["accent"])).pack(side="left", fill="y")
            ec = tk.Frame(ef, bg=TC["surface"])
            ec.pack(side="left", fill="both", expand=True, padx=10, pady=8)
            tk.Label(ec, text=f"{entry.get('user','?')}   {entry.get('time','')}",
                     font=("DM Sans",10,"bold"),
                     fg=project.get("color", TC["accent"]), bg=TC["surface"]).pack(anchor="w")
            tk.Label(ec, text=entry.get("text",""),
                     font=("DM Sans",12), fg=TC["text"], bg=TC["surface"],
                     wraplength=500, justify="left").pack(anchor="w")

        # Aggiungi aggiornamento
        add_frame = ctk.CTkFrame(parent, fg_color=TC["surface"], corner_radius=8)
        add_frame.pack(fill="x")
        user_entry = ctk.CTkEntry(add_frame, width=90, height=34, placeholder_text="Tu",
                                  font=("DM Sans",12), corner_radius=6)
        user_entry.pack(side="left", padx=(10,4), pady=8)
        text_entry = ctk.CTkEntry(add_frame, height=34,
                                  placeholder_text="Scrivi un aggiornamento...",
                                  font=("DM Sans",12), corner_radius=6)
        text_entry.pack(side="left", fill="x", expand=True, padx=4, pady=8)

        def _add_log(e=None):
            text = text_entry.get().strip()
            if not text:
                return
            project.setdefault("log", []).append({
                "id": uid(),
                "user": user_entry.get().strip() or "Tu",
                "text": text,
                "time": now_str(),
            })
            self._save_and_refresh(project)

        text_entry.bind("<Return>", _add_log)
        ctk.CTkButton(add_frame, text="→", command=_add_log,
                      fg_color=project.get("color", TC["accent"]),
                      font=("DM Sans",13,"bold"), height=34, width=40,
                      corner_radius=6).pack(side="right", padx=10, pady=8)

    # ── Backup ─────────────────────────────────────────────────────────────────

    def _render_backup(self):
        ctk.CTkLabel(self._body, text="💾 Backup & Importazione",
                     font=("DM Sans",18,"bold"),
                     text_color=TC["text"]).pack(anchor="w", padx=28, pady=(20,4))
        ctk.CTkLabel(self._body, text="Importa un backup da WorkTrack standalone o esporta i dati correnti.",
                     font=("DM Sans",12), text_color=TC["muted"]).pack(anchor="w", padx=28, pady=(0,20))

        # Import
        imp_frame = ctk.CTkFrame(self._body, fg_color=TC["surface"],
                                  corner_radius=10)
        imp_frame.pack(fill="x", padx=24, pady=(0,12))
        ctk.CTkLabel(imp_frame, text="📥 Importa backup",
                     font=("DM Sans",14,"bold"), text_color=TC["text"]).pack(anchor="w", padx=16, pady=(14,4))
        ctk.CTkLabel(imp_frame, text="Carica un file .json esportato da WorkTrack o da DMGDesk.",
                     font=("DM Sans",11), text_color=TC["muted"]).pack(anchor="w", padx=16)

        self._import_status = ctk.CTkLabel(imp_frame, text="",
                                            font=("DM Sans",11), text_color=TC["green"])
        self._import_status.pack(anchor="w", padx=16, pady=(4,0))

        btn_row = ctk.CTkFrame(imp_frame, fg_color="transparent")
        btn_row.pack(anchor="w", padx=16, pady=12)
        ctk.CTkButton(btn_row, text="+ Importa (merge)", command=lambda: self._import_file("merge"),
                      fg_color=TC["accent"], hover_color="#B5600A",
                      font=("DM Sans",11,"bold"), height=32, corner_radius=6).pack(side="left", padx=(0,8))
        ctk.CTkButton(btn_row, text="Sostituisci tutto", command=lambda: self._import_file("replace"),
                      fg_color="transparent", hover_color=TC["surface2"],
                      border_width=1, border_color=TC["border"],
                      text_color=TC["sub"],
                      font=("DM Sans",11), height=32, corner_radius=6).pack(side="left")

        ctk.CTkLabel(imp_frame,
                     text="Merge: aggiunge i progetti importati senza cancellare quelli esistenti (consigliato)\n"
                          "Sostituisci: cancella tutto e importa il backup",
                     font=("DM Sans",10), text_color=TC["muted"]).pack(anchor="w", padx=16, pady=(0,14))

        # Export
        exp_frame = ctk.CTkFrame(self._body, fg_color=TC["surface"], corner_radius=10)
        exp_frame.pack(fill="x", padx=24, pady=(0,20))
        ctk.CTkLabel(exp_frame, text="📤 Esporta backup",
                     font=("DM Sans",14,"bold"), text_color=TC["text"]).pack(anchor="w", padx=16, pady=(14,4))
        ctk.CTkLabel(exp_frame, text="Salva tutti i progetti e template come file JSON compatibile con WorkTrack.",
                     font=("DM Sans",11), text_color=TC["muted"]).pack(anchor="w", padx=16)
        ctk.CTkButton(exp_frame, text="💾 Scarica backup completo",
                      command=self._export_file,
                      fg_color=TC["blue"], hover_color="#154E9A",
                      font=("DM Sans",11,"bold"), height=32, corner_radius=6).pack(anchor="w", padx=16, pady=12)

    def _import_file(self, mode):
        path = fd.askopenfilename(
            title="Seleziona backup WorkTrack",
            filetypes=[("JSON", "*.json"), ("Tutti", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            if not d.get("_worktrack") and not d.get("_worktrack_backup"):
                raise ValueError("File non riconosciuto (manca _worktrack)")
            if not isinstance(d.get("projects"), list) or not isinstance(d.get("templates"), list):
                raise ValueError("Struttura backup non valida")

            new_projects  = d["projects"]
            new_templates = d["templates"]

            if mode == "replace":
                self._projects  = new_projects
                self._templates = new_templates
            else:
                # Merge
                existing_ids = {p["id"] for p in self._projects}
                for p in new_projects:
                    if p["id"] in existing_ids:
                        self._projects = [p if x["id"]==p["id"] else x for x in self._projects]
                    else:
                        self._projects.append(p)
                existing_tmpl_ids = {t["id"] for t in self._templates}
                for t in new_templates:
                    if t["id"] in existing_tmpl_ids:
                        self._templates = [t if x["id"]==t["id"] else x for x in self._templates]
                    else:
                        self._templates.append(t)

            _save_progetti(self._projects)
            _save_templates(self._templates)

            msg = f"✓ {len(new_projects)} progetti e {len(new_templates)} template importati ({mode})"
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
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            payload = {
                "_worktrack": True,
                "version": 2,
                "exportedAt": datetime.now().isoformat(),
                "label": f"Backup DMGDesk {datetime.now().strftime('%Y-%m-%d')}",
                "projects": self._projects,
                "templates": self._templates,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            mb.showinfo("Export completato", f"Backup salvato in:\n{path}")
        except Exception as e:
            mb.showerror("Errore export", str(e))

    # ══════════════════════════════════════════════════════════════════════════
    # Azioni
    # ══════════════════════════════════════════════════════════════════════════

    def _save_and_refresh(self, project):
        self._projects = [project if p["id"]==project["id"] else p for p in self._projects]
        threading.Thread(target=lambda: _save_progetti(self._projects), daemon=True).start()
        self.parent.after(0, self._refresh)

    def _set_pallet(self, project, value):
        project["pallet_assegnato"] = None if value == "—" else int(value)
        self._save_and_refresh(project)

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
        self._save_and_refresh(project)

    def _delete_task(self, project, step_id, task_id):
        for s in project.get("steps", []):
            if s["id"] == step_id:
                s["tasks"] = [t for t in s.get("tasks",[]) if t["id"] != task_id]
        self._save_and_refresh(project)

    def _lancia_nc(self, project):
        mpf = get_mpf_list(project)
        if not mpf:
            return
        cfg = _carica_config()
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
                nome = project.get("name","").upper().replace(" ","_")[:20]
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
        from tkinter.simpledialog import askstring
        nome = askstring("Nuovo Progetto", "Nome commessa / progetto:", parent=self.parent)
        if not nome or not nome.strip():
            return
        # Scelta template
        templates = self._templates
        steps = []
        if templates:
            tmpl_names = ["(vuoto)"] + [t["name"] for t in templates]
            choice = self._choose_template(tmpl_names)
            if choice and choice != "(vuoto)":
                tmpl = next((t for t in templates if t["name"]==choice), None)
                if tmpl:
                    steps = [{"id":uid(),"title":s["title"],
                              "tasks":[{"id":uid(),"text":t["text"],"done":False,
                                        "notes":[],"note":"","doneAt":None}
                                       for t in s.get("tasks",[])]}
                             for s in tmpl.get("steps",[])]

        project = {"id": uid(), "name": nome.strip(), "description": "",
                   "color": "#D4700A", "steps": steps,
                   "createdAt": datetime.now().isoformat()[:10],
                   "archived": False, "pallet_assegnato": None, "log": []}
        self._projects.append(project)
        _save_progetti(self._projects)
        self._selected_id = project["id"]
        self._refresh()

    def _choose_template(self, options):
        """Dialog semplice per scegliere un template."""
        result = [None]
        win = tk.Toplevel(self.parent)
        win.title("Scegli template")
        win.geometry("320x280")
        win.grab_set()
        tk.Label(win, text="Seleziona un template:", font=("DM Sans",12,"bold")).pack(pady=12)
        lb = tk.Listbox(win, font=("DM Sans",12), height=8)
        lb.pack(fill="both", expand=True, padx=20)
        for opt in options:
            lb.insert("end", opt)
        lb.selection_set(0)
        def _ok():
            sel = lb.curselection()
            result[0] = options[sel[0]] if sel else None
            win.destroy()
        tk.Button(win, text="OK", command=_ok, font=("DM Sans",11,"bold"),
                  bg=TC["accent"], fg="#fff", relief="flat", padx=20, pady=6).pack(pady=10)
        win.wait_window()
        return result[0]

    def refresh(self):
        self._load()
