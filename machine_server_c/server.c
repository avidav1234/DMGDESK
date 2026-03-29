/*
 * server.c - MachineServer per trasferimento NC a Siemens 840D PowerLine
 *            + esportazione OpcUaLegacy.log sulla share (integra esporta_stato_macchina.vbs)
 * Compilazione: i686-w64-mingw32-gcc-win32 -static -static-libgcc -o MchnSrv.exe server.c -lws2_32 -lshlwapi
 */

#include <winsock2.h>
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <shlwapi.h>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "shlwapi.lib")

#define DEFAULT_PORT       9999
#define DEFAULT_BASE       "F:\\dh\\wks.dir"
#define DEFAULT_DNC_TMP    "D:\\tmp\\autoimport"
#define DEFAULT_VBS_PATH   "F:\\ADD_ON\\DNC\\transfer_dnc.vbs"
#define DEFAULT_OPCUA_LOG  "F:\\oem\\opcualegacy\\OpcUaLegacy.log"
#define DEFAULT_SHARE_DIR  "Z:\\DMG_DMC_160U\\"
#define DEFAULT_EXPORT_INT 60000   /* ms tra una copia e l'altra */
#define BUF_SIZE           65536
#define MAX_PATH_LEN       512

/* Path assoluto del config — costruito a runtime nella stessa cartella dell'exe */
static char CFG_FILE[MAX_PATH_LEN];

static void init_cfg_path(void) {
    char exe_path[MAX_PATH_LEN];
    GetModuleFileNameA(NULL, exe_path, sizeof(exe_path));
    char *last_slash = strrchr(exe_path, '\\');
    if (last_slash) {
        *(last_slash + 1) = '\0';
        snprintf(CFG_FILE, sizeof(CFG_FILE), "%sserver_config.ini", exe_path);
    } else {
        strncpy(CFG_FILE, "server_config.ini", sizeof(CFG_FILE));
    }
    printf("[CFG] Config: %s\n", CFG_FILE);
}

/* ── Config ─────────────────────────────────────────────────────────────── */

static int get_port(void) {
    return (int)GetPrivateProfileIntA("server", "port", DEFAULT_PORT, CFG_FILE);
}
static void get_base_path(char *out, int n) {
    GetPrivateProfileStringA("server", "base_path", DEFAULT_BASE, out, n, CFG_FILE);
}
static void get_dnc_tmp(char *out, int n) {
    GetPrivateProfileStringA("server", "dnc_path", DEFAULT_DNC_TMP, out, n, CFG_FILE);
}
static void get_vbs_path(char *out, int n) {
    GetPrivateProfileStringA("server", "vbs_path", DEFAULT_VBS_PATH, out, n, CFG_FILE);
}
static void get_opcua_log(char *out, int n) {
    GetPrivateProfileStringA("server", "opcua_log", DEFAULT_OPCUA_LOG, out, n, CFG_FILE);
}
static void get_share_dir(char *out, int n) {
    GetPrivateProfileStringA("server", "share_dir", DEFAULT_SHARE_DIR, out, n, CFG_FILE);
}
static int get_export_interval(void) {
    return (int)GetPrivateProfileIntA("server", "export_interval_ms", DEFAULT_EXPORT_INT, CFG_FILE);
}

/* ── Mutex globale — serializza chiamate VBS (F6) ────────────────────────── */
static HANDLE g_vbs_mutex = NULL;
static void   init_vbs_mutex(void) {
    g_vbs_mutex = CreateMutexA(NULL, FALSE, NULL);
}

/* ── VBS serializzato con delay (F4) ────────────────────────────────────── */

static void call_transfer_dnc(const char *filepath) {
    char vbs[MAX_PATH_LEN];
    char cmd[MAX_PATH_LEN * 3];
    get_vbs_path(vbs, sizeof(vbs));
    if (filepath && filepath[0])
        snprintf(cmd, sizeof(cmd), "cscript //Nologo \"%s\" \"%s\" > NUL 2>&1", vbs, filepath);
    else
        snprintf(cmd, sizeof(cmd), "cscript //Nologo \"%s\" > NUL 2>&1", vbs);

    Sleep(500); /* F4: lascia alla NCU 500ms dopo la scrittura del file */

    if (g_vbs_mutex) WaitForSingleObject(g_vbs_mutex, 15000); /* F6: una VBS alla volta */
    printf("[DNC] %s\n", cmd);
    int ret = system(cmd);
    if (ret == 0) printf("[DNC] OK\n");
    else          printf("[DNC] ret=%d\n", ret);
    if (g_vbs_mutex) ReleaseMutex(g_vbs_mutex);
}

