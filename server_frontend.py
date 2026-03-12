"""
server_frontend.py
===================
Serve i file statici React (frontend/dist/) su porta 3000
e proxya tutte le chiamate /api → FastAPI su porta 8000.

Non richiede Nginx o Docker — solo Python standard + urllib.
Avvio: python server_frontend.py
"""

import http.server
import urllib.request
import urllib.error
import os
import sys
import mimetypes
from pathlib import Path

FRONTEND_DIR = Path(__file__).parent / "frontend" / "dist"
BACKEND_URL  = "http://127.0.0.1:8000"
PORT         = 9191  # porta non standard — raramente occupata o filtrata

# Mappa estensioni → content type
MIME_EXTRA = {
    ".jsx": "application/javascript",
    ".ts":  "application/javascript",
    ".tsx": "application/javascript",
}

class ToolManagerHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Log minimale — solo errori e /api
        if "/api" in (args[0] if args else ""):
            print(f"  API  {args[0]} {args[1]}", flush=True)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def do_DELETE(self):
        self._handle("DELETE")

    def do_PATCH(self):
        self._handle("PATCH")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,PATCH,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")

    def _handle(self, method):
        path = self.path

        # ── Proxy /api e /health e /docs → FastAPI ─────────────
        if path.startswith("/api") or path.startswith("/health") or path.startswith("/docs") or path.startswith("/redoc"):
            self._proxy(method, path)
            return

        # ── File statici React ──────────────────────────────────
        self._serve_static(path)

    def _proxy(self, method, path):
        target = BACKEND_URL + path
        try:
            # Leggi body se presente
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else None

            req = urllib.request.Request(
                url=target,
                data=body,
                method=method,
            )
            # Copia headers rilevanti
            for h in ("Content-Type", "Content-Length", "Accept"):
                val = self.headers.get(h)
                if val:
                    req.add_header(h, val)

            with urllib.request.urlopen(req, timeout=30) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(k, v)
                self._cors_headers()
                self.end_headers()
                self.wfile.write(resp.read())

        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self._cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            print(f"  PROXY ERR {e}", flush=True)
            self.send_response(502)
            self._cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(f'{{"detail":"Backend non raggiungibile: {e}"}}'.encode())

    def _serve_static(self, path):
        # Rimuovi query string
        clean = path.split("?")[0]

        # Mappa percorso file
        file_path = FRONTEND_DIR / clean.lstrip("/")

        # Se non esiste come file → SPA fallback su index.html
        if not file_path.is_file():
            file_path = FRONTEND_DIR / "index.html"

        if not file_path.exists():
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Frontend non trovato. Hai eseguito 'npm run build' in frontend/?")
            return

        # Determina MIME type
        suffix = file_path.suffix
        mime = MIME_EXTRA.get(suffix) or mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        # Cache breve per HTML, lunga per assets hash
        if suffix == ".html":
            self.send_header("Cache-Control", "no-cache")
        else:
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(content)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Tool Manager — Frontend Server")
    parser.add_argument("--port", type=int, default=PORT, help="Porta HTTP (default: 80)")
    args = parser.parse_args()
    port = args.port

    if not FRONTEND_DIR.exists():
        print(f"\n⚠  Cartella '{FRONTEND_DIR}' non trovata.")
        print("   Esegui prima:\n")
        print("   cd frontend")
        print("   npm install")
        print("   npm run build\n")
        sys.exit(1)

    import socketserver
    socketserver.TCPServer.allow_reuse_address = True

    print(f"\n  Tool Manager — Server Frontend")
    print(f"  ─────────────────────────────────────")
    print(f"  Dashboard:   http://localhost")
    print(f"  Dalla LAN:   http://<IP-PC>  (porta 80 standard, nessuna configurazione firewall)")
    print(f"  API proxied: http://localhost/api → {BACKEND_URL}  (interno, non esposto)")
    print(f"\n  Premi CTRL+C per fermare.\n")

    with socketserver.TCPServer(("0.0.0.0", PORT), ToolManagerHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Server fermato.")


if __name__ == "__main__":
    main()
