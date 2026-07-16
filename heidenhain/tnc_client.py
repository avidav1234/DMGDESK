"""Client di SOLA LETTURA per controllo HEIDENHAIN TNC 640 (HEROS).

Due canali, entrambi verificati sul campo (2026-07-16) su Mikron P800
— TNC640, NC SW 340590-08 SP7, IP 192.168.244.149:

  * VNC (porta 5900): cattura schermo via protocollo RFB, solo stdlib. Sulla
    macchina di test l'auth e' "None" (nessuna password). Qui si LEGGE solo il
    framebuffer: nessun evento mouse/tastiera viene mai inviato.

  * LSV2 (porta 19000, libreria pyLSV2, safe_mode=True): versione controllo,
    messaggi attivi, lista/trasferimento file, screen dump. I dati STRUTTURATI
    (assi, override, stato programma, utensile) richiedono l'opzione 18 (DNC),
    NON attiva su questa macchina -> ritornano None. Vedi README (🟡).

Niente di qui pilota la macchina. Il comando "umano" (mouse) passa semmai dal
client VNC lato frontend, con gating esplicito (vedi README, sezione sicurezza).
"""

from __future__ import annotations

import socket
import struct
import zlib
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Canale VNC / RFB — cattura schermo (stdlib pura)
# ---------------------------------------------------------------------------


