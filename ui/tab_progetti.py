"""Tab Progetti — integrazione WorkTrack in DMGDesk desktop"""

import customtkinter as ctk
import tkinter as tk
import tkinter.ttk as ttk
import json, threading, os, sys
from pathlib import Path
from datetime import datetime

from config.theme import *
from config.constants import *


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


def _progetti_path() -> Path:
    cfg = _carica_config()
    base = (cfg.get("tools_toa_folder") or "").strip()
    return Path(base) / "worktrack_projects.json" if base else None


def _load_progetti() -> list:
    path = _progetti_path()
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("projects", [])
        except Exception:
            pass
    return []


def _save_progetto(project: dict):
    path = _progetti_path()
    if not path:
        return
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = {"projects": []}
        projects = data.get("projects", [])
        idx = next((i for i, p in enumerate(projects) if p.get("id") == project.get("id")), None)
        if idx is not None:
            projects[idx] = project
        else:
            projects.append(project)
        data["projects"] = projects
        data["ultimo_aggiornamento"] = datetime.now().isoformat()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Errore salvataggio progetto: {e}")


def _get_progress(project: dict) -> int:
    tasks = [t for s in project.get("steps", []) for t in s.get("tasks", [])]
    if not tasks:
        return 0
    done = sum(1 for t in tasks if t.get("done"))
    return round(done / len(tasks) * 100)


def _get_mpf_list(project: dict) -> list:
    mpf = []
    for step in project.get("steps", []):
        for task in step.get("tasks", []):
            if task.get("text", "").strip().lower() == "fresatura":
                for pgm in task.get("programs", []):
                    if pgm.get("tipoGruppo") != "ipm":
                        mpf.append(pgm)
    return mpf


