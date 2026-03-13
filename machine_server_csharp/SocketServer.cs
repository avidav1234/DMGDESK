using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

namespace MachineServer
{
    /// <summary>
    /// Server TCP che riceve comandi JSON dal PC operatore.
    /// Protocollo: header JSON terminato da \n, poi eventuali bytes del file.
    /// Comandi supportati: CHECK, INVIA
    /// </summary>
    public class SocketServer
    {
        private TcpListener  _listener;
        private bool         _running;
        private ServerConfig _config;

        public delegate void LogHandler(string message);
        public event LogHandler OnLog;

        public SocketServer(ServerConfig config)
        {
            _config = config;
        }

        // ── Avvio / Stop ──────────────────────────────────────────────────────

        public void Start()
        {
            _running = true;
            Thread t = new Thread(new ThreadStart(Listen));
            t.IsBackground = true;
            t.Start();
        }

        public void Stop()
        {
            _running = false;
            if (_listener != null)
            {
                try { _listener.Stop(); }
                catch { }
            }
        }

        public void UpdateConfig(ServerConfig config)
        {
            _config = config;
        }

        // ── Loop ascolto ──────────────────────────────────────────────────────

        private void Listen()
        {
            try
            {
                _listener = new TcpListener(IPAddress.Any, _config.Port);
                _listener.Start();
                Log("✅ Server avviato  porta " + _config.Port);
                Log("📁 Cartella base: " + _config.BasePath);
            }
            catch (Exception ex)
            {
                Log("❌ Errore avvio: " + ex.Message);
                return;
            }

            while (_running)
            {
                try
                {
                    // AcceptTcpClient è bloccante — usiamo Pending con sleep
                    if (!_listener.Pending())
                    {
                        Thread.Sleep(100);
                        continue;
                    }

                    TcpClient client = _listener.AcceptTcpClient();
                    string ip = ((IPEndPoint)client.Client.RemoteEndPoint).Address.ToString();
                    Log("🔌 Connessione da " + ip);

                    Thread ct = new Thread(new ParameterizedThreadStart(HandleClient));
                    ct.IsBackground = true;
                    ct.Start(client);
                }
                catch (Exception ex)
                {
                    if (_running) Log("❌ Errore accept: " + ex.Message);
                }
            }
        }

        // ── Gestione singola connessione ──────────────────────────────────────

        private void HandleClient(object obj)
        {
            TcpClient client = (TcpClient)obj;
            NetworkStream stream = null;

            try
            {
                stream = client.GetStream();
                stream.ReadTimeout  = 15000;
                stream.WriteTimeout = 15000;

                // ── Leggi header JSON (fino a \n) ─────────────────────────────
                MemoryStream headerBuf = new MemoryStream();
                int b;
                while ((b = stream.ReadByte()) != -1)
                {
                    if (b == '\n') break;
                    headerBuf.WriteByte((byte)b);
                }

                string headerJson = Encoding.UTF8.GetString(headerBuf.ToArray());
                SimpleJson header = SimpleJson.Parse(headerJson);

                string comando  = header.GetString("comando");
                string progetto = header.GetString("progetto").Trim();

                // Cartella destinazione = BasePath\progetto  (se progetto fornito)
                string destDir = string.IsNullOrEmpty(progetto)
                    ? _config.BasePath
                    : Path.Combine(_config.BasePath, progetto);

                // ── CHECK ─────────────────────────────────────────────────────
                if (comando == "CHECK")
                {
                    string[] files    = header.GetStringArray("files");
                    string[] esistenti = FindExisting(destDir, files);

                    string resp = BuildCheckResponse(esistenti, destDir);
                    byte[] respBytes = Encoding.UTF8.GetBytes(resp);
                    stream.Write(respBytes, 0, respBytes.Length);

                    Log("🔍 CHECK [" + progetto + "]: " + files.Length +
                        " file, " + esistenti.Length + " già presenti");
                }

                // ── INVIA ─────────────────────────────────────────────────────
                else if (comando == "INVIA")
                {
                    string filename = header.GetString("filename");
                    int    filesize = header.GetInt("filesize");

                    // Crea cartella se non esiste
                    if (!Directory.Exists(destDir))
                    {
                        Directory.CreateDirectory(destDir);
                        Log("📂 Cartella creata: " + destDir);
                    }

                    // Ricevi bytes del file
                    byte[] fileData = new byte[filesize];
                    int    received = 0;
                    while (received < filesize)
                    {
                        int chunk = stream.Read(fileData, received, filesize - received);
                        if (chunk == 0) break;
                        received += chunk;
                    }

                    string destPath = Path.Combine(destDir, filename);
                    File.WriteAllBytes(destPath, fileData);

                    Log("[" + DateTime.Now.ToString("HH:mm:ss") + "] ✅ " +
                        filename + "  (" + filesize + " B)");

                    byte[] ok = Encoding.UTF8.GetBytes("OK");
                    stream.Write(ok, 0, ok.Length);
                }
                else
                {
                    byte[] err = Encoding.UTF8.GetBytes("ERRORE: comando sconosciuto");
                    stream.Write(err, 0, err.Length);
                }
            }
            catch (Exception ex)
            {
                Log("❌ Errore connessione: " + ex.Message);
                try
                {
                    if (stream != null)
                    {
                        byte[] err = Encoding.UTF8.GetBytes("ERRORE: " + ex.Message);
                        stream.Write(err, 0, err.Length);
                    }
                }
                catch { }
            }
            finally
            {
                try { client.Close(); } catch { }
            }
        }

