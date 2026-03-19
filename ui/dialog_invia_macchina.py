"""
Dialog "Invia alla Macchina" - Tab Analisi NC
Riceve la lista esatta di file da inviare (analizzati + MAIN).
Controlla quali esistono già, chiede conferma, invia.
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import configparser

from machine_client import MachineClient

# ─── Config IP/porta ──────────────────────────────────────────────────────────
CLIENT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "client_config.ini")
DEFAULT_IP    = "10.95.20.29"
DEFAULT_PORT  = 9999


def carica_client_config():
    cfg = configparser.ConfigParser()
    if not os.path.exists(CLIENT_CONFIG):
        cfg["macchina"] = {"ip": DEFAULT_IP, "port": str(DEFAULT_PORT)}
        with open(CLIENT_CONFIG, "w") as f:
            cfg.write(f)
    cfg.read(CLIENT_CONFIG)
    return cfg["macchina"].get("ip", DEFAULT_IP), int(cfg["macchina"].get("port", DEFAULT_PORT))


def salva_client_config(ip, port):
    cfg = configparser.ConfigParser()
    cfg["macchina"] = {"ip": ip, "port": str(port)}
    with open(CLIENT_CONFIG, "w") as f:
        cfg.write(f)


# ─── Dialog ───────────────────────────────────────────────────────────────────
class DialogInviaMacchina(tk.Toplevel):
    """
    Riceve file_paths: lista esatta di path completi da inviare
    (file analizzati + MAIN generato).
    """

    def __init__(self, parent, file_paths, progetto):
        super().__init__(parent)
        # file_paths = lista di path assoluti
        self.file_paths   = file_paths
        self.progetto     = progetto
        self.ip, self.port = carica_client_config()

        self.title(f"Invia alla macchina  —  {progetto}")
        self.geometry("620x500")
        self.resizable(True, True)
        self.minsize(500, 380)
        self.grab_set()

        self._build_ui()
        self._controlla()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg="#1565C0")
        hdr.pack(fill="x")
        tk.Label(hdr, text="📤  Invia programmi alla macchina",
                 font=("Segoe UI", 12, "bold"), bg="#1565C0", fg="white").pack(
            side="left", padx=14, pady=8)

        # IP / porta
        cfg_frame = tk.Frame(self, bg="#E8EAF6", pady=5)
        cfg_frame.pack(fill="x", padx=10, pady=(8, 0))

        tk.Label(cfg_frame, text="IP macchina:", font=("Segoe UI", 9),
                 bg="#E8EAF6").pack(side="left", padx=(10, 4))
        self.entry_ip = tk.Entry(cfg_frame, width=14, font=("Segoe UI", 9))
        self.entry_ip.insert(0, self.ip)
        self.entry_ip.pack(side="left", padx=(0, 8))

        tk.Label(cfg_frame, text="Porta:", font=("Segoe UI", 9),
                 bg="#E8EAF6").pack(side="left", padx=(0, 4))
        self.entry_port = tk.Entry(cfg_frame, width=7, font=("Segoe UI", 9))
        self.entry_port.insert(0, str(self.port))
        self.entry_port.pack(side="left", padx=(0, 10))

        tk.Button(cfg_frame, text="💾 Salva",
                  font=("Segoe UI", 8), command=self._salva_ip).pack(side="left", padx=2)
        tk.Button(cfg_frame, text="🔄 Ricontrolla",
                  font=("Segoe UI", 8), command=self._ricontrolla).pack(side="left", padx=4)

        # Info progetto / destinazione
        dest_frame = tk.Frame(self, bg="#F5F5F5", pady=4)
        dest_frame.pack(fill="x", padx=10, pady=(6, 0))
        tk.Label(dest_frame, text=f"Progetto:      {self.progetto}",
                 font=("Segoe UI", 9), bg="#F5F5F5", anchor="w").pack(fill="x", padx=10)
        self.lbl_dest = tk.Label(dest_frame, text="Destinazione:  (verifica in corso...)",
                                  font=("Segoe UI", 9), bg="#F5F5F5", anchor="w", fg="#555")
        self.lbl_dest.pack(fill="x", padx=10)

        # Legenda
        leg = tk.Frame(self)
        leg.pack(fill="x", padx=12, pady=(6, 2))
        tk.Label(leg, text="🟢 nuovo  ", font=("Segoe UI", 8), fg="#2E7D32").pack(side="left")
        tk.Label(leg, text="🟡 già presente (verrà sovrascritto)",
                 font=("Segoe UI", 8), fg="#E65100").pack(side="left")

        # Tabella
        tbl = tk.Frame(self)
        tbl.pack(fill="both", expand=True, padx=10, pady=4)
        scroll = ttk.Scrollbar(tbl)
        scroll.pack(side="right", fill="y")

        self.tree = ttk.Treeview(tbl, columns=("tipo", "file", "dim", "stato"),
                                  show="headings", height=10,
                                  yscrollcommand=scroll.set)
        scroll.config(command=self.tree.yview)

        self.tree.heading("tipo",  text="")
        self.tree.heading("file",  text="File")
        self.tree.heading("dim",   text="Dim")
        self.tree.heading("stato", text="Stato")
        self.tree.column("tipo",  width=50,  anchor="center", stretch=False)
        self.tree.column("file",  width=260)
        self.tree.column("dim",   width=80,  anchor="center")
        self.tree.column("stato", width=160, anchor="center")

        self.tree.tag_configure("nuovo",     foreground="#2E7D32")
        self.tree.tag_configure("esistente", foreground="#E65100")
        self.tree.tag_configure("main",      foreground="#1565C0")
        self.tree.tag_configure("errore",    foreground="#C62828")
        self.tree.pack(fill="both", expand=True)

        # Stato + progress
        self.lbl_stato = tk.Label(self, text="⏳ Verifica connessione...",
                                   font=("Segoe UI", 9), fg="#1565C0", anchor="w")
        self.lbl_stato.pack(fill="x", padx=12, pady=(4, 0))

        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(fill="x", padx=10, pady=(2, 6))

        # Bottoni
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=(0, 12))

        self.btn_invia = tk.Button(
            btn_frame, text="📤  INVIA ALLA MACCHINA",
            font=("Segoe UI", 10, "bold"),
            bg="#4CAF50", fg="white", activebackground="#388E3C",
            padx=16, pady=6, state="disabled",
            command=self._conferma_e_invia
        )
        self.btn_invia.pack(side="left", padx=6)

        tk.Button(btn_frame, text="Chiudi",
                  font=("Segoe UI", 9), padx=12, pady=6,
                  command=self.destroy).pack(side="left", padx=6)

    # ── Logica ────────────────────────────────────────────────────────────────
    def _get_ip_port(self):
        ip = self.entry_ip.get().strip()
        try:
            port = int(self.entry_port.get().strip())
        except ValueError:
            port = DEFAULT_PORT
        return ip, port

    def _salva_ip(self):
        ip, port = self._get_ip_port()
        salva_client_config(ip, port)
        messagebox.showinfo("Salvato", f"IP {ip}:{port} salvato.", parent=self)

    def _ricontrolla(self):
        self.tree.delete(*self.tree.get_children())
        self.lbl_stato.config(text="⏳ Verifica in corso...", fg="#1565C0")
        self.btn_invia.config(state="disabled")
        self._controlla()

    def _controlla(self):
        """Verifica sul server quali file esistono già. Usa esattamente self.file_paths."""
        filenames = [os.path.basename(fp) for fp in self.file_paths]
        threading.Thread(
            target=self._check_thread, args=(filenames,), daemon=True).start()

    def _check_thread(self, filenames):
        ip, port   = self._get_ip_port()
        client     = MachineClient(ip, port)
        esistenti, dest_dir, err = client.check_esistenti(filenames, self.progetto)
        self.after(0, lambda: self._popola(esistenti, dest_dir, err))

    def _popola(self, esistenti, dest_dir, err):
        self.tree.delete(*self.tree.get_children())

        if dest_dir:
            self.lbl_dest.config(text=f"Destinazione:  {dest_dir}")

        n_nuovi = n_esistenti = 0

        for fp in self.file_paths:
            fname = os.path.basename(fp)
            size  = f"{os.path.getsize(fp):,} B" if os.path.exists(fp) else "-"
            is_main = "MAIN" in fname.upper() or fname.upper().startswith("O9999")

            if err:
                tipo  = "📄" if not is_main else "⭐"
                stato = "⚠️ server non raggiungibile"
                tag   = "errore"
            elif fname in esistenti:
                tipo  = "📄" if not is_main else "⭐"
                stato = "🟡 già presente"
                tag   = "esistente"
                n_esistenti += 1
            else:
                tipo  = "📄" if not is_main else "⭐"
                stato = "🟢 nuovo"
                tag   = "main" if is_main else "nuovo"
                n_nuovi += 1

            self.tree.insert("", "end", values=(tipo, fname, size, stato), tags=(tag,))

        if err:
            self.lbl_stato.config(
                text=f"❌ Server non raggiungibile: {err}", fg="#C62828")
            self.btn_invia.config(state="disabled")
        else:
            tot = len(self.file_paths)
            msg = f"✅ {tot} file pronti"
            if n_esistenti:
                msg += f"  —  {n_nuovi} nuovi, {n_esistenti} da sovrascrivere"
            self.lbl_stato.config(text=msg, fg="#333")
            self.btn_invia.config(state="normal")

    def _conferma_e_invia(self):
        esistenti_in_lista = [
            self.tree.item(i)["values"][1]
            for i in self.tree.get_children()
            if "già presente" in str(self.tree.item(i)["values"][3])
        ]

        if esistenti_in_lista:
            lista_str = "\n".join(f"  • {f}" for f in esistenti_in_lista)
            if not messagebox.askyesno(
                    "Conferma sovrascrittura",
                    f"Questi file esistono già nella macchina\n"
                    f"e verranno sovrascritti:\n\n{lista_str}\n\n"
                    f"Procedere?", parent=self):
                return
        else:
            if not messagebox.askyesno(
                    "Conferma invio",
                    f"Inviare {len(self.file_paths)} file alla macchina?\n"
                    f"Progetto: {self.progetto}", parent=self):
                return

        self.btn_invia.config(state="disabled", text="⏳ Invio in corso...")
        self.progress["maximum"] = len(self.file_paths)
        self.progress["value"]   = 0
        threading.Thread(target=self._invia_thread, daemon=True).start()

    def _invia_thread(self):
        ip, port = self._get_ip_port()
        client   = MachineClient(ip, port)
        inviati  = 0

        def on_progress(filename, ok, msg):
            nonlocal inviati
            inviati += 1
            stato = "✅ inviato" if ok else f"❌ {msg}"
            def _upd():
                # Il callback può ricevere filename con o senza .MPF:
                # confronta normalizzando (senza estensione, maiuscolo)
                fn_base = filename.upper().removesuffix(".MPF")
                for item in self.tree.get_children():
                    tree_val = str(self.tree.item(item)["values"][1]).upper().removesuffix(".MPF")
                    if tree_val == fn_base:
                        vals      = list(self.tree.item(item)["values"])
                        vals[3]   = stato
                        tag       = "nuovo" if ok else "errore"
                        self.tree.item(item, values=vals, tags=(tag,))
                        break
                self.progress["value"] = inviati
                self.lbl_stato.config(
                    text=f"⏳ Invio... {inviati}/{len(self.file_paths)}")
            self.after(0, _upd)

        n_ok, n_err, errori = client.invia_lista(
            self.file_paths, self.progetto, on_progress)

        def _fine():
            if n_err == 0:
                self.lbl_stato.config(
                    text=f"✅ Completato — {n_ok} file inviati con successo",
                    fg="#2E7D32")
                self.btn_invia.config(text="✅ Completato", bg="#9E9E9E")
                messagebox.showinfo("Invio completato",
                                    f"✅ {n_ok} file inviati con successo\n"
                                    f"Progetto: {self.progetto}", parent=self)
            else:
                self.lbl_stato.config(
                    text=f"⚠️  {n_ok} ok, {n_err} errori", fg="#E65100")
                self.btn_invia.config(state="normal", text="📤  Riprova", bg="#FF7043")
                messagebox.showwarning("Invio parziale",
                                       f"{n_ok} inviati, {n_err} falliti:\n\n" +
                                       "\n".join(errori), parent=self)
        self.after(0, _fine)


# ─── Entry point ──────────────────────────────────────────────────────────────
def apri_dialog_invia(parent, file_paths, progetto):
    """
    file_paths: lista di path assoluti (file analizzati + MAIN).
    progetto:   nome del progetto (diventa sottocartella nella macchina).
    """
    dlg = DialogInviaMacchina(parent, file_paths, progetto)
    parent.wait_window(dlg)
