/*
 * MachineServer - Server TCP per DMG Sinumerik 840D
 * Compatibile Windows XP / 2000 - nessuna dipendenza
 * Compilare con: gcc -o MachineServer.exe server.c -lws2_32
 * Oppure con MinGW: mingw32-gcc -o MachineServer.exe server.c -lws2_32
 */

#define _WIN32_WINNT 0x0501  /* Windows XP */
#include <winsock2.h>
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#pragma comment(lib, "ws2_32.lib")

/* ── Configurazione ─────────────────────────────────────────────────────── */

#define DEFAULT_PORT     9999
#define DEFAULT_BASEPATH "F:\\dh\\wks.dir"
#define CONFIG_FILE      "server_config.ini"
#define MAX_PATH_LEN     512
#define BUFFER_SIZE      8192
#define LOG_FILE         "server_log.txt"

static int   g_port = DEFAULT_PORT;
static char  g_basepath[MAX_PATH_LEN] = DEFAULT_BASEPATH;
static HANDLE g_log_mutex;

/* ── Log ────────────────────────────────────────────────────────────────── */

void log_msg(const char *msg)
{
    SYSTEMTIME st;
    GetLocalTime(&st);

    WaitForSingleObject(g_log_mutex, INFINITE);

    /* Stampa su console */
    printf("[%02d:%02d:%02d] %s\n", st.wHour, st.wMinute, st.wSecond, msg);
    fflush(stdout);

    /* Scrivi su file */
    FILE *f = fopen(LOG_FILE, "a");
    if (f) {
        fprintf(f, "[%04d-%02d-%02d %02d:%02d:%02d] %s\n",
                st.wYear, st.wMonth, st.wDay,
                st.wHour, st.wMinute, st.wSecond, msg);
        fclose(f);
    }

    ReleaseMutex(g_log_mutex);
}

/* ── Config INI ─────────────────────────────────────────────────────────── */

void load_config(void)
{
    FILE *f = fopen(CONFIG_FILE, "r");
    if (!f) {
        /* Crea config di default */
        f = fopen(CONFIG_FILE, "w");
        if (f) {
            fprintf(f, "[server]\n");
            fprintf(f, "port=%d\n", DEFAULT_PORT);
            fprintf(f, "base_path=%s\n", DEFAULT_BASEPATH);
            fclose(f);
        }
        return;
    }

    char line[MAX_PATH_LEN];
    while (fgets(line, sizeof(line), f)) {
        /* Rimuovi newline */
        int len = strlen(line);
        while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r'))
            line[--len] = '\0';

        if (strncmp(line, "port=", 5) == 0)
            g_port = atoi(line + 5);
        else if (strncmp(line, "base_path=", 10) == 0)
            strncpy(g_basepath, line + 10, MAX_PATH_LEN - 1);
    }
    fclose(f);
}

/* ── Helpers JSON minimale ──────────────────────────────────────────────── */

/* Estrae il valore di una chiave stringa: "key":"value" -> value */
int json_get_string(const char *json, const char *key, char *out, int out_size)
{
    char search[256];
    sprintf(search, "\"%s\"", key);
    const char *p = strstr(json, search);
    if (!p) return 0;

    p += strlen(search);
    while (*p == ' ' || *p == ':' || *p == ' ') p++;
    if (*p != '"') return 0;
    p++; /* salta " iniziale */

    int i = 0;
    while (*p && *p != '"' && i < out_size - 1) {
        if (*p == '\\') p++; /* skip escape */
        out[i++] = *p++;
    }
    out[i] = '\0';
    return 1;
}

/* Estrae valore intero: "key":1234 -> 1234 */
int json_get_int(const char *json, const char *key)
{
    char search[256];
    sprintf(search, "\"%s\"", key);
    const char *p = strstr(json, search);
    if (!p) return 0;

    p += strlen(search);
    while (*p == ' ' || *p == ':') p++;
    return atoi(p);
}

/* Conta quanti file ci sono nell'array "files":["a","b",...] */
int json_count_files(const char *json)
{
    const char *p = strstr(json, "\"files\"");
    if (!p) return 0;
    p = strchr(p, '[');
    if (!p) return 0;

    int count = 0;
    while (*p && *p != ']') {
        if (*p == '"') count++;
        p++;
        /* Salta stringa */
        while (*p && *p != '"' && *p != ']') p++;
        if (*p == '"') p++; /* fine stringa */
    }
    return count / 2; /* ogni file ha " iniziale e " finale */
}

