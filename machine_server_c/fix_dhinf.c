/*
 * fix_dhinf.c - Genera _dhinf.000 nel formato corretto per Siemens 840D PowerLine
 *
 * Formato record (71 bytes):
 *   [0-3]   "MPF\0"          tipo file
 *   [4-?]   short_name\0     nome 8.3 (da GetShortPathNameA)
 *   [?-?]   long_name\0      nome completo NC
 *   [39]    0x2A             marker fisso
 *   [40-64] 0x00             padding
 *   [65-69] "65775"          costante formato
 *   [70]    0x00
 *
 * Compilazione:
 *   i686-w64-mingw32-gcc -o FixDhinf.exe fix_dhinf.c -lshlwapi
 *
 * Uso:
 *   FixDhinf.exe "F:\dh\wks.dir\TEST.WPD"
 *   FixDhinf.exe "F:\dh\wks.dir\TEST.WPD" MPF
 *   FixDhinf.exe "F:\dh\wks.dir\TEST.WPD" SPF
 */

#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <shlwapi.h>

#define RECORD_SIZE 71
#define MARKER_POS  39
#define CONST_POS   65

/* Scrive un record di 71 bytes nel file */
static void write_record(FILE *f,
                          const char *type,       /* "MPF" */
                          const char *short_name, /* max 8 chars */
                          const char *long_name)  /* nome completo */
{
    unsigned char r[RECORD_SIZE];
    memset(r, 0, RECORD_SIZE);

    /* Tipo file [0-3] */
    int tlen = (int)strlen(type);
    if (tlen > 3) tlen = 3;
    memcpy(r, type, tlen);
    r[3] = 0x00;

    /* Nome corto [4..] null-terminated */
    int slen = (int)strlen(short_name);
    if (slen > 8) slen = 8;
    memcpy(r + 4, short_name, slen);
    r[4 + slen] = 0x00;

    /* Nome lungo [4+slen+1..] null-terminated */
    int lstart = 4 + slen + 1;
    int llen   = (int)strlen(long_name);
    int lmax   = MARKER_POS - lstart - 1; /* lascia spazio per null prima del marker */
    if (lmax < 0) lmax = 0;
    if (llen > lmax) llen = lmax;
    memcpy(r + lstart, long_name, llen);
    r[lstart + llen] = 0x00;

    /* Marker 0x2A a posizione 39 */
    r[MARKER_POS] = 0x2A;

    /* Costante "65775" a posizione 65 */
    r[CONST_POS + 0] = '6';
    r[CONST_POS + 1] = '5';
    r[CONST_POS + 2] = '7';
    r[CONST_POS + 3] = '7';
    r[CONST_POS + 4] = '5';
    r[70] = 0x00;

    fwrite(r, 1, RECORD_SIZE, f);
}

/* Ottieni il nome 8.3 del file (short name FAT) */
static void get_short_name(const char *full_path, char *out, int n)
{
    char short_path[MAX_PATH] = {0};
    DWORD r = GetShortPathNameA(full_path, short_path, MAX_PATH);
    if (r == 0) {
        /* Fallback: usa i primi 8 chars del nome file */
        const char *base = PathFindFileNameA(full_path);
        strncpy(out, base, 8);
        out[8] = '\0';
        return;
    }
    /* Estrai solo il nome file (senza percorso) */
    const char *base = PathFindFileNameA(short_path);
    /* Rimuovi eventuale estensione */
    char tmp[MAX_PATH];
    strncpy(tmp, base, MAX_PATH);
    char *dot = strrchr(tmp, '.');
    if (dot) *dot = '\0';
    strncpy(out, tmp, n);
    out[n-1] = '\0';
}

int main(int argc, char *argv[])
{
    if (argc < 2) {
        fprintf(stderr, "Uso: FixDhinf.exe <cartella_wpd> [tipo=MPF|SPF]\n");
        fprintf(stderr, "  es: FixDhinf.exe \"F:\\dh\\wks.dir\\TEST.WPD\"\n");
        return 1;
    }

    const char *wpd_folder = argv[1];
    const char *file_type  = (argc >= 3) ? argv[2] : "MPF";

    if (!PathIsDirectoryA(wpd_folder)) {
        fprintf(stderr, "[ERRORE] Cartella non trovata: %s\n", wpd_folder);
        return 2;
    }

    /* Backup del _dhinf.000 esistente */
    char dhinf_path[MAX_PATH], backup_path[MAX_PATH];
    snprintf(dhinf_path, MAX_PATH, "%s\\_dhinf.000", wpd_folder);
    snprintf(backup_path, MAX_PATH, "%s\\_dhinf.bak", wpd_folder);

    if (PathFileExistsA(dhinf_path)) {
        CopyFileA(dhinf_path, backup_path, FALSE);
        printf("[INFO] Backup: %s\n", backup_path);
    }

    /* Apri file output */
    FILE *out = fopen(dhinf_path, "wb");
    if (!out) {
        fprintf(stderr, "[ERRORE] Impossibile scrivere: %s\n", dhinf_path);
        return 3;
    }

    /* Scorri i file nella cartella WPD */
    char pattern[MAX_PATH];
    snprintf(pattern, MAX_PATH, "%s\\*", wpd_folder);

    WIN32_FIND_DATAA fd;
    HANDLE hf = FindFirstFileA(pattern, &fd);

    int count = 0;

    if (hf != INVALID_HANDLE_VALUE) {
        do {
            /* Salta directory e file di sistema */
            if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
            if (fd.cFileName[0] == '_') continue;   /* _dhinf.000, _dhinf.sav */

            /* Nome lungo = nome file senza estensione, maiuscolo */
            char long_name[MAX_PATH];
            strncpy(long_name, fd.cFileName, MAX_PATH);
            long_name[MAX_PATH-1] = '\0';
            char *dot = strrchr(long_name, '.');
            if (dot) *dot = '\0';
            /* Maiuscolo */
            for (int i = 0; long_name[i]; i++)
                if (long_name[i] >= 'a' && long_name[i] <= 'z')
                    long_name[i] -= 32;

            /* Nome corto = nome 8.3 dal filesystem */
            char short_name[16] = {0};
            char full_path[MAX_PATH];
            snprintf(full_path, MAX_PATH, "%s\\%s", wpd_folder, fd.cFileName);
            get_short_name(full_path, short_name, sizeof(short_name));

            write_record(out, file_type, short_name, long_name);
            printf("[OK] %s  (short: %s, long: %s, type: %s)\n",
                   fd.cFileName, short_name, long_name, file_type);
            count++;

        } while (FindNextFileA(hf, &fd));
        FindClose(hf);
    }

    fclose(out);

    printf("\n[DONE] %d record scritti in %s\n", count, dhinf_path);
    printf("\n>>> Ora nell'HMI: esci dalla cartella %s e rientra.\n",
           PathFindFileNameA(wpd_folder));
    printf(">>> Controlla se i file appaiono con tipo %s.\n", file_type);

    return 0;
}
