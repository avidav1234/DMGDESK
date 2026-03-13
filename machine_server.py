"""
DMG Machine Server - Da eseguire sulla macchina CNC (o PC di test)
Riceve file dal PC operatore e li copia nella cartella di destinazione.

VERSIONE TEST:
- Cartella base default: C:\\Users\\i.dodon\\Documents\\test_gestionale
- La sottocartella viene creata automaticamente con il nome del progetto
- Cartella configurabile dal menu Impostazioni

INSTALLAZIONE:
1. Copia machine_server.py sul PC destinazione
2. Avvia: python machine_server.py
3. La finestra si minimizza nella taskbar
4. Usa menu Impostazioni per cambiare cartella base
"""

import socket
import os
import json
import threading
import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import configparser
from datetime import datetime

# ─── Costanti ─────────────────────────────────────────────────────────────────
CONFIG_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_config.ini")
DEFAULT_PORT = 9999
DEFAULT_BASE = r"C:\Users\i.dodon\Documents\test_gestionale"


# ─── Config ───────────────────────────────────────────────────────────────────
def carica_config():
    cfg = configparser.ConfigParser()
    if not os.path.exists(CONFIG_FILE):
        cfg["server"] = {"port": str(DEFAULT_PORT), "base_path": DEFAULT_BASE}
        with open(CONFIG_FILE, "w") as f:
            cfg.write(f)
    cfg.read(CONFIG_FILE)
    port      = int(cfg["server"].get("port",      DEFAULT_PORT))
    base_path =     cfg["server"].get("base_path", DEFAULT_BASE)
    return port, base_path


def salva_config(port, base_path):
    cfg = configparser.ConfigParser()
    cfg["server"] = {"port": str(port), "base_path": base_path}
    with open(CONFIG_FILE, "w") as f:
        cfg.write(f)


# ─── Server socket ────────────────────────────────────────────────────────────
class MachineServer:

    def __init__(self, port, base_path, log_cb):
        self.port      = port
        self.base_path = base_path
        self.log       = log_cb
        self.running   = False
        self._sock     = None

    def start(self):
        self.running = True
        threading.Thread(target=self._listen, daemon=True).start()

    def stop(self):
        self.running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    def _listen(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._sock.bind(("0.0.0.0", self.port))
            self._sock.listen(5)
            self.log(f"✅ Server avviato  porta {self.port}")
            self.log(f"📁 Cartella base: {self.base_path}")
        except Exception as e:
            self.log(f"❌ Errore avvio: {e}")
            return

        while self.running:
            try:
                self._sock.settimeout(1.0)
                try:
                    conn, addr = self._sock.accept()
                except socket.timeout:
                    continue
                self.log(f"🔌 Connessione da {addr[0]}")
                threading.Thread(target=self._handle, args=(conn,), daemon=True).start()
            except Exception:
                break

    def _handle(self, conn):
        try:
            raw = b""
            while b"\n" not in raw:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                raw += chunk

            header_line, resto = raw.split(b"\n", 1)
            header   = json.loads(header_line.decode("utf-8"))
            comando  = header.get("comando")
            progetto = header.get("progetto", "").strip()

            dest_dir = os.path.join(self.base_path, progetto) if progetto else self.base_path

            # ── CHECK ────────────────────────────────────────────────────────
            if comando == "CHECK":
                files     = header.get("files", [])
                esistenti = [f for f in files if os.path.exists(os.path.join(dest_dir, f))]
                conn.sendall(json.dumps({"esistenti": esistenti, "dest_dir": dest_dir}).encode())
                self.log(f"🔍 CHECK [{progetto}]: {len(files)} file, {len(esistenti)} già presenti")

            # ── INVIA ────────────────────────────────────────────────────────
            elif comando == "INVIA":
                filename = header.get("filename")
                filesize = int(header.get("filesize", 0))

                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)
                    self.log(f"📂 Cartella creata: {dest_dir}")

                dest_path = os.path.join(dest_dir, filename)
                received  = resto
                while len(received) < filesize:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    received += chunk

                with open(dest_path, "wb") as f:
                    f.write(received[:filesize])

                ts = datetime.now().strftime("%H:%M:%S")
                self.log(f"[{ts}] ✅ {filename}  ({filesize} B)")
                conn.sendall(b"OK")

            else:
                conn.sendall(b"ERRORE: comando sconosciuto")

        except Exception as e:
            self.log(f"❌ Errore: {e}")
            try:
                conn.sendall(f"ERRORE: {e}".encode())
            except Exception:
                pass
        finally:
            conn.close()


