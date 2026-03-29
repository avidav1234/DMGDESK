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

/* TransferAutom — avvia ciclo import automatico senza aspettare file specifico */
static void call_transfer_autom(void) {
    char vbs[MAX_PATH_LEN];
    char cmd[MAX_PATH_LEN * 3];
    get_vbs_path(vbs, sizeof(vbs));
    snprintf(cmd, sizeof(cmd), "cscript //Nologo \"%s\" > NUL 2>&1", vbs);
    Sleep(300);
    if (g_vbs_mutex) WaitForSingleObject(g_vbs_mutex, 15000);
    printf("[DNC AUTOM] %s\n", cmd);
    int ret = system(cmd);
    if (ret == 0) printf("[DNC AUTOM] OK\n");
    else          printf("[DNC AUTOM] ret=%d\n", ret);
    if (g_vbs_mutex) ReleaseMutex(g_vbs_mutex);
}

/* Scrive un file MPF in dnc_tmp con header NCK e CRLF.
   Restituisce 1 se OK, 0 se errore (messaggio in err_out). */
static int write_mpf_file(const char *norm, const char *progetto,
                           const char *filebuf, long filesize,
                           const char *dnc_tmp,
                           char *dest_out, int dest_n,
                           char *err_out,  int err_n) {
    /* Header NCK */
    char header_nck[256];
    snprintf(header_nck, sizeof(header_nck),
             "%%_N_%s_MPF\r\n;$PATH=/_N_WKS_DIR/_N_%s_WPD\r\n",
             norm, progetto);
    int hlen = strlen(header_nck);

    /* Normalizza LF → CRLF */
    char *body = (char*)malloc(filesize * 2 + 1);
    if (!body) { snprintf(err_out, err_n, "malloc CRLF"); return 0; }
    long blen = 0;
    for (long i = 0; i < filesize; i++) {
        unsigned char ch = (unsigned char)filebuf[i];
        if (ch == '\n' && (blen == 0 || body[blen-1] != '\r'))
            body[blen++] = '\r';
        body[blen++] = (char)ch;
    }

    /* Footer */
    const char *footer = (blen >= 2 &&
                          body[blen-2] == '\r' && body[blen-1] == '\n')
                         ? "%" : "\r\n%";
    int flen = strlen(footer);

    /* Componi */
    long total = hlen + blen + flen;
    char *outbuf = (char*)malloc(total + 1);
    if (!outbuf) { free(body); snprintf(err_out, err_n, "malloc output"); return 0; }
    memcpy(outbuf,        header_nck, hlen);
    memcpy(outbuf + hlen, body,       blen);
    memcpy(outbuf + hlen + blen, footer, flen);
    free(body);

    /* Path destinazione */
    snprintf(dest_out, dest_n, "%s\\%s.MPF", dnc_tmp, norm);

    /* Scrivi */
    FILE *f = fopen(dest_out, "wb");
    if (!f) {
        free(outbuf);
        snprintf(err_out, err_n, "fopen %s", dest_out);
        return 0;
    }
    fwrite(outbuf, 1, total, f);
    fclose(f);
    free(outbuf);
    printf("[MPF] scritto %s (%ld bytes)\n", dest_out, total);
    return 1;
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

/* Forward declarations */
static void handle_batch(SOCKET client, const char *progetto_in);

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
    if (!json_get_str(hdr, "cmd", cmd, sizeof(cmd)))
        json_get_str(hdr, "comando", cmd, sizeof(cmd));

    char progetto[128] = {0};
    json_get_str(hdr, "progetto", progetto, sizeof(progetto));
    for (int i = 0; progetto[i]; i++)
        if (progetto[i] >= 'a' && progetto[i] <= 'z') progetto[i] -= 32;

    char wpd[MAX_PATH_LEN];
    snprintf(wpd, sizeof(wpd), "%s\\%s.WPD", base_path, progetto);

    /* ── INVIA_BATCH — tutti i file in una sola chiamata ── */
    if (strcmp(cmd, "INVIA_BATCH") == 0) {
        handle_batch(client, progetto);
        return;
    }

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

    /* ── INVIA (file singolo) ── */
    if (strcmp(cmd, "INVIA") == 0) {
        char filename[256] = {0}, norm[256] = {0};
        long filesize = 0;
        json_get_str(hdr, "filename", filename, sizeof(filename));
        filesize = json_get_long(hdr, "filesize");
        normalize_name(filename, norm, sizeof(norm));

        if (filesize <= 0) {
            send(client, "{\"stato\":\"errore\",\"msg\":\"filesize non valido\"}\n", 47, 0);
            return;
        }
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

        char dnc_tmp[MAX_PATH_LEN];
        get_dnc_tmp(dnc_tmp, sizeof(dnc_tmp));
        if (!PathIsDirectoryA(dnc_tmp)) CreateDirectoryA(dnc_tmp, NULL);

        char dest[MAX_PATH_LEN] = {0};
        char errbuf[256] = {0};
        if (!write_mpf_file(norm, progetto, filebuf, filesize,
                            dnc_tmp, dest, sizeof(dest), errbuf, sizeof(errbuf))) {
            free(filebuf);
            char resp[512];
            snprintf(resp, sizeof(resp), "{\"stato\":\"errore\",\"msg\":\"%s\"}\n", errbuf);
            send(client, resp, strlen(resp), 0);
            return;
        }

        call_transfer_dnc(dest);

        /* Attesa trasferimento */
        char err_path[MAX_PATH_LEN];
        snprintf(err_path, sizeof(err_path), "%s.ERR", dest);
        int transferred = 0, err_count = 0, elapsed = 0;

        /* Rileggi outbuf per eventuale retry */
        long filesize2 = filesize;
        char *filebuf2 = filebuf;

        while (elapsed < 90) {
            Sleep(2000); elapsed += 2;
            int fe = (GetFileAttributesA(dest)     != INVALID_FILE_ATTRIBUTES);
            int ee = (GetFileAttributesA(err_path) != INVALID_FILE_ATTRIBUTES);
            if (!fe && !ee) { transferred = 1; break; }
            if (ee) {
                err_count++;
                DeleteFileA(err_path);
                if (!fe) {
                    FILE *fw = fopen(dest, "wb");
                    /* Riscrivi — dobbiamo rigenerare il file */
                    char dest2[MAX_PATH_LEN] = {0};
                    char eb2[256] = {0};
                    write_mpf_file(norm, progetto, filebuf2, filesize2,
                                   dnc_tmp, dest2, sizeof(dest2), eb2, sizeof(eb2));
                    if (fw) fclose(fw);
                    printf("[RETRY] %s riscritto dopo .ERR n.%d\n", norm, err_count);
                }
            }
            printf("[WAIT] %s... %ds\n", norm, elapsed);
        }
        free(filebuf);

        char wpd_escaped[MAX_PATH_LEN * 2];
        int si = 0, di = 0;
        while (wpd[si] && di < (int)sizeof(wpd_escaped) - 2) {
            if (wpd[si] == '\\') wpd_escaped[di++] = '\\';
            wpd_escaped[di++] = wpd[si++];
        }
        wpd_escaped[di] = '\0';

        char resp[512];
        if (transferred)
            snprintf(resp, sizeof(resp), "{\"stato\":\"ok\",\"msg\":\"OK %s -> %s\"}\n", norm, wpd_escaped);
        else if (err_count > 0)
            snprintf(resp, sizeof(resp), "{\"stato\":\"ok\",\"msg\":\"OK %s -> in coda autoimport (%d retry NCU)\"}\n", norm, err_count);
        else
            snprintf(resp, sizeof(resp), "{\"stato\":\"ok\",\"msg\":\"OK %s -> in coda autoimport\"}\n", norm);

        send(client, resp, strlen(resp), 0);
        closesocket(client);
        return;
    }

    send(client, "{\"stato\":\"errore\",\"msg\":\"Comando sconosciuto\"}\n", 47, 0);
}