/* Estrae i nomi file dall'array "files":["a","b",...] */
int json_get_files(const char *json, char files[][MAX_PATH_LEN], int max_files)
{
    const char *p = strstr(json, "\"files\"");
    if (!p) return 0;
    p = strchr(p, '[');
    if (!p) return 0;
    p++;

    int count = 0;
    while (*p && *p != ']' && count < max_files) {
        while (*p == ' ' || *p == ',') p++;
        if (*p == '"') {
            p++;
            int i = 0;
            while (*p && *p != '"' && i < MAX_PATH_LEN - 1) {
                if (*p == '\\') p++;
                files[count][i++] = *p++;
            }
            files[count][i] = '\0';
            if (*p == '"') p++;
            count++;
        } else {
            p++;
        }
    }
    return count;
}

/* ── Crea directory ricorsivamente ──────────────────────────────────────── */

void create_dir_recursive(const char *path)
{
    char tmp[MAX_PATH_LEN];
    strncpy(tmp, path, MAX_PATH_LEN - 1);
    int len = strlen(tmp);

    for (int i = 1; i < len; i++) {
        if (tmp[i] == '\\' || tmp[i] == '/') {
            tmp[i] = '\0';
            CreateDirectoryA(tmp, NULL);
            tmp[i] = '\\';
        }
    }
    CreateDirectoryA(tmp, NULL);
}

/* ── Ricevi esattamente N bytes ─────────────────────────────────────────── */

int recv_all(SOCKET s, char *buf, int size)
{
    int received = 0;
    while (received < size) {
        int r = recv(s, buf + received, size - received, 0);
        if (r <= 0) return received;
        received += r;
    }
    return received;
}

/* ── Invia stringa ──────────────────────────────────────────────────────── */

void send_str(SOCKET s, const char *msg)
{
    send(s, msg, strlen(msg), 0);
}

/* ── Gestione connessione client (thread) ───────────────────────────────── */

DWORD WINAPI handle_client(LPVOID param)
{
    SOCKET client = (SOCKET)param;
    char header_buf[4096] = {0};
    int  header_len = 0;
    char logbuf[1024];

    /* Leggi header JSON fino a \n */
    char c;
    while (header_len < (int)sizeof(header_buf) - 1) {
        int r = recv(client, &c, 1, 0);
        if (r <= 0) goto cleanup;
        if (c == '\n') break;
        header_buf[header_len++] = c;
    }
    header_buf[header_len] = '\0';

    /* Estrai comando */
    char comando[64] = {0};
    char progetto[MAX_PATH_LEN] = {0};
    json_get_string(header_buf, "comando",  comando,  sizeof(comando));
    json_get_string(header_buf, "progetto", progetto, sizeof(progetto));

    /* Cartella destinazione */
    char destdir[MAX_PATH_LEN * 2];
    if (strlen(progetto) > 0)
        sprintf(destdir, "%s\\%s", g_basepath, progetto);
    else
        strncpy(destdir, g_basepath, sizeof(destdir) - 1);

    /* ── CHECK ────────────────────────────────────────────────────────── */
    if (strcmp(comando, "CHECK") == 0) {
        char files[256][MAX_PATH_LEN];
        int  nfiles = json_get_files(header_buf, files, 256);

        /* Trova file esistenti */
        char esistenti[256][MAX_PATH_LEN];
        int  n_esistenti = 0;

        for (int i = 0; i < nfiles; i++) {
            char fullpath[MAX_PATH_LEN * 2];
            sprintf(fullpath, "%s\\%s", destdir, files[i]);
            if (GetFileAttributesA(fullpath) != INVALID_FILE_ATTRIBUTES)
                strncpy(esistenti[n_esistenti++], files[i], MAX_PATH_LEN - 1);
        }

        /* Costruisci risposta JSON */
        char resp[8192] = {0};
        strcat(resp, "{\"esistenti\":[");
        for (int i = 0; i < n_esistenti; i++) {
            if (i > 0) strcat(resp, ",");
            strcat(resp, "\"");
            strcat(resp, esistenti[i]);
            strcat(resp, "\"");
        }
        strcat(resp, "],\"dest_dir\":\"");
        /* Escape backslash per JSON */
        for (const char *p = destdir; *p; p++) {
            if (*p == '\\') strcat(resp, "\\\\");
            else { char tmp[2] = {*p, 0}; strcat(resp, tmp); }
        }
        strcat(resp, "\"}");
        send_str(client, resp);

        sprintf(logbuf, "CHECK [%s]: %d file, %d esistenti", progetto, nfiles, n_esistenti);
        log_msg(logbuf);
    }

    /* ── INVIA ────────────────────────────────────────────────────────── */
    else if (strcmp(comando, "INVIA") == 0) {
        char filename[MAX_PATH_LEN] = {0};
        int  filesize = 0;

        json_get_string(header_buf, "filename", filename, sizeof(filename));
        filesize = json_get_int(header_buf, "filesize");

        /* Crea cartella se non esiste */
        if (GetFileAttributesA(destdir) == INVALID_FILE_ATTRIBUTES) {
            create_dir_recursive(destdir);
            sprintf(logbuf, "Cartella creata: %s", destdir);
            log_msg(logbuf);
        }

        /* Ricevi file */
        char *filebuf = (char*)malloc(filesize + 1);
        if (!filebuf) {
            send_str(client, "ERRORE: memoria insufficiente");
            goto cleanup;
        }

        int received = recv_all(client, filebuf, filesize);

        if (received != filesize) {
            sprintf(logbuf, "ERRORE: ricevuti %d/%d bytes per %s", received, filesize, filename);
            log_msg(logbuf);
            free(filebuf);
            send_str(client, "ERRORE: trasferimento incompleto");
            goto cleanup;
        }

        /* Scrivi file */
        char destpath[MAX_PATH_LEN * 2];
        sprintf(destpath, "%s\\%s", destdir, filename);

        FILE *f = fopen(destpath, "wb");
        if (!f) {
            sprintf(logbuf, "ERRORE: impossibile scrivere %s", destpath);
            log_msg(logbuf);
            free(filebuf);
            send_str(client, "ERRORE: impossibile scrivere il file");
            goto cleanup;
        }

        fwrite(filebuf, 1, filesize, f);
        fclose(f);
        free(filebuf);

        sprintf(logbuf, "OK  %s  (%d bytes) -> %s", filename, filesize, destdir);
        log_msg(logbuf);
        send_str(client, "OK");
    }

    else {
        send_str(client, "ERRORE: comando sconosciuto");
    }

cleanup:
    closesocket(client);
    return 0;
}

