"""
DMG Machine Client - Logica invio file alla macchina CNC
Usato da dialog_invia_macchina nel tab analisi NC.
"""

import socket
import os
import json

SERVER_PORT = 9999
TIMEOUT_SEC = 10


class MachineClient:
    """Comunica con machine_server.py sulla macchina/PC di test."""

    def __init__(self, server_ip, port=SERVER_PORT):
        self.server_ip = server_ip
        self.port      = port

    def _connect(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(TIMEOUT_SEC)
        s.connect((self.server_ip, self.port))
        return s

    def check_esistenti(self, filenames, progetto):
        """
        Chiede al server quali file esistono già nella cartella destinazione.
        Restituisce (lista_esistenti, dest_dir, errore_str_o_None)
        """
        header = json.dumps({
            "comando":  "CHECK",
            "progetto": progetto,
            "files":    filenames
        }) + "\n"
        try:
            s = self._connect()
            s.sendall(header.encode("utf-8"))
            raw = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                raw += chunk
            s.close()
            risposta = json.loads(raw.decode("utf-8"))
            return risposta.get("esistenti", []), risposta.get("dest_dir", ""), None
        except Exception as e:
            return [], "", str(e)

    def invia_file(self, filepath, progetto, progress_callback=None):
        """
        Invia un singolo file al server.
        progress_callback(filename, successo: bool, messaggio: str)
        Restituisce (successo: bool, messaggio: str)
        """
        filename = os.path.basename(filepath)
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            filesize = len(content)

            header = json.dumps({
                "comando":  "INVIA",
                "progetto": progetto,
                "filename": filename,
                "filesize": filesize
            }) + "\n"

            s = self._connect()
            s.sendall(header.encode("utf-8") + content)

            risposta = b""
            while True:
                chunk = s.recv(1024)
                if not chunk:
                    break
                risposta += chunk
            s.close()

            ok = risposta.strip() == b"OK"
            msg = "OK" if ok else risposta.decode("utf-8", errors="replace")
            if progress_callback:
                progress_callback(filename, ok, msg)
            return ok, msg

        except Exception as e:
            if progress_callback:
                progress_callback(filename, False, str(e))
            return False, str(e)

    def invia_lista(self, filepaths, progetto, progress_callback=None):
        """
        Invia una lista di file in sequenza.
        Restituisce (n_ok, n_err, lista_errori)
        """
        n_ok, n_err, errori = 0, 0, []
        for fp in filepaths:
            ok, msg = self.invia_file(fp, progetto, progress_callback)
            if ok:
                n_ok += 1
            else:
                n_err += 1
                errori.append(f"{os.path.basename(fp)}: {msg}")
        return n_ok, n_err, errori