/* ── JSON helpers ────────────────────────────────────────────────────────── */

static int json_get_str(const char *json, const char *key, char *out, int n) {
    char search[64];
    snprintf(search, sizeof(search), "\"%s\"", key);
    const char *p = strstr(json, search);
    if (!p) return 0;
    p += strlen(search);
    while (*p == ' ' || *p == ':') p++;
    if (*p != '"') return 0;
    p++;
    int i = 0;
    while (*p && *p != '"' && i < n-1) out[i++] = *p++;
    out[i] = '\0';
    return 1;
}

static long json_get_long(const char *json, const char *key) {
    char search[64];
    snprintf(search, sizeof(search), "\"%s\"", key);
    const char *p = strstr(json, search);
    if (!p) return -1;
    p += strlen(search);
    while (*p == ' ' || *p == ':') p++;
    char buf[32]; int i = 0;
    while ((*p >= '0' && *p <= '9') && i < 30) buf[i++] = *p++;
    buf[i] = '\0';
    return i > 0 ? atol(buf) : -1;
}

/* ── Normalizza nome ─────────────────────────────────────────────────────── */

static void normalize_name(const char *src, char *dst, int n) {
    strncpy(dst, src, n); dst[n-1] = '\0';
    for (int i = 0; dst[i]; i++)
        if (dst[i] >= 'a' && dst[i] <= 'z') dst[i] -= 32;
    int len = strlen(dst);
    if (len > 4 && strcmp(dst + len - 4, ".MPF") == 0)
        dst[len - 4] = '\0';
}

/* ── Gestione client ─────────────────────────────────────────────────────── */