        // ── Helpers ───────────────────────────────────────────────────────────

        private string[] FindExisting(string dir, string[] files)
        {
            if (files == null) return new string[0];
            System.Collections.ArrayList found = new System.Collections.ArrayList();
            foreach (string f in files)
            {
                if (File.Exists(Path.Combine(dir, f)))
                    found.Add(f);
            }
            return (string[])found.ToArray(typeof(string));
        }

        private string BuildCheckResponse(string[] esistenti, string destDir)
        {
            // Costruisce JSON manualmente (no dipendenze esterne)
            StringBuilder sb = new StringBuilder();
            sb.Append("{\"esistenti\":[");
            for (int i = 0; i < esistenti.Length; i++)
            {
                if (i > 0) sb.Append(",");
                sb.Append("\"").Append(EscapeJson(esistenti[i])).Append("\"");
            }
            sb.Append("],\"dest_dir\":\"");
            sb.Append(EscapeJson(destDir));
            sb.Append("\"}");
            return sb.ToString();
        }

        private string EscapeJson(string s)
        {
            return s.Replace("\\", "\\\\").Replace("\"", "\\\"");
        }

        private void Log(string msg)
        {
            if (OnLog != null) OnLog(msg);
        }
    }

    // ── Parser JSON minimale (no dipendenze, .NET 2.0) ────────────────────────

    public class SimpleJson
    {
        private string _raw;

        private SimpleJson(string raw) { _raw = raw; }

        public static SimpleJson Parse(string json)
        {
            return new SimpleJson(json ?? "");
        }

        public string GetString(string key)
        {
            // Cerca "key":"value"
            string search = "\"" + key + "\"";
            int ki = _raw.IndexOf(search);
            if (ki < 0) return "";

            int colon = _raw.IndexOf(':', ki + search.Length);
            if (colon < 0) return "";

            int start = _raw.IndexOf('"', colon + 1);
            if (start < 0) return "";

            int end = start + 1;
            while (end < _raw.Length)
            {
                if (_raw[end] == '\\') { end += 2; continue; }
                if (_raw[end] == '"') break;
                end++;
            }
            return _raw.Substring(start + 1, end - start - 1)
                       .Replace("\\\"", "\"")
                       .Replace("\\\\", "\\")
                       .Replace("\\n", "\n");
        }

        public int GetInt(string key)
        {
            string search = "\"" + key + "\"";
            int ki = _raw.IndexOf(search);
            if (ki < 0) return 0;

            int colon = _raw.IndexOf(':', ki + search.Length);
            if (colon < 0) return 0;

            int start = colon + 1;
            while (start < _raw.Length && (_raw[start] == ' ' || _raw[start] == '\t'))
                start++;

            int end = start;
            while (end < _raw.Length && (char.IsDigit(_raw[end]) || _raw[end] == '-'))
                end++;

            int result;
            int.TryParse(_raw.Substring(start, end - start), out result);
            return result;
        }

        public string[] GetStringArray(string key)
        {
            string search = "\"" + key + "\"";
            int ki = _raw.IndexOf(search);
            if (ki < 0) return new string[0];

            int bracketOpen = _raw.IndexOf('[', ki + search.Length);
            if (bracketOpen < 0) return new string[0];

            int bracketClose = _raw.IndexOf(']', bracketOpen);
            if (bracketClose < 0) return new string[0];

            string inner = _raw.Substring(bracketOpen + 1, bracketClose - bracketOpen - 1);
            if (inner.Trim().Length == 0) return new string[0];

            System.Collections.ArrayList list = new System.Collections.ArrayList();
            int pos = 0;
            while (pos < inner.Length)
            {
                int s = inner.IndexOf('"', pos);
                if (s < 0) break;
                int e = s + 1;
                while (e < inner.Length)
                {
                    if (inner[e] == '\\') { e += 2; continue; }
                    if (inner[e] == '"') break;
                    e++;
                }
                list.Add(inner.Substring(s + 1, e - s - 1));
                pos = e + 1;
            }
            return (string[])list.ToArray(typeof(string));
        }
    }
}
