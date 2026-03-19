/*
 * server.c - MachineServer per trasferimento NC a Siemens 840D PowerLine
 * Compilazione: i686-w64-mingw32-gcc -static -static-libgcc -o MachineServer.exe server.c -lws2_32 -lshlwapi
 */

#include <winsock2.h>
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <shlwapi.h>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "shlwapi.lib")

#define CFG_FILE         "server_config.ini"
#define DEFAULT_PORT     9999
#define DEFAULT_BASE     "F:\\dh\\wks.dir"
#define DEFAULT_DNC_TMP  "F:\\ADD_ON\\DNC\\TMP"
#define DEFAULT_VBS_PATH "F:\\ADD_ON\\DNC\\transfer_dnc.vbs"
#define BUF_SIZE         65536
#define MAX_PATH_LEN     512

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

/* ── VBS con path file specifico ─────────────────────────────────────────── */

static void call_transfer_dnc(const char *filepath) {
    char vbs[MAX_PATH_LEN];
    char cmd[MAX_PATH_LEN * 3];
    get_vbs_path(vbs, sizeof(vbs));
    if (filepath && filepath[0])
        snprintf(cmd, sizeof(cmd), "cscript //Nologo \"%s\" \"%s\" > NUL 2>&1", vbs, filepath);
    else
        snprintf(cmd, sizeof(cmd), "cscript //Nologo \"%s\" > NUL 2>&1", vbs);
    printf("[DNC] %s\n", cmd);
    int ret = system(cmd);
    if (ret == 0)
        printf("[DNC] OK\n");
    else
        printf("[DNC] ret=%d\n", ret);
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

        /* Scrivi in DNC TMP */
        char dest_path[MAX_PATH_LEN];
        /* Scrivi in TMP con estensione .MPF — TransferAutom filtra per estensione */
        snprintf(dest_path, sizeof(dest_path), "%s\\%s.MPF", dnc_tmp, norm);
        FILE *f = fopen(dest_path, "wb");
        if (!f) {
            free(outbuf);
            send(client, "{\"stato\":\"errore\",\"msg\":\"Impossibile scrivere file\"}\n", 52, 0);
            return;
        }
        fwrite(outbuf, 1, total2, f);
        fclose(f);
        free(outbuf);

        printf("[OK] %s (%ld -> %ld bytes CRLF) -> %s\n", norm, filesize, total2, dest_path);

        /* Rispondi OK PRIMA di chiamare il VBS
           ATTENZIONE: i backslash di wpd vanno escapati come \\ in JSON */
        char wpd_escaped[MAX_PATH_LEN * 2];
        int si = 0, di = 0;
        while (wpd[si] && di < (int)sizeof(wpd_escaped) - 2) {
            if (wpd[si] == '\\') wpd_escaped[di++] = '\\';
            wpd_escaped[di++] = wpd[si++];
        }
        wpd_escaped[di] = '\0';

        char resp[512];
        snprintf(resp, sizeof(resp),
                 "{\"stato\":\"ok\",\"msg\":\"OK %s -> %s\"}\n", norm, wpd_escaped);
        send(client, resp, strlen(resp), 0);
        closesocket(client);
        client = INVALID_SOCKET;

        /* Chiama VBS con path file specifico */
        call_transfer_dnc(dest_path);
        return;
    }

    send(client, "{\"stato\":\"errore\",\"msg\":\"Comando sconosciuto\"}\n", 47, 0);
}

/* ── Main ────────────────────────────────────────────────────────────────── */

int main(void) {
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