# ─── Dialog Impostazioni ──────────────────────────────────────────────────────
class ImpostazioniDialog(tk.Toplevel):

    def __init__(self, parent, port, base_path, on_save):
        super().__init__(parent)
        self.title("Impostazioni Server")
        self.geometry("500x230")
        self.resizable(False, False)
        self.grab_set()
        self.on_save = on_save

        pad = {"padx": 14, "pady": 7}

        tk.Label(self, text="Porta:", font=("Segoe UI", 9, "bold"), anchor="w").grid(
            row=0, column=0, sticky="w", **pad)
        self.entry_port = tk.Entry(self, width=10, font=("Segoe UI", 9))
        self.entry_port.insert(0, str(port))
        self.entry_port.grid(row=0, column=1, sticky="w", **pad)

        tk.Label(self, text="Cartella base:", font=("Segoe UI", 9, "bold"), anchor="w").grid(
            row=1, column=0, sticky="w", **pad)
        self.entry_path = tk.Entry(self, width=40, font=("Segoe UI", 9))
        self.entry_path.insert(0, base_path)
        self.entry_path.grid(row=1, column=1, sticky="ew", **pad)
        tk.Button(self, text="📁", command=self._sfoglia, width=3).grid(row=1, column=2, padx=(0,14))

        tk.Label(self,
                 text="Nota: la sottocartella con il nome del progetto\nviene aggiunta automaticamente a questa.",
                 font=("Segoe UI", 8), fg="#777", justify="left").grid(
            row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 8))

        tk.Label(self, text="Esempio:  [cartella base]\\NOME_PROGETTO\\file.MPF",
                 font=("Courier New", 8), fg="#1565C0", justify="left").grid(
            row=3, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 12))

        btn = tk.Frame(self)
        btn.grid(row=4, column=0, columnspan=3)
        tk.Button(btn, text="💾  Salva e riavvia", width=18, bg="#1565C0", fg="white",
                  font=("Segoe UI", 9, "bold"), command=self._salva).pack(side="left", padx=6)
        tk.Button(btn, text="Annulla", width=10, command=self.destroy).pack(side="left", padx=6)

        self.columnconfigure(1, weight=1)

    def _sfoglia(self):
        path = filedialog.askdirectory(title="Seleziona cartella base")
        if path:
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, path.replace("/", "\\"))

    def _salva(self):
        try:
            port = int(self.entry_port.get().strip())
        except ValueError:
            messagebox.showerror("Errore", "Porta non valida", parent=self)
            return
        base_path = self.entry_path.get().strip()
        if not base_path:
            messagebox.showerror("Errore", "Inserisci cartella base", parent=self)
            return
        self.on_save(port, base_path)
        self.destroy()


# ─── App principale ───────────────────────────────────────────────────────────
class ServerApp:

    def __init__(self, root):
        self.root      = root
        self.port, self.base_path = carica_config()
        self.server    = None
        self._build_ui()
        self._avvia_server()
        root.after(300, root.iconify)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        self.root.title("DMG Machine Server")
        self.root.geometry("560x420")
        self.root.resizable(True, True)
        self.root.minsize(400, 300)

        # Menu
        menubar   = tk.Menu(self.root)
        menu_imp  = tk.Menu(menubar, tearoff=0)
        menu_imp.add_command(label="⚙️  Impostazioni...", command=self._apri_impostazioni)
        menu_imp.add_separator()
        menu_imp.add_command(label="Esci", command=self._on_close)
        menubar.add_cascade(label="Menu", menu=menu_imp)
        self.root.config(menu=menubar)

        # Header
        hdr = tk.Frame(self.root, bg="#1565C0")
        hdr.pack(fill="x")
        tk.Label(hdr, text="DMG Machine Server", font=("Segoe UI", 13, "bold"),
                 bg="#1565C0", fg="white").pack(side="left", padx=14, pady=8)
        self.lbl_stato = tk.Label(hdr, text="⏳ Avvio...",
                                   font=("Segoe UI", 9), bg="#1565C0", fg="#90CAF9")
        self.lbl_stato.pack(side="right", padx=14)

        # Info
        info = tk.Frame(self.root, bg="#E3F2FD", pady=6)
        info.pack(fill="x", padx=10, pady=(8, 0))
        self.lbl_porta = tk.Label(info, font=("Segoe UI", 9), bg="#E3F2FD", anchor="w")
        self.lbl_porta.pack(fill="x", padx=10, pady=1)
        self.lbl_path  = tk.Label(info, font=("Segoe UI", 9), bg="#E3F2FD", anchor="w",
                                   wraplength=520, justify="left")
        self.lbl_path.pack(fill="x", padx=10, pady=1)
        self._aggiorna_labels()

        # Log
        tk.Label(self.root, text="Log attività:", font=("Segoe UI", 9),
                 anchor="w").pack(fill="x", padx=10, pady=(10, 2))
        self.log_box = scrolledtext.ScrolledText(
            self.root, font=("Courier New", 8), state="disabled", bg="#FAFAFA")
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log_box.tag_config("ok",   foreground="#2E7D32")
        self.log_box.tag_config("err",  foreground="#C62828")
        self.log_box.tag_config("info", foreground="#1565C0")
        self.log_box.tag_config("plain",foreground="#333333")

    def _aggiorna_labels(self):
        self.lbl_porta.config(text=f"Porta:          {self.port}")
        self.lbl_path.config( text=f"Cartella base:  {self.base_path}")

    def _avvia_server(self):
        if self.server:
            self.server.stop()
        self.server = MachineServer(self.port, self.base_path, self._log)
        self.server.start()
        self.lbl_stato.config(text=f"🟢 In ascolto :{self.port}", fg="#A5D6A7")

    def _log(self, msg):
        def _do():
            tag = ("ok"   if "✅" in msg else
                   "err"  if "❌" in msg else
                   "info" if any(c in msg for c in ["🔍","🔌","📂","📁","⚙️"]) else "plain")
            self.log_box.config(state="normal")
            self.log_box.insert("end", msg + "\n", tag)
            self.log_box.see("end")
            self.log_box.config(state="disabled")
        self.root.after(0, _do)

    def _apri_impostazioni(self):
        def on_save(new_port, new_base):
            self.port      = new_port
            self.base_path = new_base
            salva_config(new_port, new_base)
            self._aggiorna_labels()
            self._avvia_server()
            self._log(f"⚙️  Impostazioni aggiornate — porta {new_port}  |  {new_base}")
        ImpostazioniDialog(self.root, self.port, self.base_path, on_save)

    def _on_close(self):
        if messagebox.askyesno("Chiudi server",
                               "Chiudendo il server i file non potranno più\n"
                               "essere inviati dalla postazione operatore.\n\n"
                               "Vuoi chiudere?"):
            if self.server:
                self.server.stop()
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    ServerApp(root)
    root.mainloop()
