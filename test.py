@"
import http.server, socketserver
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok')
    def log_message(self, *a): pass
with socketserver.TCPServer(('127.0.0.1', 9999), H) as s:
    print('Apri http://localhost:9999')
    s.serve_forever()
"@ | Out-File test_server.py -Encoding utf8
python test_server.py