static void handle_client(SOCKET client, const char *base_path) {
    char hdr[1024] = {0};
    int  hlen = 0;

    /* Leggi header JSON fino a \n */
    while (hlen < (int)sizeof(hdr) - 1) {
        char c;
        if (recv(client, &c, 1, 0) <= 0) break;
        if (c == '\n') break;
        hdr[hlen++] = c;
    }
    hdr[hlen] = '\0';
    printf("[REQ] %s\n", hdr);

    char cmd[32] = {0};
    /* Accetta sia "cmd" che "comando" */
    if (!json_get_str(hdr, "cmd", cmd, sizeof(cmd)))
        json_get_str(hdr, "comando", cmd, sizeof(cmd));

    char progetto[128] = {0};
    json_get_str(hdr, "progetto", progetto, sizeof(progetto));
    /* Maiuscolo */
    for (int i = 0; progetto[i]; i++)
        if (progetto[i] >= 'a' && progetto[i] <= 'z') progetto[i] -= 32;

    char wpd[MAX_PATH_LEN];
    snprintf(wpd, sizeof(wpd), "%s\\%s.WPD", base_path, progetto);

    /* ── CHECK ── */
    if (strcmp(cmd, "CHECK") == 0) {
        char files_json[2048] = {0};
        if (PathIsDirectoryA(wpd)) {
            char pattern[MAX_PATH_LEN];
            snprintf(pattern, sizeof(pattern), "%s\\*", wpd);
            WIN32_FIND_DATAA fd;
            HANDLE hf = FindFirstFileA(pattern, &fd);
            int first = 1;
            if (hf != INVALID_HANDLE_VALUE) {
                do {
                    if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
                    if (fd.cFileName[0] == '_') continue;
                    if (!first) strncat(files_json, ",", sizeof(files_json)-strlen(files_json)-1);
                    char e[256];
                    snprintf(e, sizeof(e), "\"%s\"", fd.cFileName);
                    strncat(files_json, e, sizeof(files_json)-strlen(files_json)-1);
                    first = 0;
                } while (FindNextFileA(hf, &fd));
                FindClose(hf);
            }
        }
        char resp[4096];
        snprintf(resp, sizeof(resp), "{\"stato\":\"ok\",\"files\":[%s]}\n", files_json);
        send(client, resp, strlen(resp), 0);
        return;
    }

    /* ── INVIA ── */
    if (strcmp(cmd, "INVIA") == 0) {
        char filename[256] = {0}, norm[256] = {0};
        long filesize = 0;
        json_get_str(hdr, "filename", filename, sizeof(filename));
        filesize = json_get_long(hdr, "filesize");
        normalize_name(filename, norm, sizeof(norm));

        if (filesize <= 0) {
            const char *err = "{\"stato\":\"errore\",\"msg\":\"filesize non valido\"}\n";
            send(client, err, strlen(err), 0);
            return;
        }

        /* Ricevi bytes */
        char *filebuf = (char*)malloc(filesize);
        if (!filebuf) {
            send(client, "{\"stato\":\"errore\",\"msg\":\"Memoria insufficiente\"}\n", 48, 0);
            return;
        }
        long received = 0;
        while (received < filesize) {
            int to_read = (int)(filesize - received);
            if (to_read > BUF_SIZE) to_read = BUF_SIZE;
            int r = recv(client, filebuf + received, to_read, 0);
            if (r <= 0) break;
            received += r;
        }
        if (received != filesize) {
            free(filebuf);
            char err[128];
            snprintf(err, sizeof(err), "{\"stato\":\"errore\",\"msg\":\"Incompleto %ld/%ld\"}\n", received, filesize);
            send(client, err, strlen(err), 0);
            return;
        }

        /* Prepara header NCK */
        char dnc_tmp[MAX_PATH_LEN];
        get_dnc_tmp(dnc_tmp, sizeof(dnc_tmp));
        if (!PathIsDirectoryA(dnc_tmp))
            CreateDirectoryA(dnc_tmp, NULL);

        char header_nck[256];
        snprintf(header_nck, sizeof(header_nck),
                 "%%_N_%s_MPF\r\n;$PATH=/_N_WKS_DIR/_N_%s_WPD\r\n",
                 norm, progetto);
        int hlen2 = strlen(header_nck);

        /* Normalizza LF→CRLF nel corpo del file.
           Sinumerik 840D PowerLine richiede CRLF su tutto il file.
           Alloca worst-case: ogni \n diventa \r\n → al massimo 2x */
        char *body_crlf = (char*)malloc(filesize * 2 + 1);
        if (!body_crlf) {
            free(filebuf);
            send(client, "{\"stato\":\"errore\",\"msg\":\"Errore allocazione CRLF\"}\n", 51, 0);
            return;
        }
        long body_len = 0;
        for (long ci = 0; ci < filesize; ci++) {
            unsigned char ch = (unsigned char)filebuf[ci];
            if (ch == '\n') {
                /* Aggiungi \r solo se non già preceduto da \r */
                if (body_len == 0 || body_crlf[body_len-1] != '\r')
                    body_crlf[body_len++] = '\r';
            }
            body_crlf[body_len++] = (char)ch;
        }
        free(filebuf);
        filebuf = NULL;

        /* Footer Sinumerik: \r\n% — se il corpo già finisce con \r\n non aggiungere altro \r\n */
        const char *footer = "\r\n%";
        int footer_len = 3;
        if (body_len >= 2 &&
            body_crlf[body_len-2] == '\r' && body_crlf[body_len-1] == '\n') {
            /* corpo finisce già con \r\n → footer è solo % */
            footer     = "%";
            footer_len = 1;
        }

        /* Componi: header + corpo CRLF + footer */
        long total2 = hlen2 + body_len + footer_len;
        char *outbuf = (char*)malloc(total2 + 1);
        if (!outbuf) {
            free(body_crlf);
            send(client, "{\"stato\":\"errore\",\"msg\":\"Errore allocazione output\"}\n", 52, 0);
            return;
        }
        memcpy(outbuf,           header_nck, hlen2);
        memcpy(outbuf + hlen2,   body_crlf,  body_len);
        memcpy(outbuf + hlen2 + body_len, footer, footer_len);
        free(body_crlf);

        /* Scrivi in D:\tmp\autoimport — unico path che funziona con USE_INTERN_PATH */
        char dest_path[MAX_PATH_LEN];
        snprintf(dest_path, sizeof(dest_path), "%s\\%s.MPF", dnc_tmp, norm);
        FILE *f = fopen(dest_path, "wb");
        if (!f) {
            free(outbuf);
            send(client, "{\"stato\":\"errore\",\"msg\":\"Impossibile scrivere file\"}\n", 52, 0);
            return;
        }
        fwrite(outbuf, 1, total2, f);
        fclose(f);
        /* NON free(outbuf) qui — serve nel loop per ri-scrivere dopo .ERR */

        printf("[OK] %s (%ld -> %ld bytes CRLF) -> %s\n", norm, filesize, total2, dest_path);

        call_transfer_dnc(dest_path);

        /* ── Attesa trasferimento (F3+F5) ──────────────────────────────────
           .ERR è TRANSITORIO: NCU occupata → DNCMachine riprova.
           Se DNCMachine rimuove anche il .MPF → lo riscriviamo da outbuf.
        ── */
        char err_path[MAX_PATH_LEN];
        snprintf(err_path, sizeof(err_path), "%s.ERR", dest_path);

        int transferred = 0;
        int err_count   = 0;
        int elapsed     = 0;

        while (elapsed < 90) {
            Sleep(2000);
            elapsed += 2;
            int file_exists = (GetFileAttributesA(dest_path) != INVALID_FILE_ATTRIBUTES);
            int err_exists  = (GetFileAttributesA(err_path)  != INVALID_FILE_ATTRIBUTES);

            if (!file_exists && !err_exists) { transferred = 1; break; }

            if (err_exists) {
                err_count++;
                DeleteFileA(err_path);
                if (!file_exists) {
                    /* DNCMachine ha rimosso il .MPF insieme al .ERR — riscrivilo */
                    FILE *fw = fopen(dest_path, "wb");
                    if (fw) { fwrite(outbuf, 1, total2, fw); fclose(fw); }
                    printf("[RETRY] %s riscritto dopo .ERR n.%d\n", norm, err_count);
                } else {
                    printf("[RETRY] %s .ERR n.%d cancellato\n", norm, err_count);
                }
                continue;
            }
            printf("[WAIT] %s... %ds\n", norm, elapsed);
        }

        free(outbuf); /* libera solo ora */

        /* Costruisci risposta JSON con escape backslash */
        char wpd_escaped[MAX_PATH_LEN * 2];
        int si = 0, di = 0;
        while (wpd[si] && di < (int)sizeof(wpd_escaped) - 2) {
            if (wpd[si] == '\\') wpd_escaped[di++] = '\\';
            wpd_escaped[di++] = wpd[si++];
        }
        wpd_escaped[di] = '\0';

        char resp[512];
        if (transferred) {
            snprintf(resp, sizeof(resp),
                     "{\"stato\":\"ok\",\"msg\":\"OK %s -> %s\"}\n", norm, wpd_escaped);
            printf("[OK] %s trasferito in NCU\n", norm);
        } else if (err_count > 0) {
            /* Timeout ma ci sono stati .ERR — il file è in coda, arriverà via autoimport */
            snprintf(resp, sizeof(resp),
                     "{\"stato\":\"ok\",\"msg\":\"OK %s -> in coda autoimport (%d retry NCU)\"}\n",
                     norm, err_count);
            printf("[OK] %s in coda autoimport dopo %d .ERR\n", norm, err_count);
        } else {
            snprintf(resp, sizeof(resp),
                     "{\"stato\":\"ok\",\"msg\":\"OK %s -> in coda autoimport\"}\n", norm);
            printf("[OK] %s in coda autoimport\n", norm);
        }

        send(client, resp, strlen(resp), 0);
        closesocket(client);
        client = INVALID_SOCKET;
        return;
    }

    send(client, "{\"stato\":\"errore\",\"msg\":\"Comando sconosciuto\"}\n", 47, 0);
}

