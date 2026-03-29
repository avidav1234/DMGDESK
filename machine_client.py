"""
DMG Machine Client - Logica invio file alla macchina CNC
Usato da dialog_invia_macchina nel tab analisi NC.
"""

import socket
import os
import json

SERVER_PORT = 9999
TIMEOUT_SEC = 120  # Il server attende fino a 90s che DNCMachine trasferisca il file


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
            # F2: leggi fino a \n — stesso meccanismo di invia_file
            # evita di bloccare con risposte grandi (128KB con molti file)
            raw = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                raw += chunk
                if b"\n" in raw:
                    break
            s.close()
            risposta = json.loads(raw.strip().decode("utf-8"))
            # server risponde "files", compatibile con "esistenti" per retrocompatibilità
            esistenti = risposta.get("files", risposta.get("esistenti", []))
            dest_dir  = risposta.get("dest_dir", "")
            return esistenti, dest_dir, None
        except Exception as e:
            return [], "", str(e)

    def invia_file(self, filepath, progetto, progress_callback=None):
        """
        Invia un singolo file al server.
        progress_callback(filename, successo: bool, messaggio: str)
        Restituisce (successo: bool, messaggio: str)
        """
        filename = os.path.basename(filepath)
        # Sinumerik vuole nomi MAIUSCOLI e senza estensione .MPF
        filename_siemens = filename.upper()
        if filename_siemens.endswith(".MPF"):
            filename_siemens = filename_siemens[:-4]
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            filesize = len(content)

            header = json.dumps({
                "comando":  "INVIA",
                "progetto": progetto,
                "filename": filename_siemens,
                "filesize": filesize
            }) + "\n"

            s = self._connect()
            s.sendall(header.encode("utf-8") + content)

            # Leggi fino a newline: il server termina la risposta con \n
            risposta = b""
            while True:
                chunk = s.recv(1024)
                if not chunk:
                    break
                risposta += chunk
                if b"\n" in risposta:
                    break
            s.close()

            risposta_str = risposta.strip().decode("utf-8", errors="replace")
            # Accetta sia "OK" semplice che JSON {"stato":"ok",...}
            try:
                risposta_json = json.loads(risposta_str)
                ok = risposta_json.get("stato") == "ok"
                msg = risposta_json.get("msg", "OK") if ok else risposta_json.get("msg", risposta_str)
            except Exception:
                # Fallback: risposta testuale semplice
                ok = risposta_str.strip().upper() in ("OK", "OK\n")
                msg = "OK" if ok else risposta_str

            # Nota: il callback riceve il filename originale (con estensione)
            # così il dialog può trovarlo nella tabella
            if progress_callback:
                progress_callback(filename, ok, msg)
            return ok, msg

        except Exception as e:
            if progress_callback:
                progress_callback(filename, False, str(e))
            return False, str(e)

    def invia_batch(self, filepaths, progetto, progress_callback=None):
        """
        Invia tutti i file in una sola connessione TCP.
        Protocollo:
          1. Header: {"cmd":"INVIA_BATCH","progetto":"...","count":N}\n
          2. Per ogni file: {"filename":"...","filesize":N}\n + bytes
          3. Chiude connessione → server chiama TransferAutom una sola volta
        Molto più veloce di invia_lista per batch grandi.
        Restituisce (n_ok, n_err, lista_errori)
        """
        if not filepaths:
            return 0, 0, []

        # Leggi tutti i file prima di aprire la connessione
        files_data = []
        for fp in filepaths:
            try:
                with open(fp, "rb") as f:
                    content = f.read()
                fname = os.path.basename(fp).upper()
                if fname.endswith(".MPF"):
                    fname = fname[:-4]
                files_data.append((fname, content, fp))
            except Exception as e:
                if progress_callback:
                    progress_callback(os.path.basename(fp), False, str(e))

        if not files_data:
            return 0, len(filepaths), ["Nessun file leggibile"]

        n_ok, n_err, errori = 0, 0, []
        try:
            s = self._connect()
            s.settimeout(30)  # batch: timeout breve per file singolo

            # 1. Header batch
            header = json.dumps({
                "cmd":      "INVIA_BATCH",
                "progetto": progetto,
                "count":    len(files_data)
            }) + "\n"
            s.sendall(header.encode("utf-8"))

            # 2. Invia ogni file
            for fname, content, fp in files_data:
                fhdr = json.dumps({
                    "filename": fname,
                    "filesize": len(content)
                }) + "\n"
                s.sendall(fhdr.encode("utf-8") + content)
                n_ok += 1
                if progress_callback:
                    progress_callback(os.path.basename(fp), True, "inviato")

            # 3. Chiudi connessione → server avvia TransferAutom
            s.shutdown(socket.SHUT_WR)

            # 4. Leggi risposta finale
            risposta = b""
            s.settimeout(15)
            try:
                while True:
                    chunk = s.recv(1024)
                    if not chunk:
                        break
                    risposta += chunk
                    if b"\n" in risposta:
                        break
            except Exception:
                pass
            s.close()

            risposta_str = risposta.strip().decode("utf-8", errors="replace")
            if risposta_str:
                try:
                    rj = json.loads(risposta_str)
                    print(f"[BATCH] risposta server: {rj}")
                    if rj.get("errori", 0) > 0:
                        n_err = rj["errori"]
                        n_ok  = rj.get("inviati", n_ok)
                        errori.append(rj.get("msg", "errore batch"))
                except Exception:
                    print(f"[BATCH] risposta: {risposta_str}")

        except Exception as e:
            n_err = len(files_data) - n_ok
            errori.append(str(e))

        return n_ok, n_err, errori

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
