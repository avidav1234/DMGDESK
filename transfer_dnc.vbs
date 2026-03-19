' transfer_dnc.vbs - Trasferisce un file specifico alla NCU via DncOCX
' Posizione: F:\ADD_ON\DNC\transfer_dnc.vbs
' Uso: cscript //Nologo "F:\ADD_ON\DNC\transfer_dnc.vbs" "D:\tmp\autoimport\MISURA2.MPF"
' Richiede: DNCMachine.exe aperto

On Error Resume Next

' ── Leggi argomento (path file da trasferire) ────────────────────────────────
Dim filepath
filepath = ""
If WScript.Arguments.Count > 0 Then
    filepath = WScript.Arguments(0)
End If

' ── Crea oggetto DncOCX ──────────────────────────────────────────────────────
Dim dnc
Set dnc = CreateObject("DncOCX.CopyDNC")

If Err.Number <> 0 Then
    WScript.Echo "ERRORE: DncOCX.CopyDNC non disponibile: " & Err.Description
    WScript.Quit(1)
End If

Err.Clear

' ── Trasferimento ─────────────────────────────────────────────────────────────
If filepath <> "" Then
    ' Trasferisce il file specifico tramite CopyDNC (immediato)
    dnc.CopyDNC filepath
    If Err.Number = 0 Then
        WScript.Echo "OK CopyDNC: " & filepath
        WScript.Quit(0)
    End If
    ' Se CopyDNC fallisce, prova TransferAutom come fallback
    Err.Clear
End If

' Fallback: TransferAutom (avvia ciclo import automatico)
dnc.TransferAutom

If Err.Number = 0 Then
    WScript.Echo "OK TransferAutom"
    WScript.Quit(0)
Else
    WScript.Echo "ERRORE: " & Err.Number & " - " & Err.Description
    WScript.Quit(2)
End If