/* ── Thread esportazione OpcUaLegacy.log sulla share ─────────────────────── */

static DWORD WINAPI export_thread(LPVOID unused) {
    (void)unused;

    char opcua_log[MAX_PATH_LEN];
    char share_dir[MAX_PATH_LEN];
    int  interval_ms;

    get_opcua_log(opcua_log, sizeof(opcua_log));
    get_share_dir(share_dir, sizeof(share_dir));
    interval_ms = get_export_interval();

    /* Assicura che share_dir termini con \ */
    int slen = strlen(share_dir);
    if (slen > 0 && share_dir[slen-1] != '\\') {
        share_dir[slen]   = '\\';
        share_dir[slen+1] = '\0';
    }

    printf("[EXPORT] OpcUa log: %s\n", opcua_log);
    printf("[EXPORT] Share dir: %s\n", share_dir);
    printf("[EXPORT] Intervallo: %d ms\n", interval_ms);

    /* Aspetta 15 secondi all'avvio — lascia tempo alla rete di connettersi */
    Sleep(15000);

    while (1) {
        SYSTEMTIME st;
        GetLocalTime(&st);
        char ts[32];
        snprintf(ts, sizeof(ts), "%04d-%02d-%02d %02d:%02d:%02d",
                 st.wYear, st.wMonth, st.wDay,
                 st.wHour, st.wMinute, st.wSecond);

        int opcua_ok = 0;
        char errori[256] = {0};

        /* 1. Copia OpcUaLegacy.log sulla share */
        if (GetFileAttributesA(opcua_log) != INVALID_FILE_ATTRIBUTES) {
            char dest[MAX_PATH_LEN];
            snprintf(dest, sizeof(dest), "%sOpcUaLegacy.log", share_dir);

            /* Leggi il file sorgente con FILE_SHARE_READ|WRITE
               — funziona anche se opcUa_Server_xp.exe lo tiene aperto */
            HANDLE hSrc = CreateFileA(opcua_log,
                GENERIC_READ,
                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);

            if (hSrc != INVALID_HANDLE_VALUE) {
                HANDLE hDst = CreateFileA(dest,
                    GENERIC_WRITE, 0, NULL,
                    CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);

                if (hDst != INVALID_HANDLE_VALUE) {
                    char buf[4096];
                    DWORD nr, nw;
                    opcua_ok = 1;
                    while (ReadFile(hSrc, buf, sizeof(buf), &nr, NULL) && nr > 0) {
                        if (!WriteFile(hDst, buf, nr, &nw, NULL) || nw != nr) {
                            opcua_ok = 0;
                            snprintf(errori, sizeof(errori),
                                     "ERR scrittura dest: %lu", GetLastError());
                            break;
                        }
                    }
                    CloseHandle(hDst);
                    if (opcua_ok)
                        printf("[EXPORT] %s OK\n", ts);
                    else
                        printf("[EXPORT] %s WARN %s\n", ts, errori);
                } else {
                    snprintf(errori, sizeof(errori),
                             "ERR apertura dest: %lu", GetLastError());
                    printf("[EXPORT] %s WARN %s\n", ts, errori);
                }
                CloseHandle(hSrc);
            } else {
                snprintf(errori, sizeof(errori),
                         "ERR apertura src: %lu", GetLastError());
                printf("[EXPORT] %s WARN %s\n", ts, errori);
            }
        } else {
            strncpy(errori, "WARN: OpcUaLegacy.log non trovato", sizeof(errori));
            printf("[EXPORT] %s %s\n", ts, errori);
        }

        /* 2. Heartbeat — xp_heartbeat.txt */
        char hb_path[MAX_PATH_LEN];
        snprintf(hb_path, sizeof(hb_path), "%sxp_heartbeat.txt", share_dir);
        FILE *hb = fopen(hb_path, "w");
        if (hb) {
            fprintf(hb, "ultimo_run=%s\n", ts);
            fprintf(hb, "opcua_log_ok=%s\n", opcua_ok ? "True" : "False");
            if (errori[0]) fprintf(hb, "errori=%s\n", errori);
            fclose(hb);
        }

        /* 3. Log esecuzione — esporta_log.txt (append) */
        char log_path[MAX_PATH_LEN];
        snprintf(log_path, sizeof(log_path), "%sesporta_log.txt", share_dir);
        FILE *lf = fopen(log_path, "a");
        if (lf) {
            if (!errori[0])
                fprintf(lf, "%s OK\n", ts);
            else
                fprintf(lf, "%s WARN %s\n", ts, errori);
            fclose(lf);
        }

        Sleep(interval_ms);
    }

    return 0;
}

