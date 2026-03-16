/*
 * server.c - MachineServer per trasferimento NC a Siemens 840D PowerLine
 * Versione con registrazione NCK via Job32dll.InterpretJob
 *
 * Compilazione (da Linux con MinGW):
 *   i686-w64-mingw32-gcc -o MachineServer.exe server.c -lws2_32 -lshlwapi
 *
 * Protocollo socket (porta configurabile in server_config.ini):
 *   CHECK: { "cmd":"CHECK", "progetto":"NOME" }
 *         → risposta JSON con lista file esistenti
 *   INVIA: { "cmd":"INVIA", "progetto":"NOME", "filename":"PROG", "filesize":N }
 *         → poi N bytes del file → risposta OK o ERRORE
 */

#include <winsock2.h>
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <shlwapi.h>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "shlwapi.lib")

/* ============================================================
 * Configurazione
 * ============================================================ */
#define CFG_FILE        "server_config.ini"
#define INI_MMC         "F:\\hmi_adv\\MMC.INI"
#define DEFAULT_PORT    9999
#define DEFAULT_BASE    "F:\\dh\\wks.dir"
#define DEFAULT_TMPDIR  "d:\\tmp"
#define JOB_FILENAME    "job_tmp.in"
#define BUF_SIZE        65536
#define MAX_PATH_LEN    512

/* ============================================================
 * Firma InterpretJob da Job32dll.dll
 * ============================================================ */
typedef int (__cdecl *InterpretJob_t)(const char *job_file);

static InterpretJob_t g_interpretJob = NULL;
static HMODULE        g_hJob         = NULL;

/* ============================================================
 * Helpers configurazione
 * ============================================================ */
static int get_port(void) {
    return (int)GetPrivateProfileIntA("server", "port", DEFAULT_PORT, CFG_FILE);
}

static void get_base_path(char *out, int n) {
    GetPrivateProfileStringA("server", "base_path", DEFAULT_BASE, out, n, CFG_FILE);
}

static void get_temp_dir(char *out, int n) {
    char buf[MAX_PATH_LEN];
    DWORD r = GetPrivateProfileStringA("DIRECTORIES", "TempDir", DEFAULT_TMPDIR,
                                       buf, sizeof(buf), INI_MMC);
    if (r == 0)
        GetPrivateProfileStringA("DIRECTORIES", "TempDir", DEFAULT_TMPDIR,
                                 buf, sizeof(buf), INI_MMC);
    strncpy(out, buf, n);
    out[n-1] = '\0';
}

/* ============================================================
 * Carica Job32dll.dll
 * ============================================================ */
static int load_job32dll(void) {
    g_hJob = LoadLibraryA("F:\\hmi_adv\\Job32dll.dll");
    if (!g_hJob)
        g_hJob = LoadLibraryA("Job32dll.dll");
    if (!g_hJob) {
        printf("[WARN] Job32dll.dll non trovata - registrazione NCK disabilitata\n");
        return 0;
    }
    g_interpretJob = (InterpretJob_t)GetProcAddress(g_hJob, "InterpretJob");
    if (!g_interpretJob) {
        printf("[WARN] InterpretJob non trovata in Job32dll.dll\n");
        FreeLibrary(g_hJob);
        g_hJob = NULL;
        return 0;
    }
    printf("[OK] Job32dll.dll caricata - registrazione NCK attiva\n");
    return 1;
}

/* ============================================================
 * Registra un programma nella NCK via InterpretJob
 * wpd_folder = "F:\dh\wks.dir\PROGETTO.WPD"
 * prog_name  = "NOMEFILE" (senza estensione, maiuscolo)
 * ============================================================ */
static void register_nck(const char *wpd_folder, const char *prog_name) {
    if (!g_interpretJob) {
        printf("[WARN] InterpretJob non disponibile - file inviato ma non registrato in NCK\n");
        return;
    }

    char tmp_dir[MAX_PATH_LEN];
    get_temp_dir(tmp_dir, sizeof(tmp_dir));

    /* Crea TempDir se non esiste */
    if (!PathIsDirectoryA(tmp_dir))
        CreateDirectoryA(tmp_dir, NULL);

    char job_path[MAX_PATH_LEN];
    snprintf(job_path, sizeof(job_path), "%s\\%s", tmp_dir, JOB_FILENAME);

    FILE *jf = fopen(job_path, "w");
    if (!jf) {
        printf("[WARN] Impossibile scrivere %s\n", job_path);
        return;
    }
    fprintf(jf, "LOAD %s\\%s\n", wpd_folder, prog_name);
    fclose(jf);

    printf("[NCK] Chiamata InterpretJob: LOAD %s\\%s\n", wpd_folder, prog_name);
    int ret = g_interpretJob(job_path);
    if (ret == 0)
        printf("[NCK] OK - programma registrato nella NCK\n");
    else
        printf("[NCK] WARN - InterpretJob ritornato %d\n", ret);
}

