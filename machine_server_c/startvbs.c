/*
 * startvbs.c - Launcher VBS per Sinumerik 840D / Regie.ini
 *
 * Legge il path del VBS da startvbs_config.ini nella stessa cartella dell'exe.
 * Se il config non esiste, usa il path di default.
 *
 * Compilazione (statica — zero DLL esterne):
 *   i686-w64-mingw32-gcc -static -static-libgcc -mwindows -o StartVBS.exe startvbs.c
 *
 * Config (startvbs_config.ini):
 *   [vbs]
 *   path=F:\oem\esporta_stato_macchina.vbs
 */

#include <windows.h>
#include <stdio.h>
#include <string.h>

#define DEFAULT_VBS "F:\\oem\\esporta_stato_macchina.vbs"
#define MAX_PATH_LEN 512

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrev,
                   LPSTR lpCmdLine, int nCmdShow)
{
    (void)hInstance; (void)hPrev; (void)lpCmdLine; (void)nCmdShow;

    /* Costruisce path config nella stessa cartella dell'exe */
    char exe_path[MAX_PATH_LEN] = {0};
    char cfg_path[MAX_PATH_LEN] = {0};
    GetModuleFileNameA(NULL, exe_path, sizeof(exe_path));
    char *slash = strrchr(exe_path, '\\');
    if (slash) {
        *(slash + 1) = '\0';
        snprintf(cfg_path, sizeof(cfg_path), "%sstartvbs_config.ini", exe_path);
    } else {
        strncpy(cfg_path, "startvbs_config.ini", sizeof(cfg_path));
    }

    /* Legge path VBS dal config */
    char vbs_path[MAX_PATH_LEN] = {0};
    GetPrivateProfileStringA("vbs", "path", DEFAULT_VBS,
                             vbs_path, sizeof(vbs_path), cfg_path);

    /* Verifica che il VBS esista */
    if (GetFileAttributesA(vbs_path) == INVALID_FILE_ATTRIBUTES) {
        /* VBS non trovato — scrivi log e termina */
        char log_path[MAX_PATH_LEN] = {0};
        if (slash) {
            char tmp[MAX_PATH_LEN];
            strncpy(tmp, exe_path, sizeof(tmp));
            snprintf(log_path, sizeof(log_path), "%sstartvbs_error.log", tmp);
        } else {
            strncpy(log_path, "startvbs_error.log", sizeof(log_path));
        }
        FILE *f = fopen(log_path, "w");
        if (f) {
            fprintf(f, "StartVBS: file non trovato: %s\n", vbs_path);
            fclose(f);
        }
        return 1;
    }

    /* Costruisce comando: wscript.exe "path_vbs" */
    char cmd[MAX_PATH_LEN * 2] = {0};
    snprintf(cmd, sizeof(cmd), "wscript.exe \"%s\"", vbs_path);

    /* Lancia wscript in background — non aspetta la fine */
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;
    ZeroMemory(&pi, sizeof(pi));

    BOOL ok = CreateProcessA(
        NULL,           /* modulo — usa cmd */
        cmd,            /* comando completo */
        NULL, NULL,     /* security attributes */
        FALSE,          /* inherit handles */
        CREATE_NO_WINDOW | DETACHED_PROCESS,
        NULL,           /* environment */
        NULL,           /* working directory */
        &si, &pi
    );

    if (ok) {
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
    } else {
        /* Log errore */
        char log_path[MAX_PATH_LEN] = {0};
        if (slash) {
            char tmp[MAX_PATH_LEN];
            strncpy(tmp, exe_path, sizeof(tmp));
            snprintf(log_path, sizeof(log_path), "%sstartvbs_error.log", tmp);
        }
        FILE *f = fopen(log_path, "w");
        if (f) {
            fprintf(f, "StartVBS: CreateProcess fallito per: %s\n  Errore: %lu\n",
                    cmd, GetLastError());
            fclose(f);
        }
        return 2;
    }

    return 0;
}
