"""
Dialog "Invia alla Macchina" - Tab Analisi NC
Mostra la lista file da inviare, evidenzia quelli già presenti,
chiede conferma prima di sovrascrivere.
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from config.theme import get_font, COLOR_PRIMARY, COLOR_SURFACE, COLOR_PRIMARY_LIGHT
from machine_client import MachineClient


# ─── Configurazione IP server (modificabile) ──────────────────────────────────
import configparser

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
    ip   =     cfg["macchina"].get("ip",   DEFAULT_IP)
    port = int(cfg["macchina"].get("port", DEFAULT_PORT))
    return ip, port


def salva_client_config(ip, port):
    cfg = configparser.ConfigParser()
    cfg["macchina"] = {"ip": ip, "port": str(port)}
    with open(CLIENT_CONFIG, "w") as f:
        cfg.write(f)


# ─── Dialog principale ────────────────────────────────────────────────────────
class DialogInviaMacchina(tk.Toplevel):
    """
    Mostra i file MPF/SPF trovati in sorgente_dir,
    controlla quali esistono già nella macchina,
    chiede conferma e invia.
    """

    def __init__(self, parent, sorgente_dir, progetto):
        super().__init__(parent)
        self.sorgente_dir = sorgente_dir
        self.progetto     = progetto
        self.ip, self.port = carica_client_config()
        self.files_da_inviare = []   # popolato dopo check

        self.title(f"Invia alla macchina  —  {progetto}")
        self.geometry("620x520")
        self.resizable(True, True)
        self.minsize(500, 400)
        self.grab_set()

        self._build_ui()
        self._carica_e_controlla()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg="#1565C0")
        hdr.pack(fill="x")
        tk.Label(hdr, text="📤  Invia programmi alla macchina",
                 font=("Segoe UI", 12, "bold"), bg="#1565C0", fg="white").pack(
            side="left", padx=14, pady=8)

        # IP / porta configurabili
        cfg_frame = tk.Frame(self, bg="#E8EAF6", pady=5)
        cfg_frame.pack(fill="x", padx=10, pady=(8, 0))

        tk.Label(cfg_frame, text="IP macchina:", font=("Segoe UI", 9), bg="#E8EAF6").pack(
            side="left", padx=(10, 4))
        self.entry_ip = tk.Entry(cfg_frame, width=14, font=("Segoe UI", 9))
        self.entry_ip.insert(0, self.ip)
        self.entry_ip.pack(side="left", padx=(0, 10))

        tk.Label(cfg_frame, text="Porta:", font=("Segoe UI", 9), bg="#E8EAF6").pack(
            side="left", padx=(0, 4))
        self.entry_port = tk.Entry(cfg_frame, width=7, font=("Segoe UI", 9))
        self.entry_port.insert(0, str(self.port))
        self.entry_port.pack(side="left", padx=(0, 10))

        tk.Button(cfg_frame, text="🔄 Ricontrolla",
                  font=("Segoe UI", 8), command=self._ricontrolla).pack(side="left", padx=4)
        tk.Button(cfg_frame, text="💾 Salva IP",
                  font=("Segoe UI", 8), command=self._salva_ip).pack(side="left", padx=4)

        # Progetto e destinazione
        dest_frame = tk.Frame(self, bg="#F5F5F5", pady=4)
        dest_frame.pack(fill="x", padx=10, pady=(6, 0))
        tk.Label(dest_frame, text=f"Progetto:    {self.progetto}",
                 font=("Segoe UI", 9), bg="#F5F5F5", anchor="w").pack(fill="x", padx=10)
        self.lbl_dest = tk.Label(dest_frame, text="Destinazione: (verifica in corso...)",
                                  font=("Segoe UI", 9), bg="#F5F5F5", anchor="w", fg="#555")
        self.lbl_dest.pack(fill="x", padx=10)

        # Legenda
        leg = tk.Frame(self)
        leg.pack(fill="x", padx=10, pady=(6, 2))
        tk.Label(leg, text="🟡 già presente  ", font=("Segoe UI", 8), fg="#E65100").pack(side="left")
        tk.Label(leg, text="🟢 nuovo",          font=("Segoe UI", 8), fg="#2E7D32").pack(side="left")

        # Tabella file
        tbl_frame = tk.Frame(self)
        tbl_frame.pack(fill="both", expand=True, padx=10, pady=4)

        scroll = ttk.Scrollbar(tbl_frame)
        scroll.pack(side="right", fill="y")

        self.tree = ttk.Treeview(tbl_frame,
                                  columns=("file", "dim", "stato"),
                                  show="headings",
                                  height=12,
                                  yscrollcommand=scroll.set)
        scroll.config(command=self.tree.yview)

        self.tree.heading("file",  text="File")
        self.tree.heading("dim",   text="Dimensione")
        self.tree.heading("stato", text="Stato")
        self.tree.column("file",  width=280)
        self.tree.column("dim",   width=100, anchor="center")
        self.tree.column("stato", width=160, anchor="center")

        self.tree.tag_configure("nuovo",     foreground="#2E7D32")
        self.tree.tag_configure("esistente", foreground="#E65100")
        self.tree.tag_configure("errore",    foreground="#C62828")

        self.tree.pack(fill="both", expand=True)

        # Stato / progress
        self.lbl_stato = tk.Label(self, text="⏳ Verifica in corso...",
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
            padx=16, pady=6,
            state="disabled",
            command=self._conferma_e_invia
        )
        self.btn_invia.pack(side="left", padx=6)

        tk.Button(btn_frame, text="Annulla",
                  font=("Segoe UI", 9),
                  padx=12, pady=6,
                  command=self.destroy).pack(side="left", padx=6)

    # ── Logica ────────────────────────────────────────────────────────────────
    def _get_ip_port(self):
        ip   = self.entry_ip.get().strip()
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
        self._carica_e_controlla()

    def _carica_e_controlla(self):
        """Raccoglie i file MPF/SPF dalla sorgente e chiede al server quali esistono già."""
        # Raccogli file
        try:
            tutti = [
                f for f in os.listdir(self.sorgente_dir)
                if f.upper().endswith((".MPF", ".SPF"))
            ]
        except Exception as e:
            self.lbl_stato.config(text=f"❌ Errore lettura cartella: {e}", fg="#C62828")
            return

        if not tutti:
            self.lbl_stato.config(text="⚠️  Nessun file .MPF/.SPF trovato in P:\\", fg="#E65100")
            return

        self.files_trovati = tutti

        # Contatta il server in background
        threading.Thread(target=self._check_thread, daemon=True).start()

    def _check_thread(self):
        ip, port = self._get_ip_port()
        client   = MachineClient(ip, port)
        esistenti, dest_dir, err = client.check_esistenti(self.files_trovati, self.progetto)

        self.after(0, lambda: self._popola_tabella(esistenti, dest_dir, err))

    def _popola_tabella(self, esistenti, dest_dir, err):
        self.tree.delete(*self.tree.get_children())

        if err:
            self.lbl_stato.config(
                text=f"❌ Impossibile contattare il server: {err}", fg="#C62828")
            # Mostra comunque i file ma senza info esistenza
            for fname in self.files_trovati:
                fp   = os.path.join(self.sorgente_dir, fname)
                size = f"{os.path.getsize(fp)} B" if os.path.exists(fp) else "-"
                self.tree.insert("", "end", values=(fname, size, "⚠️ server non raggiungibile"),
                                 tags=("errore",))
            self.btn_invia.config(state="disabled")
            return

        if dest_dir:
            self.lbl_dest.config(text=f"Destinazione: {dest_dir}")

        self.files_da_inviare = []
        n_nuovi = n_esistenti = 0

        for fname in self.files_trovati:
            fp    = os.path.join(self.sorgente_dir, fname)
            size  = f"{os.path.getsize(fp):,} B" if os.path.exists(fp) else "-"
            if fname in esistenti:
                stato = "🟡 già presente"
                tag   = "esistente"
                n_esistenti += 1
            else:
                stato = "🟢 nuovo"
                tag   = "nuovo"
                n_nuovi += 1
            self.tree.insert("", "end", values=(fname, size, stato), tags=(tag,))
            self.files_da_inviare.append(fp)

        riepilogo = f"✅ {len(self.files_trovati)} file trovati"
        if n_esistenti:
            riepilogo += f"  —  {n_nuovi} nuovi, {n_esistenti} già presenti (verranno sovrascritti se confermato)"
        self.lbl_stato.config(text=riepilogo, fg="#333")
        self.btn_invia.config(state="normal" if self.files_da_inviare else "disabled")

    def _conferma_e_invia(self):
        """Chiede conferma (specialmente se ci sono file esistenti) poi invia."""
        esistenti_in_lista = [
            self.tree.item(i)["values"][0]
            for i in self.tree.get_children()
            if "già presente" in str(self.tree.item(i)["values"][2])
        ]

        if esistenti_in_lista:
            lista_str = "\n".join(f"  • {f}" for f in esistenti_in_lista)
            ok = messagebox.askyesno(
                "Conferma sovrascrittura",
                f"I seguenti file esistono già nella macchina\n"
                f"e verranno sovrascritti:\n\n{lista_str}\n\n"
                f"Procedere con l'invio?",
                parent=self
            )
            if not ok:
                return
        else:
            ok = messagebox.askyesno(
                "Conferma invio",
                f"Inviare {len(self.files_da_inviare)} file alla macchina?\n\n"
                f"Progetto: {self.progetto}",
                parent=self
            )
            if not ok:
                return

        self.btn_invia.config(state="disabled", text="⏳ Invio in corso...")
        self.progress["maximum"] = len(self.files_da_inviare)
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
            # Aggiorna riga nella tabella
            def _upd():
                for item in self.tree.get_children():
                    if self.tree.item(item)["values"][0] == filename:
                        vals = list(self.tree.item(item)["values"])
                        vals[2] = stato
                        self.tree.item(item, values=vals,
                                       tags=("nuovo" if ok else "errore",))
                        break
                self.progress["value"] = inviati
                self.lbl_stato.config(
                    text=f"⏳ Invio... {inviati}/{len(self.files_da_inviare)}")
            self.after(0, _upd)

        n_ok, n_err, errori = client.invia_lista(
            self.files_da_inviare, self.progetto, on_progress)

        def _fine():
            if n_err == 0:
                self.lbl_stato.config(
                    text=f"✅ Invio completato — {n_ok} file inviati con successo", fg="#2E7D32")
                self.btn_invia.config(text="✅ Completato", bg="#9E9E9E")
                messagebox.showinfo("Invio completato",
                                    f"✅ {n_ok} file inviati con successo\n"
                                    f"nella macchina — progetto: {self.progetto}",
                                    parent=self)
            else:
                self.lbl_stato.config(
                    text=f"⚠️  {n_ok} ok, {n_err} errori", fg="#E65100")
                self.btn_invia.config(state="normal", text="📤  Riprova",
                                      bg="#FF7043")
                messagebox.showwarning("Invio parziale",
                                       f"{n_ok} file inviati, {n_err} falliti:\n\n" +
                                       "\n".join(errori),
                                       parent=self)
        self.after(0, _fine)


# ─── Funzione di accesso rapido ───────────────────────────────────────────────
def apri_dialog_invia(parent, sorgente_dir, progetto):
    """Apre il dialog. Chiamata da tab_analisi_nc."""
    dlg = DialogInviaMacchina(parent, sorgente_dir, progetto)
    parent.wait_window(dlg)