/* ── Main ────────────────────────────────────────────────────────────────── */

int main(void) {
    init_cfg_path();
    init_vbs_mutex();

    /* Avvia thread esportazione OpcUa log in background */
    HANDLE hExport = CreateThread(NULL, 0, export_thread, NULL, 0, NULL);
    if (hExport) CloseHandle(hExport);
    else printf("[WARN] Thread esportazione non avviato\n");

    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2,2), &wsa) != 0) {
        fprintf(stderr, "ERRORE WSAStartup\n"); return 1;
    }

    int  port = get_port();
    char base[MAX_PATH_LEN];
    get_base_path(base, sizeof(base));

    SOCKET srv = socket(AF_INET, SOCK_STREAM, 0);
    if (srv == INVALID_SOCKET) { fprintf(stderr, "ERRORE socket\n"); return 1; }

    int opt = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, (char*)&opt, sizeof(opt));

    struct sockaddr_in addr = {0};
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port        = htons((u_short)port);

    if (bind(srv, (struct sockaddr*)&addr, sizeof(addr)) == SOCKET_ERROR) {
        fprintf(stderr, "ERRORE bind porta %d\n", port);
        closesocket(srv); WSACleanup(); return 1;
    }

    listen(srv, 5);
    printf("MachineServer avviato - porta %d - cartella: %s\n", port, base);
    printf("Header NCK: ATTIVO  (%%_N_PROG_MPF + PATH)\n");
    printf("VBS path: %s\n", DEFAULT_VBS_PATH);

    while (1) {
        struct sockaddr_in ca; int cl = sizeof(ca);
        SOCKET client = accept(srv, (struct sockaddr*)&ca, &cl);
        if (client == INVALID_SOCKET) continue;
        printf("[CONN] Client connesso\n");
        handle_client(client, base);
        if (client != INVALID_SOCKET) closesocket(client);
        printf("[CONN] Client disconnesso\n");
    }

    closesocket(srv); WSACleanup(); return 0;
}
