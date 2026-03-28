/*
 * startvbs.c - Launcher VBS per Sinumerik 840D / Regie.ini
 *
 * Lancia direttamente: wscript.exe "F:\oem\esporta_stato_macchina.vbs"
 * Scrive startvbs_error.log nella stessa cartella se fallisce.
 *
 * Compilazione (statica — zero DLL esterne):
 *   i686-w64-mingw32-gcc -static -static-libgcc -mwindows -o StartVBS.exe startvbs.c
 */

#include <windows.h>
#include <stdio.h>
#include <string.h>

#define VBS_PATH "F:\\oem\\esporta_stato_macchina.vbs"
#define MAX_PATH_LEN 512

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrev,
                   LPSTR lpCmdLine, int nCmdShow)
{
    (void)hInstance; (void)hPrev; (void)lpCmdLine; (void)nCmdShow;

    /* Cartella dell'exe — per il log errori */
    char exe_path[MAX_PATH_LEN] = {0};
    GetModuleFileNameA(NULL, exe_path, sizeof(exe_path));
    char *slash = strrchr(exe_path, '\\');
    if (slash) *(slash + 1) = '\0';

    /* Verifica che il VBS esista */
    if (GetFileAttributesA(VBS_PATH) == INVALID_FILE_ATTRIBUTES) {
        char log_path[MAX_PATH_LEN] = {0};
        snprintf(log_path, sizeof(log_path), "%sstartvbs_error.log", exe_path);
        FILE *f = fopen(log_path, "w");
        if (f) {
            fprintf(f, "StartVBS: file non trovato: %s\n", VBS_PATH);
            fclose(f);
        }
        return 1;
    }

    /* Comando: wscript.exe "F:\oem\esporta_stato_macchina.vbs" */
    char cmd[MAX_PATH_LEN * 2] = {0};
    snprintf(cmd, sizeof(cmd), "wscript.exe \"%s\"", VBS_PATH);

    /* Lancia in background senza finestra */
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;
    ZeroMemory(&pi, sizeof(pi));

    BOOL ok = CreateProcessA(
        NULL, cmd, NULL, NULL, FALSE,
        CREATE_NO_WINDOW | DETACHED_PROCESS,
        NULL, NULL, &si, &pi
    );

    if (ok) {
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
    } else {
        char log_path[MAX_PATH_LEN] = {0};
        snprintf(log_path, sizeof(log_path), "%sstartvbs_error.log", exe_path);
        FILE *f = fopen(log_path, "w");
        if (f) {
            fprintf(f, "StartVBS: CreateProcess fallito\n  cmd: %s\n  errore: %lu\n",
                    cmd, GetLastError());
            fclose(f);
        }
        return 2;
    }

    return 0;
}
