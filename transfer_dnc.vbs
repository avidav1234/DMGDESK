' transfer_dnc.vbs - Trasferisce un file specifico alla NCU via DncOCX
' Posizione: F:\ADD_ON\DNC\transfer_dnc.vbs
' Uso: cscript //Nologo "F:\ADD_ON\DNC\transfer_dnc.vbs" "D:\tmp\autoimport\MISURA2.MPF"

On Error Resume Next

Const LOG_FILE = "F:\ADD_ON\DNC\transfer_dnc_log.txt"

' Log su file
Sub WriteLog(msg)
    Dim fso, f
    Set fso = CreateObject("Scripting.FileSystemObject")
    Set f = fso.OpenTextFile(LOG_FILE, 8, True) ' 8 = append, True = crea se non esiste
    f.WriteLine Now() & " " & msg
    f.Close
End Sub

' Leggi argomento
Dim filepath
filepath = ""
If WScript.Arguments.Count > 0 Then
    filepath = WScript.Arguments(0)
End If

WriteLog "--- avvio --- filepath=" & filepath

' Crea oggetto DncOCX
Dim dnc
Set dnc = CreateObject("DncOCX.CopyDNC")

If Err.Number <> 0 Then
    WriteLog "ERRORE CreateObject: " & Err.Number & " - " & Err.Description
    WScript.Echo "ERRORE: DncOCX.CopyDNC non disponibile: " & Err.Description
    WScript.Quit(1)
End If

WriteLog "DncOCX creato OK"
Err.Clear

' Trasferimento
If filepath <> "" Then
    WriteLog "CopyDNC: " & filepath
    dnc.CopyDNC filepath
    If Err.Number = 0 Then
        WriteLog "OK CopyDNC"
        WScript.Echo "OK CopyDNC: " & filepath
        WScript.Quit(0)
    End If
    WriteLog "CopyDNC fallito: " & Err.Number & " - " & Err.Description & " — provo TransferAutom"
    Err.Clear
End If

' Fallback TransferAutom
WriteLog "TransferAutom..."
dnc.TransferAutom

If Err.Number = 0 Then
    WriteLog "OK TransferAutom"
    WScript.Echo "OK TransferAutom"
    WScript.Quit(0)
Else
    WriteLog "ERRORE TransferAutom: " & Err.Number & " - " & Err.Description
    WScript.Echo "ERRORE: " & Err.Number & " - " & Err.Description
    WScript.Quit(2)
End If