def _recvall(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connessione VNC chiusa durante la lettura")
        buf.extend(chunk)
    return bytes(buf)


def grab_screen_rfb(ip: str, port: int = 5900, timeout: float = 8.0) -> Tuple[int, int, bytearray]:
    """Cattura un fotogramma completo dello schermo del controllo via RFB.

    Ritorna (width, height, rgb) dove rgb e' un bytearray width*height*3 in
    ordine riga-per-riga top-down (R,G,B). Forza encoding Raw per decodifica
    semplice. Gestisce solo auth "None" (nessuna password) — se il server
    richiede password solleva un'eccezione esplicita.
    """
    s = socket.create_connection((ip, port), timeout=timeout)
    try:
        s.settimeout(timeout)

        # 1) ProtocolVersion
        _server_ver = _recvall(s, 12)
        s.sendall(b"RFB 003.008\n")

        # 2) Security types
        cnt = _recvall(s, 1)[0]
        if cnt == 0:
            rlen = struct.unpack(">I", _recvall(s, 4))[0]
            raise RuntimeError("VNC ha rifiutato l'handshake: " + _recvall(s, rlen).decode("ascii", "replace"))
        types = _recvall(s, cnt)
        if 1 not in types:
            raise RuntimeError(
                "Il server VNC richiede autenticazione (nessun 'None'): tipi=%s. "
                "Imposta/recupera la password a bordo (Settings -> VNC) e aggiungi "
                "il supporto VNC Auth qui." % list(types)
            )
        s.sendall(bytes([1]))  # scegli None

        # 3) SecurityResult (RFB 3.8: sempre presente)
        if struct.unpack(">I", _recvall(s, 4))[0] != 0:
            raise RuntimeError("VNC SecurityResult != 0 (autenticazione fallita)")

        # 4) ClientInit -> ServerInit
        s.sendall(bytes([1]))  # shared = 1
        hdr = _recvall(s, 24)
        width, height = struct.unpack(">HH", hdr[0:4])
        name_len = struct.unpack(">I", hdr[20:24])[0]
        _name = _recvall(s, name_len)

        # 5) SetPixelFormat: 32bpp, depth24, big-endian, true-color, RGB max 255,
        #    shift R16/G8/B0 -> ogni pixel arriva come byte [x, R, G, B]
        pf = struct.pack(">BBBB HHH BBB xxx", 32, 24, 1, 1, 255, 255, 255, 16, 8, 0)
        s.sendall(struct.pack(">B xxx", 0) + pf)

        # 6) SetEncodings: solo Raw (0)
        s.sendall(struct.pack(">B x H", 2, 1) + struct.pack(">i", 0))

        # 7) FramebufferUpdateRequest (incremental=0 => full)
        s.sendall(struct.pack(">B B HHHH", 3, 0, 0, 0, width, height))

        # 8) FramebufferUpdate
        if _recvall(s, 1)[0] != 0:
            raise RuntimeError("atteso messaggio FramebufferUpdate (0)")
        _recvall(s, 1)  # padding
        nrects = struct.unpack(">H", _recvall(s, 2))[0]

        img = bytearray(width * height * 3)
        for _ in range(nrects):
            rx, ry, rw, rh = struct.unpack(">HHHH", _recvall(s, 8))
            enc = struct.unpack(">i", _recvall(s, 4))[0]
            if enc != 0:
                raise RuntimeError("ricevuto encoding non-Raw (%d): non supportato dal grabber minimale" % enc)
            data = _recvall(s, rw * rh * 4)
            # Estrazione canali via slicing (C-level): pixel = [x, R, G, B].
            for row in range(rh):
                src = data[row * rw * 4:(row + 1) * rw * 4]
                dst = ((ry + row) * width + rx) * 3
                img[dst + 0:dst + rw * 3:3] = src[1::4]  # R
                img[dst + 1:dst + rw * 3:3] = src[2::4]  # G
                img[dst + 2:dst + rw * 3:3] = src[3::4]  # B
        return width, height, img
    finally:
        s.close()


def rgb_to_png(width: int, height: int, rgb: bytearray) -> bytes:
    """Codifica RGB top-down (R,G,B) in PNG. Solo stdlib (zlib)."""
    raw = bytearray()
    row_bytes = width * 3
    for y in range(height):
        raw.append(0)  # filtro 0
        base = y * row_bytes
        raw += rgb[base:base + row_bytes]

    def _chunk(typ: bytes, payload: bytes) -> bytes:
        c = struct.pack(">I", len(payload)) + typ + payload
        return c + struct.pack(">I", zlib.crc32(typ + payload) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += _chunk(b"IEND", b"")
    return png


def screenshot_png(ip: str, port: int = 5900, timeout: float = 8.0) -> bytes:
    """Cattura lo schermo e ritorna direttamente i byte PNG (per l'endpoint HTTP)."""
    w, h, rgb = grab_screen_rfb(ip, port=port, timeout=timeout)
    return rgb_to_png(w, h, rgb)


# ---------------------------------------------------------------------------
# Canale LSV2 (pyLSV2) — info di sola lettura
# ---------------------------------------------------------------------------


def lsv2_info(ip: str, port: int = 19000, timeout: float = 6.0) -> dict:
    """Info di sola lettura via LSV2. safe_mode=True (comandi bloccati).

    Ritorna sempre un dict; i campi che richiedono l'opzione 18 (DNC) sono None
    con nota in 'note'. Non solleva: incapsula gli errori in 'errore'.
    """
    out: dict = {
        "connesso": False,
        "versione": None,
        "controllo": None,
        "dnc_attivo": None,
        "messaggi_attivi": [],
        # richiedono login DNC (opzione 18) — attiva su questa macchina
        "stato_programma": None,
        "stato_esecuzione": None,
        "programma_corrente": None,
        "assi": None,
        "override": None,
        "utensile": None,
        "note": [],
        "errore": None,
    }
    try:
        import pyLSV2
    except ImportError:
        out["errore"] = "pyLSV2 non installato (pip install pyLSV2)"
        return out

    con = pyLSV2.LSV2(ip, port=port, timeout=timeout, safe_mode=True)
    try:
        con.connect()
        out["connesso"] = True

        # safe_mode=True mantiene bloccati i comandi di sistema/scrittura pericolosi.
        # Abilitiamo SOLO il login DNC (opzione 18) per la LETTURA dei dati di stato
        # (assi/override/programma). pyLSV2 in safe_mode esclude DNC dai login noti,
        # quindi lo aggiungiamo esplicitamente. Nessun metodo di scrittura/comando
        # viene mai invocato da questo modulo.
        try:
            con._known_logins = tuple(set(con._known_logins) | {pyLSV2.Login.DNC})
        except Exception:  # noqa: BLE001
            out["note"].append("impossibile abilitare login DNC in lettura")

        try:
            ver = con.versions  # property
            out["versione"] = str(ver.nc_sw)
            out["controllo"] = str(ver.control)
        except Exception as e:  # noqa: BLE001
            out["note"].append(f"versione non letta: {e}")

        try:
            msgs = con.get_error_messages() or []
            out["messaggi_attivi"] = [str(m) for m in msgs]
        except Exception as e:  # noqa: BLE001
            out["note"].append(f"messaggi non letti: {e}")

        # Dati strutturati (richiedono login DNC / opzione 18). Su questa macchina
        # l'opzione 18 e' ATTIVA (la usa anche il MES) -> dati disponibili e live.
        def _name(v):
            if v is None:
                return None
            return getattr(v, "name", None) or str(v)

        try:
            out["stato_programma"] = _name(con.program_status())
            out["stato_esecuzione"] = _name(con.execution_state())
            out["assi"] = con.axes_location()

            stack = con.program_stack()
            if stack is not None:
                out["programma_corrente"] = {
                    "main": getattr(stack, "main", None),
                    "corrente": getattr(stack, "current", None),
                    "linea": getattr(stack, "line_no", None),
                }

            ovr = con.override_state()
            if ovr is not None:
                out["override"] = {
                    "feed": getattr(ovr, "feed", None),
                    "rapid": getattr(ovr, "rapid", None),
                    "spindle": getattr(ovr, "spindle", None),
                }

            tool = con.spindle_tool_status()  # None su alcuni controlli (incl. questo)
            out["utensile"] = _name(tool)
            if tool is None:
                out["note"].append("utensile via spindle_tool_status non disponibile su questo controllo")

            out["dnc_attivo"] = out["assi"] is not None
            if not out["dnc_attivo"]:
                out["note"].append(
                    "Login DNC ok ma dati assenti: verificare stato macchina o sessioni concorrenti."
                )
        except Exception as e:  # noqa: BLE001
            out["dnc_attivo"] = False
            out["note"].append(f"dati DNC non letti: {e}")
    except Exception as e:  # noqa: BLE001
        out["errore"] = f"{type(e).__name__}: {e}"
    finally:
        try:
            con.disconnect()
        except Exception:  # noqa: BLE001
            pass
    return out


# ---------------------------------------------------------------------------
# Diagnostica porte (senza dipendenze)
# ---------------------------------------------------------------------------


def port_open(ip: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def connectivity(ip: str) -> dict:
    return {
        "ip": ip,
        "vnc_5900": port_open(ip, 5900),
        "lsv2_19000": port_open(ip, 19000),
    }