/* ============================================================
 * Parsing JSON minimo (estrae valore stringa/numero per chiave)
 * ============================================================ */
static int json_get_str(const char *json, const char *key, char *out, int n) {
    char search[64];
    snprintf(search, sizeof(search), "\"%s\"", key);
    const char *p = strstr(json, search);
    if (!p) return 0;
    p += strlen(search);
    while (*p == ' ' || *p == ':') p++;
    if (*p == '"') {
        p++;
        int i = 0;
        while (*p && *p != '"' && i < n-1) out[i++] = *p++;
        out[i] = '\0';
        return 1;
    }
    return 0;
}

static long json_get_long(const char *json, const char *key) {
    char buf[32];
    char search[64];
    snprintf(search, sizeof(search), "\"%s\"", key);
    const char *p = strstr(json, search);
    if (!p) return -1;
    p += strlen(search);
    while (*p == ' ' || *p == ':') p++;
    int i = 0;
    while ((*p >= '0' && *p <= '9') && i < 30) buf[i++] = *p++;
    buf[i] = '\0';
    return i > 0 ? atol(buf) : -1;
}

/* ============================================================
 * Normalizza nome file per Sinumerik:
 * - Maiuscolo
 * - Rimuove estensione .MPF o .mpf
 * ============================================================ */
static void normalize_name(const char *src, char *dst, int n) {
    strncpy(dst, src, n);
    dst[n-1] = '\0';
    /* Maiuscolo */
    for (int i = 0; dst[i]; i++)
        if (dst[i] >= 'a' && dst[i] <= 'z')
            dst[i] -= 32;
    /* Rimuovi .MPF */
    int len = strlen(dst);
    if (len > 4 && strcmp(dst + len - 4, ".MPF") == 0)
        dst[len - 4] = '\0';
}

/* ============================================================
 * Gestione connessione client
 * ============================================================ */