/* ── INVIA_BATCH ──────────────────────────────────────────────────────────────
   Fasi:
   1. Ricevi tutti i file e scrivili in dnc_tmp
   2. Chiama TransferAutom una sola volta
   3. Monitora ogni file per max 120s:
      - file sparito            → OK trasferito
      - .ERR trovato            → cancella .ERR, riscrivi file, riprova (max 5x)
      - timeout con err_count>0 → in coda autoimport (DNCMachine completerà)
      - timeout senza nulla     → in coda autoimport
   4. Risponde JSON con dettaglio per ogni file
─────────────────────────────────────────────────────────────────────────────*/

#define BATCH_MAX_FILES  256
#define BATCH_MAX_RETRY    5    /* max tentativi dopo .ERR per ogni file */
#define BATCH_TIMEOUT_S  120    /* secondi di attesa massima */

typedef struct {
    char  nome[256];
    char  dest[MAX_PATH_LEN];
    int   scritto;       /* file scritto su disco OK */
    int   ok;            /* trasferito alla NCU */
    int   err_count;     /* .ERR ricevuti */
    char  msg[128];
    char *outbuf;        /* copia del contenuto per retry */
    long  outbuf_len;
} BatchFile;

static void handle_batch(SOCKET client, const char *progetto_in) {
    char dnc_tmp[MAX_PATH_LEN];
    get_dnc_tmp(dnc_tmp, sizeof(dnc_tmp));
    if (!PathIsDirectoryA(dnc_tmp)) CreateDirectoryA(dnc_tmp, NULL);

    char progetto[128];
    strncpy(progetto, progetto_in, sizeof(progetto));
    progetto[sizeof(progetto)-1] = '\0';
    for (int i = 0; progetto[i]; i++)
        if (progetto[i] >= 'a' && progetto[i] <= 'z') progetto[i] -= 32;

    BatchFile *bf = (BatchFile*)calloc(BATCH_MAX_FILES, sizeof(BatchFile));
    if (!bf) { send(client, "{\"stato\":\"errore\",\"msg\":\"OOM\"}\n", 30, 0); return; }
    int n = 0;

    /* ── Fase 1: ricevi e scrivi tutti i file ────────────────────────────── */
    while (n < BATCH_MAX_FILES) {
        char fhdr[512] = {0}; int fhlen = 0;
        while (fhlen < (int)sizeof(fhdr)-1) {
            char c; int r = recv(client, &c, 1, 0);
            if (r <= 0) goto phase2;
            if (c == '\n') break;
            fhdr[fhlen++] = c;
        }
        if (!fhdr[0]) break;

        char filename[256] = {0}; long filesize = 0;
        json_get_str(fhdr, "filename", filename, sizeof(filename));
        filesize = json_get_long(fhdr, "filesize");
        normalize_name(filename, bf[n].nome, sizeof(bf[n].nome));

        if (filesize <= 0 || !bf[n].nome[0]) {
            snprintf(bf[n].msg, sizeof(bf[n].msg), "header non valido");
            n++; continue;
        }

        char *raw = (char*)malloc(filesize);
        if (!raw) { snprintf(bf[n].msg, sizeof(bf[n].msg), "OOM"); n++; continue; }
        long got = 0;
        while (got < filesize) {
            int nr = (int)(filesize-got); if (nr > BUF_SIZE) nr = BUF_SIZE;
            int r = recv(client, raw+got, nr, 0);
            if (r <= 0) { free(raw); goto phase2; }
            got += r;
        }

        char errbuf[256] = {0};
        if (write_mpf_file(bf[n].nome, progetto, raw, filesize,
                           dnc_tmp, bf[n].dest, sizeof(bf[n].dest),
                           errbuf, sizeof(errbuf))) {
            bf[n].scritto = 1;
            /* Leggi il file scritto per tenerlo in memoria (retry) */
            FILE *ff = fopen(bf[n].dest, "rb");
            if (ff) {
                fseek(ff, 0, SEEK_END); bf[n].outbuf_len = ftell(ff); rewind(ff);
                bf[n].outbuf = (char*)malloc(bf[n].outbuf_len);
                if (bf[n].outbuf) fread(bf[n].outbuf, 1, bf[n].outbuf_len, ff);
                fclose(ff);
            }
            printf("[BATCH] scritto %s\n", bf[n].nome);
        } else {
            snprintf(bf[n].msg, sizeof(bf[n].msg), "write err: %.80s", errbuf);
            printf("[BATCH] ERR scrittura %s: %s\n", bf[n].nome, errbuf);
        }
        free(raw); n++;
    }

phase2:
    /* ── Fase 2: TransferAutom una sola volta ────────────────────────────── */
    int n_scritti = 0;
    for (int i = 0; i < n; i++) if (bf[i].scritto) n_scritti++;
    if (n_scritti > 0) {
        printf("[BATCH] %d file scritti, TransferAutom...\n", n_scritti);
        call_transfer_autom();
    }

    /* ── Fase 3: monitora con retry ──────────────────────────────────────── */
    int elapsed = 0, pending = n_scritti;
    while (elapsed < BATCH_TIMEOUT_S && pending > 0) {
        Sleep(2000); elapsed += 2; pending = 0;
        for (int i = 0; i < n; i++) {
            if (!bf[i].scritto || bf[i].ok) continue;
            /* Blocco per file con troppi .ERR — lascia in coda autoimport */
            if (bf[i].err_count >= BATCH_MAX_RETRY) {
                snprintf(bf[i].msg, sizeof(bf[i].msg),
                         "max retry (%d .ERR) — in coda autoimport", bf[i].err_count);
                bf[i].ok = 1; /* considera risolto, DNCMachine lo processerà */
                printf("[BATCH] %s: max retry raggiunti, in coda\n", bf[i].nome);
                continue;
            }

            char err_path[MAX_PATH_LEN];
            snprintf(err_path, sizeof(err_path), "%s.ERR", bf[i].dest);
            int fe = (GetFileAttributesA(bf[i].dest)  != INVALID_FILE_ATTRIBUTES);
            int ee = (GetFileAttributesA(err_path)    != INVALID_FILE_ATTRIBUTES);

            if (!fe && !ee) {
                /* File sparito senza .ERR = trasferito correttamente */
                bf[i].ok = 1;
                snprintf(bf[i].msg, sizeof(bf[i].msg),
                         "OK — trasferito in %ds", elapsed);
                printf("[BATCH] %s OK in %ds\n", bf[i].nome, elapsed);
                continue;
            }
            if (ee) {
                /* .ERR trovato — cancella, riscrivi, riprova */
                bf[i].err_count++;
                DeleteFileA(err_path);
                if (!fe && bf[i].outbuf) {
                    /* DNCMachine ha rimosso il .MPF insieme al .ERR — riscrivi */
                    FILE *fw = fopen(bf[i].dest, "wb");
                    if (fw) {
                        fwrite(bf[i].outbuf, 1, bf[i].outbuf_len, fw);
                        fclose(fw);
                        printf("[BATCH] %s riscritto (tentativo %d/%d)\n",
                               bf[i].nome, bf[i].err_count, BATCH_MAX_RETRY);
                    }
                } else {
                    printf("[BATCH] %s .ERR cancellato (tentativo %d/%d)\n",
                           bf[i].nome, bf[i].err_count, BATCH_MAX_RETRY);
                }
                pending++;
                continue;
            }
            /* File ancora presente, nessun .ERR — semplicemente in attesa */
            pending++;
        }
        if (pending > 0)
            printf("[BATCH] %ds — %d file ancora pending\n", elapsed, pending);
    }

    /* Segna timeout per i non risolti */
    for (int i = 0; i < n; i++) {
        if (bf[i].scritto && !bf[i].ok) {
            if (bf[i].err_count > 0)
                snprintf(bf[i].msg, sizeof(bf[i].msg),
                         "timeout — %d .ERR, in coda autoimport", bf[i].err_count);
            else
                snprintf(bf[i].msg, sizeof(bf[i].msg),
                         "timeout — in coda autoimport");
        }
        if (!bf[i].scritto && !bf[i].msg[0])
            strncpy(bf[i].msg, "errore scrittura", sizeof(bf[i].msg));
        if (bf[i].outbuf) { free(bf[i].outbuf); bf[i].outbuf = NULL; }
    }

    /* ── Fase 4: risposta JSON dettagliata ───────────────────────────────── */
    int n_ok = 0, n_err = 0;
    for (int i = 0; i < n; i++) {
        /* ok = trasferito O in coda (DNCMachine completerà) */
        if (bf[i].scritto) n_ok++; else n_err++;
    }

    /* Costruisci JSON: {"stato":"ok","totale":N,"ok":X,"errori":Y,
       "dettaglio":[{"nome":"F1","ok":true,"msg":"..."},...]} */
    char *resp = (char*)malloc(n * 256 + 256);
    if (!resp) {
        send(client, "{\"stato\":\"errore\",\"msg\":\"OOM resp\"}\n", 35, 0);
        free(bf); return;
    }
    int rp = 0;
    rp += sprintf(resp+rp,
        "{\"stato\":\"ok\",\"totale\":%d,\"ok\":%d,\"errori\":%d,\"dettaglio\":[",
        n, n_ok, n_err);
    for (int i = 0; i < n; i++) {
        /* Escape backslash e virgolette nel msg */
        char safe_msg[256] = {0};
        int si = 0, di = 0;
        while (bf[i].msg[si] && di < 250) {
            if (bf[i].msg[si] == '"' || bf[i].msg[si] == '\\')
                safe_msg[di++] = '\\';
            safe_msg[di++] = bf[i].msg[si++];
        }
        rp += sprintf(resp+rp,
            "%s{\"nome\":\"%s\",\"ok\":%s,\"err_count\":%d,\"msg\":\"%s\"}",
            i ? "," : "",
            bf[i].nome,
            (bf[i].scritto) ? "true" : "false",
            bf[i].err_count,
            safe_msg);
    }
    rp += sprintf(resp+rp, "]}\n");

    send(client, resp, rp, 0);
    printf("[BATCH] done: %d OK, %d ERR\n", n_ok, n_err);
    free(resp);
    free(bf);
}

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
