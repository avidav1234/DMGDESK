# Test-TncVnc.ps1 — Diagnosi VNC (e LSV2) di un controllo HEIDENHAIN TNC 640
# Uso:  .\Test-TncVnc.ps1 -Ip 192.168.1.50
# Non installa nulla. Verifica: porta aperta + handshake RFB del server VNC.

param(
    [Parameter(Mandatory = $true)][string]$Ip,
    [int]$VncPort = 5900,     # server VNC di HEROS
    [int]$Lsv2Port = 19000,   # LSV2 (TNCremo / pyLSV2) — controllato solo come extra
    [int]$TimeoutMs = 2000
)

function Test-TcpPort {
    param([string]$HostName, [int]$Port, [int]$TimeoutMs)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne($TimeoutMs)) {
            $client.Close(); return $null   # timeout: chiusa/filtrata
        }
        $client.EndConnect($iar)
        return $client                       # aperta: torna il socket connesso
    } catch {
        if ($client) { $client.Close() }
        return $null
    }
}

Write-Host "=== Diagnosi TNC 640 @ $Ip ===" -ForegroundColor Cyan

# --- 1) Server VNC (porta 5900) ---
Write-Host "`n[1] VNC  ($Ip`:$VncPort)" -ForegroundColor Yellow
$vnc = Test-TcpPort -HostName $Ip -Port $VncPort -TimeoutMs $TimeoutMs
if ($null -eq $vnc) {
    Write-Host "  Porta $VncPort NON raggiungibile (chiusa, firewall HEROS, o servizio VNC spento)." -ForegroundColor Red
} else {
    Write-Host "  Porta $VncPort APERTA." -ForegroundColor Green
    try {
        $stream = $vnc.GetStream()
        $stream.ReadTimeout = $TimeoutMs
        # Il server VNC invia subito 12 byte: "RFB 003.00x\n"
        $buf = New-Object byte[] 12
        $n = $stream.Read($buf, 0, 12)
        $banner = ([System.Text.Encoding]::ASCII.GetString($buf, 0, $n)).Trim()
        if ($banner -like "RFB*") {
            Write-Host "  -> Server VNC CONFERMATO. Handshake: '$banner'" -ForegroundColor Green
            Write-Host "     (la funzione dell'OEM e' VNC ed e' viva: basta un client per vederla)" -ForegroundColor Green
        } else {
            Write-Host "  -> Risponde ma NON con handshake RFB: '$banner'" -ForegroundColor DarkYellow
        }
    } catch {
        Write-Host "  -> Porta aperta ma nessun banner letto: $($_.Exception.Message)" -ForegroundColor DarkYellow
    } finally {
        $vnc.Close()
    }
}

# --- 2) LSV2 (porta 19000) — utile per la Fase 2 (pyLSV2/TNCremo) ---
Write-Host "`n[2] LSV2 ($Ip`:$Lsv2Port)" -ForegroundColor Yellow
$lsv2 = Test-TcpPort -HostName $Ip -Port $Lsv2Port -TimeoutMs $TimeoutMs
if ($null -eq $lsv2) {
    Write-Host "  Porta $Lsv2Port NON raggiungibile (LSV2 disattivo, o serve tunnel SSH)." -ForegroundColor Red
} else {
    Write-Host "  Porta $Lsv2Port APERTA (LSV2 disponibile per pyLSV2/TNCremo)." -ForegroundColor Green
    $lsv2.Close()
}

Write-Host "`n=== Fine diagnosi ===" -ForegroundColor Cyan
Write-Host "Se VNC e' CONFERMATO: la funzione OEM e' recuperabile senza comprare nulla." -ForegroundColor Cyan