/* ── Main ───────────────────────────────────────────────────────────────── */

int main(void)
{
    /* Inizializza mutex log */
    g_log_mutex = CreateMutex(NULL, FALSE, NULL);

    /* Carica config */
    load_config();

    char logbuf[1024];
    sprintf(logbuf, "MachineServer avviato - porta %d - cartella: %s", g_port, g_basepath);
    log_msg(logbuf);
    log_msg("In attesa di connessioni... (Ctrl+C per uscire)");

    /* Inizializza Winsock */
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2,2), &wsa) != 0) {
        log_msg("ERRORE: WSAStartup fallito");
        return 1;
    }

    /* Crea socket */
    SOCKET srv = socket(AF_INET, SOCK_STREAM, 0);
    if (srv == INVALID_SOCKET) {
        log_msg("ERRORE: impossibile creare socket");
        WSACleanup();
        return 1;
    }

    /* Permetti riuso porta */
    int opt = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, (char*)&opt, sizeof(opt));

    /* Bind */
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port        = htons(g_port);

    if (bind(srv, (struct sockaddr*)&addr, sizeof(addr)) == SOCKET_ERROR) {
        sprintf(logbuf, "ERRORE: bind fallito sulla porta %d (porta gia' in uso?)", g_port);
        log_msg(logbuf);
        closesocket(srv);
        WSACleanup();
        return 1;
    }

    listen(srv, 10);

    sprintf(logbuf, "Server in ascolto su porta %d", g_port);
    log_msg(logbuf);

    /* Loop principale */
    while (1) {
        struct sockaddr_in client_addr;
        int client_len = sizeof(client_addr);
        SOCKET client = accept(srv, (struct sockaddr*)&client_addr, &client_len);

        if (client == INVALID_SOCKET) continue;

        sprintf(logbuf, "Connessione da %s", inet_ntoa(client_addr.sin_addr));
        log_msg(logbuf);

        /* Thread per ogni client */
        HANDLE t = CreateThread(NULL, 0, handle_client, (LPVOID)client, 0, NULL);
        if (t) CloseHandle(t);
        else closesocket(client);
    }

    closesocket(srv);
    WSACleanup();
    return 0;
}
