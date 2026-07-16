# Test-TncVncAuth.ps1 — Scopre quale autenticazione richiede il server VNC (RFB 3.x)
# Passivo: negozia solo la versione e legge la lista dei security-types. NON accede
# al framebuffer, NON invia input, NON tenta login. Uso: .\Test-TncVncAuth.ps1 -Ip 192.168.244.149

param(
    [Parameter(Mandatory = $true)][string]$Ip,
    [int]$Port = 5900,
    [int]$TimeoutMs = 3000
)

$secNames = @{
    0  = "Invalid / connessione rifiutata"
    1  = "None (NESSUNA password richiesta)"
    2  = "VNC Authentication (password DES classica)"
    5  = "RA2"; 6 = "RA2ne"
    16 = "Tight"; 17 = "Ultra"; 18 = "TLS"; 19 = "VeNCrypt"; 30 = "Apple ARD"
}

$c = New-Object System.Net.Sockets.TcpClient
try {
    $iar = $c.BeginConnect($Ip, $Port, $null, $null)
    if (-not $iar.AsyncWaitHandle.WaitOne($TimeoutMs)) { throw "timeout di connessione" }
    $c.EndConnect($iar)
    $s = $c.GetStream(); $s.ReadTimeout = $TimeoutMs; $s.WriteTimeout = $TimeoutMs

    # 1) Leggi ProtocolVersion del server (12 byte)
    $srv = New-Object byte[] 12
    $null = $s.Read($srv, 0, 12)
    $srvVer = ([Text.Encoding]::ASCII.GetString($srv, 0, 12)).Trim()
    Write-Host "Versione protocollo server: $srvVer" -ForegroundColor Cyan

    # 2) Rispondi con la nostra versione (RFB 003.008)
    $ourVer = [Text.Encoding]::ASCII.GetBytes("RFB 003.008`n")
    $s.Write($ourVer, 0, $ourVer.Length); $s.Flush()

    # 3) Leggi numero di security-types (1 byte)
    $cntB = New-Object byte[] 1
    $null = $s.Read($cntB, 0, 1)
    $cnt = [int]$cntB[0]

    if ($cnt -eq 0) {
        # 0 => seguono 4 byte lunghezza + stringa motivo del rifiuto
        $lenB = New-Object byte[] 4
        $null = $s.Read($lenB, 0, 4)
        [array]::Reverse($lenB); $len = [BitConverter]::ToUInt32($lenB, 0)
        $reasonB = New-Object byte[] $len
        $null = $s.Read($reasonB, 0, $len)
        $reason = [Text.Encoding]::ASCII.GetString($reasonB, 0, $len)
        Write-Host "Server ha RIFIUTATO l'handshake: $reason" -ForegroundColor Red
    } else {
        $types = New-Object byte[] $cnt
        $null = $s.Read($types, 0, $cnt)
        Write-Host "Metodi di autenticazione offerti ($cnt):" -ForegroundColor Yellow
        foreach ($t in $types) {
            $name = if ($secNames.ContainsKey([int]$t)) { $secNames[[int]$t] } else { "sconosciuto" }
            Write-Host ("  - tipo {0} = {1}" -f $t, $name)
        }
        if ($types -contains 1) {
            Write-Host "`n=> Il controllo accetta connessioni SENZA password." -ForegroundColor Green
        } elseif ($types -contains 2) {
            Write-Host "`n=> Serve la PASSWORD VNC (impostata a bordo: Settings -> VNC)." -ForegroundColor Green
        }
    }
    # NB: ci fermiamo qui di proposito — nessun SecurityResult, nessun login, nessun framebuffer.
    $c.Close()
} catch {
    Write-Host "Errore: $($_.Exception.Message)" -ForegroundColor Red
    if ($c) { $c.Close() }
}