static void handle_client(SOCKET client, const char *base_path) {
    char hdr_buf[1024] = {0};
    int  hdr_len = 0;

    /* Leggi header JSON fino a '\n' */
    while (hdr_len < (int)sizeof(hdr_buf) - 1) {
        char c;
        int r = recv(client, &c, 1, 0);
        if (r <= 0) break;
        if (c == '\n') break;
        hdr_buf[hdr_len++] = c;
    }
    hdr_buf[hdr_len] = '\0';
    printf("[REQ] %s\n", hdr_buf);

    char cmd[32] = {0};
    json_get_str(hdr_buf, "cmd", cmd, sizeof(cmd));

    /* ---- CHECK: elenca file esistenti ---- */
    if (strcmp(cmd, "CHECK") == 0) {
        char progetto[128] = {0};
        json_get_str(hdr_buf, "progetto", progetto, sizeof(progetto));

        char wpd_folder[MAX_PATH_LEN];
        snprintf(wpd_folder, sizeof(wpd_folder), "%s\\%s.WPD", base_path, progetto);

        char resp[4096];
        if (!PathIsDirectoryA(wpd_folder)) {
            snprintf(resp, sizeof(resp),
                     "{\"stato\":\"ok\",\"files\":[]}\n");
        } else {
            char pattern[MAX_PATH_LEN];
            snprintf(pattern, sizeof(pattern), "%s\\*", wpd_folder);
            WIN32_FIND_DATAA fd;
            HANDLE hf = FindFirstFileA(pattern, &fd);
            char files_json[2048] = {0};
            int first = 1;
            if (hf != INVALID_HANDLE_VALUE) {
                do {
                    if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
                    if (fd.cFileName[0] == '_') continue; /* salta _dhinf.000 */
                    if (!first) strncat(files_json, ",", sizeof(files_json)-strlen(files_json)-1);
                    char entry[256];
                    snprintf(entry, sizeof(entry), "\"%s\"", fd.cFileName);
                    strncat(files_json, entry, sizeof(files_json)-strlen(files_json)-1);
                    first = 0;
                } while (FindNextFileA(hf, &fd));
                FindClose(hf);
            }
            snprintf(resp, sizeof(resp),
                     "{\"stato\":\"ok\",\"files\":[%s]}\n", files_json);
        }
        printf("[CHECK] %s → %s", progetto, resp);
        send(client, resp, strlen(resp), 0);
        return;
    }

    /* ---- INVIA: ricevi e salva file ---- */
    if (strcmp(cmd, "INVIA") == 0) {
        char progetto[128] = {0}, filename[256] = {0}, norm_name[256] = {0};
        long filesize = 0;

        json_get_str(hdr_buf, "progetto", progetto, sizeof(progetto));
        json_get_str(hdr_buf, "filename", filename, sizeof(filename));
        filesize = json_get_long(hdr_buf, "filesize");
        normalize_name(filename, norm_name, sizeof(norm_name));

        /* Cartella destinazione */
        char wpd_folder[MAX_PATH_LEN], dest_path[MAX_PATH_LEN];
        snprintf(wpd_folder, sizeof(wpd_folder), "%s\\%s.WPD", base_path, progetto);
        snprintf(dest_path,  sizeof(dest_path),  "%s\\%s", wpd_folder, norm_name);

        if (!PathIsDirectoryA(wpd_folder)) {
            const char *err = "{\"stato\":\"errore\","
                "\"msg\":\"Cartella progetto non esiste. Crearla prima dall'HMI Sinumerik.\"}\n";
            send(client, err, strlen(err), 0);
            printf("[ERRORE] Cartella non trovata: %s\n", wpd_folder);
            return;
        }

        /* Ricevi bytes e scrivi file */
        FILE *out = fopen(dest_path, "wb");
        if (!out) {
            const char *err = "{\"stato\":\"errore\",\"msg\":\"Impossibile scrivere il file\"}\n";
            send(client, err, strlen(err), 0);
            printf("[ERRORE] fopen fallito: %s\n", dest_path);
            return;
        }

        char *buf = (char *)malloc(BUF_SIZE);
        if (!buf) { fclose(out); return; }

        long received = 0;
        while (received < filesize) {
            int to_read = (int)(filesize - received);
            if (to_read > BUF_SIZE) to_read = BUF_SIZE;
            int r = recv(client, buf, to_read, 0);
            if (r <= 0) break;
            fwrite(buf, 1, r, out);
            received += r;
        }
        free(buf);
        fclose(out);

        if (received != filesize) {
            char err[256];
            snprintf(err, sizeof(err),
                "{\"stato\":\"errore\",\"msg\":\"Trasferimento incompleto: %ld/%ld bytes\"}\n",
                received, filesize);
            send(client, err, strlen(err), 0);
            printf("[ERRORE] Incompleto: %ld/%ld\n", received, filesize);
            return;
        }

        printf("[OK] %s (%ld bytes) → %s\n", norm_name, filesize, dest_path);

        /* ---- REGISTRA NELLA NCK ---- */
        register_nck(wpd_folder, norm_name);

        char resp[512];
        snprintf(resp, sizeof(resp),
                 "{\"stato\":\"ok\",\"msg\":\"OK  %s  (%ld bytes) -> %s\"}\n",
                 norm_name, filesize, wpd_folder);
        send(client, resp, strlen(resp), 0);
        return;
    }

    /* Comando sconosciuto */
    const char *unk = "{\"stato\":\"errore\",\"msg\":\"Comando sconosciuto\"}\n";
    send(client, unk, strlen(unk), 0);
}

/* ============================================================
 * Main
 * ============================================================ */
int main(void) {
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2,2), &wsa) != 0) {
        fprintf(stderr, "ERRORE: WSAStartup fallito\n");
        return 1;
    }

    int   port      = get_port();
    char  base_path[MAX_PATH_LEN];
    get_base_path(base_path, sizeof(base_path));

    /* Carica Job32dll.dll per registrazione NCK */
    load_job32dll();

    SOCKET srv = socket(AF_INET, SOCK_STREAM, 0);
    if (srv == INVALID_SOCKET) {
        fprintf(stderr, "ERRORE: impossibile creare socket\n");
        return 1;
    }

    int opt = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, (char *)&opt, sizeof(opt));

    struct sockaddr_in addr = {0};
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port        = htons((u_short)port);

    if (bind(srv, (struct sockaddr *)&addr, sizeof(addr)) == SOCKET_ERROR) {
        fprintf(stderr, "ERRORE: bind fallito sulla porta %d (porta gia' in uso?)\n", port);
        closesocket(srv);
        WSACleanup();
        return 1;
    }

    listen(srv, 5);
    printf("MachineServer avviato - porta %d - cartella: %s\n", port, base_path);
    printf("Registrazione NCK: %s\n", g_interpretJob ? "ATTIVA (Job32dll)" : "DISATTIVA");

    while (1) {
        struct sockaddr_in client_addr;
        int client_len = sizeof(client_addr);
        SOCKET client = accept(srv, (struct sockaddr *)&client_addr, &client_len);
        if (client == INVALID_SOCKET) continue;

        printf("[CONN] Client connesso\n");
        handle_client(client, base_path);
        closesocket(client);
        printf("[CONN] Client disconnesso\n");
    }

    if (g_hJob) FreeLibrary(g_hJob);
    closesocket(srv);
    WSACleanup();
    return 0;
}