class TabProgetti:
    """Tab Progetti — visualizza e gestisce i progetti WorkTrack."""

    def __init__(self, parent, main_window):
        self.parent = parent
        self.main   = main_window
        self._projects = []
        self._selected_id = None
        self._create_ui()
        self._load()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _create_ui(self):
        # Toolbar
        toolbar = ctk.CTkFrame(self.parent, fg_color="white", height=52)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        left = ctk.CTkFrame(toolbar, fg_color="transparent")
        left.pack(side="left", padx=12, pady=8)

        ctk.CTkButton(left, text="+ Nuovo",
            command=self._nuovo_progetto,
            fg_color=COLOR_PRIMARY, hover_color="#1565C0",
            font=get_font("medium", bold=True), height=34, width=90, corner_radius=6
        ).pack(side="left", padx=(0, 8))

        self.entry_search = ctk.CTkEntry(left, width=200, height=34,
            placeholder_text="Cerca progetto...", corner_radius=6)
        self.entry_search.pack(side="left")
        self.entry_search.bind("<KeyRelease>", lambda e: self._refresh_lista())

        ctk.CTkButton(toolbar, text="↻ Aggiorna",
            command=self._load,
            fg_color="transparent", hover_color="#F5F5F5",
            text_color="#90A4AE", border_width=1, border_color="#E0E0E0",
            font=get_font("small"), height=30, width=80, corner_radius=6
        ).pack(side="right", padx=12, pady=10)

        sep = ctk.CTkFrame(self.parent, fg_color="#E8EDF2", height=1)
        sep.pack(fill="x")

        # Corpo: lista sinistra + dettaglio destra
        body = ctk.CTkFrame(self.parent, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=10)

        # ── Lista progetti (sinistra) ──────────────────────────────────────
        pnl_sx = ctk.CTkFrame(body, fg_color="white", corner_radius=10,
            border_width=1, border_color="#E0E6ED", width=300)
        pnl_sx.pack(side="left", fill="y", padx=(0, 8))
        pnl_sx.pack_propagate(False)

        hdr = ctk.CTkFrame(pnl_sx, fg_color="#F5F7FA", corner_radius=0, height=34)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="Progetti", font=get_font("small", bold=True),
            text_color="#546E7A").pack(side="left", padx=12, pady=8)
        self.lbl_count = ctk.CTkLabel(hdr, text="", font=get_font("small"),
            text_color="#90A4AE")
        self.lbl_count.pack(side="right", padx=8)

        list_wrap = ctk.CTkFrame(pnl_sx, fg_color="transparent")
        list_wrap.pack(fill="both", expand=True, padx=6, pady=6)

        sb = ttk.Scrollbar(list_wrap)
        sb.pack(side="right", fill="y")

        self.lb = tk.Listbox(list_wrap,
            font=("Segoe UI", 11), bg="white", fg="#37474F",
            selectbackground="#E3F2FD", selectforeground="#1565C0",
            relief="flat", bd=0, highlightthickness=0,
            yscrollcommand=sb.set, activestyle="none")
        self.lb.pack(fill="both", expand=True)
        sb.config(command=self.lb.yview)
        self.lb.bind("<<ListboxSelect>>", self._on_select)

        # ── Dettaglio progetto (destra) ────────────────────────────────────
        self.pnl_dx = ctk.CTkFrame(body, fg_color="white", corner_radius=10,
            border_width=1, border_color="#E0E6ED")
        self.pnl_dx.pack(side="left", fill="both", expand=True)

        self._show_placeholder()

    def _show_placeholder(self):
        for w in self.pnl_dx.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.pnl_dx,
            text="Seleziona un progetto dalla lista",
            font=get_font("body"), text_color="#90A4AE"
        ).pack(expand=True)

    # ── Caricamento ───────────────────────────────────────────────────────────

    def _load(self):
        def _worker():
            projects = _load_progetti()
            self.parent.after(0, lambda: self._set_projects(projects))
        threading.Thread(target=_worker, daemon=True).start()

    def _set_projects(self, projects):
        self._projects = [p for p in projects if not p.get("archived")]
        self._refresh_lista()

    def _refresh_lista(self):
        q = self.entry_search.get().strip().lower() if hasattr(self, 'entry_search') else ""
        filtered = [p for p in self._projects
                    if q == "" or q in p.get("name", "").lower()]
        self.lb.delete(0, "end")
        self._filtered = filtered
        for p in filtered:
            pct = _get_progress(p)
            mpf = _get_mpf_list(p)
            pallet_txt = f" [P{p['pallet_assegnato']}]" if p.get("pallet_assegnato") else ""
            mpf_txt = f" ⚙{len(mpf)}" if mpf else ""
            self.lb.insert("end", f"{'✓ ' if pct==100 else '  '}{p.get('name','?')}{pallet_txt}{mpf_txt}  {pct}%")
        self.lbl_count.configure(text=f"{len(filtered)}")
        # Ri-seleziona se era selezionato
        if self._selected_id:
            for i, p in enumerate(filtered):
                if p.get("id") == self._selected_id:
                    self.lb.selection_set(i)
                    self._show_detail(p)
                    break

    def _on_select(self, event=None):
        sel = self.lb.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._filtered):
            p = self._filtered[idx]
            self._selected_id = p.get("id")
            self._show_detail(p)

    # ── Dettaglio ─────────────────────────────────────────────────────────────

    def _show_detail(self, project):
        for w in self.pnl_dx.winfo_children():
            w.destroy()

        pct = _get_progress(project)
        mpf = _get_mpf_list(project)

        # Header progetto
        hdr = ctk.CTkFrame(self.pnl_dx, fg_color="#F5F7FA", corner_radius=0, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", padx=14, pady=8, fill="y")
        ctk.CTkLabel(left, text=project.get("name","?"),
            font=get_font("title", bold=True), text_color="#1A1814").pack(anchor="w")
        if project.get("description"):
            ctk.CTkLabel(left, text=project["description"],
                font=get_font("small"), text_color="#5A5750").pack(anchor="w")

        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right", padx=14)
        ctk.CTkLabel(right, text=f"{pct}%",
            font=get_font("title", bold=True),
            text_color="#22c55e" if pct==100 else COLOR_PRIMARY
        ).pack()

        # Barra progresso
        canvas = tk.Canvas(self.pnl_dx, height=4, bg="#E8EDF2", highlightthickness=0)
        canvas.pack(fill="x")
        canvas.update_idletasks()
        w = canvas.winfo_width()
        if w > 0:
            fill_color = "#22c55e" if pct==100 else "#2196F3"
            canvas.create_rectangle(0, 0, int(w * pct / 100), 4, fill=fill_color, outline="")

        # Pulsanti azione
        action_bar = ctk.CTkFrame(self.pnl_dx, fg_color="transparent")
        action_bar.pack(fill="x", padx=14, pady=8)

        # Pallet
        ctk.CTkLabel(action_bar, text="Pallet:", font=get_font("small"),
            text_color="#90A4AE").pack(side="left", padx=(0,4))
        pallet_var = tk.StringVar(value=str(project.get("pallet_assegnato","—")))
        pallet_menu = ctk.CTkOptionMenu(
            action_bar,
            values=["—","1","2","3","4","5","6"],
            variable=pallet_var,
            command=lambda v: self._set_pallet(project, v),
            width=70, height=28, font=get_font("small")
        )
        pallet_menu.pack(side="left", padx=(0,12))

        # Lancia in NC
        if mpf:
            ctk.CTkButton(action_bar, text=f"📄 Lancia {len(mpf)} file in NC →",
                command=lambda: self._lancia_nc(project),
                fg_color=COLOR_PRIMARY, hover_color="#1565C0",
                font=get_font("medium", bold=True), height=32, corner_radius=6
            ).pack(side="left")

        # Elimina
        ctk.CTkButton(action_bar, text="🗑",
            command=lambda: self._elimina(project),
            fg_color="transparent", hover_color="#FFEBEE",
            text_color="#EF5350", border_width=1, border_color="#FFCDD2",
            font=get_font("small"), height=28, width=32, corner_radius=6
        ).pack(side="right")

        # Scrollable area step/task
        scroll_frame = ctk.CTkScrollableFrame(self.pnl_dx, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=12, pady=(0,10))

        for step in project.get("steps", []):
            # Step header
            step_hdr = ctk.CTkFrame(scroll_frame, fg_color="#F0F4F8", corner_radius=6, height=28)
            step_hdr.pack(fill="x", pady=(8,2))
            step_hdr.pack_propagate(False)
            ctk.CTkLabel(step_hdr, text=step.get("title",""),
                font=get_font("small", bold=True), text_color="#546E7A"
            ).pack(side="left", padx=10, pady=4)
            done_count = sum(1 for t in step.get("tasks",[]) if t.get("done"))
            total = len(step.get("tasks",[]))
            ctk.CTkLabel(step_hdr, text=f"{done_count}/{total}",
                font=get_font("small"), text_color="#90A4AE"
            ).pack(side="right", padx=10)

            # Task
            for task in step.get("tasks", []):
                self._task_row(scroll_frame, project, step, task)

    def _task_row(self, parent, project, step, task):
        row = ctk.CTkFrame(parent, fg_color="white", corner_radius=6, height=30)
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)

        done = task.get("done", False)
        color = "#22c55e" if done else "#B0BEC5"
        text_color = "#90A4AE" if done else "#37474F"

        # Checkbox
        check = tk.Canvas(row, width=16, height=16, bg="white", highlightthickness=0)
        check.pack(side="left", padx=(10,6), pady=7)
        if done:
            check.create_rectangle(0,0,16,16, fill="#22c55e", outline="")
            check.create_text(8,8, text="✓", fill="white", font=("Segoe UI",9,"bold"))
        else:
            check.create_rectangle(0,0,15,15, outline="#B0BEC5", width=1.5)

        def _toggle(p=project, s=step, t=task):
            t["done"] = not t.get("done", False)
            t["doneAt"] = datetime.now().isoformat()[:10] if t["done"] else None
            threading.Thread(target=lambda: _save_progetto(p), daemon=True).start()
            self._show_detail(p)
            self._refresh_lista()
        check.bind("<Button-1>", lambda e: _toggle())

        # Testo
        lbl = ctk.CTkLabel(row, text=task.get("text",""),
            font=get_font("normal"), text_color=text_color, anchor="w")
        lbl.pack(side="left", fill="x", expand=True, padx=4)
        if done and task.get("doneAt"):
            ctk.CTkLabel(row, text=task["doneAt"][:10],
                font=get_font("small"), text_color="#B0BEC5"
            ).pack(side="right", padx=8)

    # ── Azioni ────────────────────────────────────────────────────────────────

    def _set_pallet(self, project, value):
        project["pallet_assegnato"] = None if value == "—" else int(value)
        threading.Thread(target=lambda: _save_progetto(project), daemon=True).start()
        self._refresh_lista()

    def _lancia_nc(self, project):
        """Passa i file MPF al tab Analisi NC."""
        mpf = _get_mpf_list(project)
        if not mpf:
            return
        # Trova i file MPF su disco tramite percorso_nc_base
        cfg = _carica_config()
        base_nc = (cfg.get("percorso_nc_base") or "").strip()
        filenames = [p.get("filename","") for p in mpf if p.get("filename")]

        # Tenta di trovare i file nella cartella NC
        found_paths = []
        if base_nc:
            for fn in filenames:
                candidate = Path(base_nc) / fn
                if candidate.exists():
                    found_paths.append(str(candidate))

        if found_paths:
            # Passa direttamente i path al tab NC
            try:
                nc_tab = self.main.tab_analisi_nc
                nc_tab.file_paths.extend(found_paths)
                nc_tab._aggiorna_lista()
                nc_tab._confronta()
                # Imposta nome cartella
                nome = project.get("name","").upper().replace(" ","_").replace("/","_")
                nc_tab.entry_nome.delete(0,"end")
                nc_tab.entry_nome.insert(0, nome)
                # Switcha al tab NC
                self.main.tabview.set("Analisi NC")
                tk.messagebox.showinfo("Caricato",
                    f"{len(found_paths)} file MPF caricati in Analisi NC")
            except Exception as e:
                tk.messagebox.showerror("Errore", str(e))
        else:
            tk.messagebox.showwarning("File non trovati",
                f"File MPF non trovati in:\n{base_nc}\n\n"
                f"File attesi:\n" + "\n".join(filenames[:5]))

    def _nuovo_progetto(self):
        from tkinter.simpledialog import askstring
        import tkinter.messagebox as mb
        nome = askstring("Nuovo Progetto", "Nome commessa / progetto:", parent=self.parent)
        if not nome or not nome.strip():
            return
        project = {
            "id": f"p{int(datetime.now().timestamp())}",
            "name": nome.strip(),
            "description": "",
            "color": "#2196F3",
            "steps": [],
            "createdAt": datetime.now().isoformat()[:10],
            "archived": False,
            "pallet_assegnato": None,
            "log": []
        }
        self._projects.append(project)
        threading.Thread(target=lambda: _save_progetto(project), daemon=True).start()
        self._refresh_lista()
        self._selected_id = project["id"]
        self._show_detail(project)

    def _elimina(self, project):
        import tkinter.messagebox as mb
        if not mb.askyesno("Elimina", f"Eliminare '{project.get('name')}'?", parent=self.parent):
            return
        path = _progetti_path()
        if path:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["projects"] = [p for p in data.get("projects",[]) if p.get("id") != project.get("id")]
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
        self._projects = [p for p in self._projects if p.get("id") != project.get("id")]
        self._selected_id = None
        self._refresh_lista()
        self._show_placeholder()

    def refresh(self):
        self._load()
