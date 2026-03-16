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


/* ── Generazione _dhinf.000 ─────────────────────────────────────────────── */

#define DHINF_RECORD_SIZE  71
#define DHINF_FILENAME     "_dhinf.000"

static void make_siemens_name(const char *original, int index, char *out)
{
    static const char counter_chars[] = "_0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-";
    int len = (int)strlen(original);
    int i;
    if (len <= 8) {
        strncpy(out, original, 8); out[len] = '\0'; return;
    }
    if (index == 0) {
        strncpy(out, original, 8); out[8] = '\0';
    } else {
        int ci = (index < (int)(sizeof(counter_chars)-1)) ? index : (int)(sizeof(counter_chars)-2);
        out[0] = original[0]; out[1] = counter_chars[ci];
        for (i = 2; i < 8; i++) out[i] = original[i];
        out[8] = '\0';
    }
}

static void dhinf_update(const char *destdir, const char *filename)
{
    char dhinf_path[MAX_PATH_LEN * 2];
    unsigned char record[DHINF_RECORD_SIZE];
    unsigned char existing[DHINF_RECORD_SIZE];
    FILE *f;
    int found = 0, nrecords = 0, i, snlen, onlen;
    char siemens_name[16];
    char logbuf[1024];

    sprintf(dhinf_path, "%s\\%s", destdir, DHINF_FILENAME);

    f = fopen(dhinf_path, "rb");
    if (f) {
        while (fread(existing, 1, DHINF_RECORD_SIZE, f) == DHINF_RECORD_SIZE) {
            char orig_in_file[32] = {0};
            strncpy(orig_in_file, (char*)existing + 13, 24);
            if (strcmp(orig_in_file, filename) == 0) { found = 1; break; }
            nrecords++;
        }
        fclose(f);
        if (found) return;
    }

    make_siemens_name(filename, nrecords, siemens_name);

    memset(record, 0, DHINF_RECORD_SIZE);
    record[0]='M'; record[1]='P'; record[2]='F'; record[3]=0;
    snlen = (int)strlen(siemens_name);
    for (i = 0; i < snlen && i < 8; i++) record[4+i] = (unsigned char)siemens_name[i];
    record[4+snlen] = 0;
    onlen = (int)strlen(filename);
    for (i = 0; i < onlen && i < 24; i++) record[13+i] = (unsigned char)filename[i];
    record[13+onlen] = 0;
    record[39] = 0x2a;
    record[65]='6'; record[66]='5'; record[67]='7';
    record[68]='7'; record[69]='5'; record[70]=0;

    f = fopen(dhinf_path, "ab");
    if (f) {
        fwrite(record, 1, DHINF_RECORD_SIZE, f);
        fclose(f);
        sprintf(logbuf, "dhinf: aggiunto %s -> %s", filename, siemens_name);
        log_msg(logbuf);
    } else {
        sprintf(logbuf, "WARN: impossibile aggiornare %s", dhinf_path);
        log_msg(logbuf);
    }
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

    /* Cartella destinazione - aggiunge .WPD se progetto specificato */
    char destdir[MAX_PATH_LEN * 2];
    if (strlen(progetto) > 0)
        sprintf(destdir, "%s\\%s.WPD", g_basepath, progetto);
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

        /* Verifica cartella - deve essere creata dall'HMI Sinumerik */
        if (GetFileAttributesA(destdir) == INVALID_FILE_ATTRIBUTES) {
            sprintf(logbuf, "ERRORE: cartella non trovata: %s", destdir);
            log_msg(logbuf);
            send_str(client, "ERRORE: cartella progetto non esiste. Crearla prima dall'HMI Sinumerik.");
            goto cleanup;
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

        /* Aggiorna _dhinf.000 per far riconoscere il file come MPF */
        dhinf_update(destdir, filename);

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
