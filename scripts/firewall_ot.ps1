<#
.SYNOPSIS
    Chiude i canali OT non autenticati di DMG Desk (porta 9999 = server DNC C#,
    opzionale 5900 = VNC PCU) sulla macchina che li espone.

.DESCRIPTION
    Reperto piu' grave dell'assessment: il server DNC su :9999 accetta comandi di
    caricamento/esecuzione programma sulla CNC SENZA autenticazione, da qualunque
    host della LAN. Questo script lo mitiga a livello firewall Windows, senza
    toccare la macchina.

    Due modalita':
      - BLOCCA (default): blocca del tutto la porta in ingresso. Consigliato per
        :9999 se il canale non e' usato ("non ha mai funzionato").
      - SOLO-BACKEND (-Backend <IP>): consente la porta SOLO dall'IP del backend
        DD e la nega a tutti gli altri. Usare se il canale serve davvero.

    Le regole sono prefissate "DMG-OT-" e sono idempotenti (rilanciabile).
    Per annullare: -Rimuovi.

.PARAMETER Porte
    Porte TCP da chiudere. Default: 9999. Per includere anche il VNC: -Porte 9999,5900
    (⚠ 5900 va chiuso sul PCU / a livello di rete, NON sul backend che deve
     poterci uscire per il relay: bloccarlo qui serve solo se questa macchina
     ESPONE il 5900).

.PARAMETER Backend
    IP del backend DD. Se indicato → modalita' SOLO-BACKEND. Altrimenti → BLOCCA.

.PARAMETER Rimuovi
    Elimina le regole "DMG-OT-*" create da questo script (rollback).

.EXAMPLE
    # Blocca del tutto la 9999 (canale inutilizzato)
    powershell -ExecutionPolicy Bypass -File scripts\firewall_ot.ps1

.EXAMPLE
    # Consenti la 9999 solo dal backend 10.95.20.50
    powershell -ExecutionPolicy Bypass -File scripts\firewall_ot.ps1 -Backend 10.95.20.50

.EXAMPLE
    # Rollback
    powershell -ExecutionPolicy Bypass -File scripts\firewall_ot.ps1 -Rimuovi

.NOTES
    Richiede PowerShell come AMMINISTRATORE. Testato su Windows 10/11 / Server.
#>
[CmdletBinding()]
param(
    [int[]] $Porte = @(9999),
    [string] $Backend = "",
    [switch] $Rimuovi
)

$ErrorActionPreference = "Stop"

# Verifica privilegi admin
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "Esegui questo script come AMMINISTRATORE (tasto destro → 'Esegui come amministratore')."
    exit 1
}

function Remove-DmgRule([string] $name) {
    $existing = Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue
    if ($existing) {
        $existing | Remove-NetFirewallRule
        Write-Host "  rimossa regola esistente: $name" -ForegroundColor DarkGray
    }
}

if ($Rimuovi) {
    Write-Host "Rollback regole DMG-OT-* ..." -ForegroundColor Yellow
    Get-NetFirewallRule -DisplayName "DMG-OT-*" -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "  rimossa: $($_.DisplayName)" -ForegroundColor DarkGray
        $_ | Remove-NetFirewallRule
    }
    Write-Host "Fatto." -ForegroundColor Green
    exit 0
}

$soloBackend = -not [string]::IsNullOrWhiteSpace($Backend)

foreach ($porta in $Porte) {
    Write-Host "Porta TCP ${porta}:" -ForegroundColor Cyan

    if ($soloBackend) {
        # SOLO-BACKEND: la porta e' consentita solo dall'IP backend, negata al resto.
        # In Windows Firewall una regola BLOCK vince su una ALLOW, quindi la logica
        # e': disabilitare eventuali ALLOW larghe preesistenti su questa porta,
        # poi creare UNA allow ristretta all'IP backend (con default-deny in ingresso
        # il resto della LAN resta fuori).
        $conflitti = Get-NetFirewallRule -Direction Inbound -Action Allow -Enabled True -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -notlike "DMG-OT-*" } |
            Where-Object {
                $pf = $_ | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue
                $pf -and $pf.Protocol -eq "TCP" -and ($pf.LocalPort -eq "$porta")
            }
        foreach ($c in $conflitti) {
            Disable-NetFirewallRule -Name $c.Name
            Write-Host "  disabilitata allow larga preesistente: $($c.DisplayName)" -ForegroundColor DarkYellow
        }

        $nameAllow = "DMG-OT-allow-$porta-backend"
        Remove-DmgRule $nameAllow
        New-NetFirewallRule -DisplayName $nameAllow -Direction Inbound -Action Allow `
            -Protocol TCP -LocalPort $porta -RemoteAddress $Backend `
            -Profile Any -Description "DMG Desk: consenti $porta solo dal backend $Backend" | Out-Null
        Write-Host "  ✔ consentita SOLO da $Backend (resto negato dal default-deny)" -ForegroundColor Green
        Write-Host "    verifica che il profilo firewall abbia InboundAction=Block di default." -ForegroundColor DarkGray
    }
    else {
        # BLOCCA: nega la porta in ingresso a tutti. Block vince sempre.
        $nameBlock = "DMG-OT-block-$porta"
        Remove-DmgRule $nameBlock
        New-NetFirewallRule -DisplayName $nameBlock -Direction Inbound -Action Block `
            -Protocol TCP -LocalPort $porta -Profile Any `
            -Description "DMG Desk: blocca canale OT non autenticato su $porta" | Out-Null
        Write-Host "  ✔ bloccata in ingresso per tutti" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Regole attive:" -ForegroundColor Cyan
Get-NetFirewallRule -DisplayName "DMG-OT-*" | Select-Object DisplayName, Enabled, Direction, Action | Format-Table -AutoSize
Write-Host "Rollback in qualsiasi momento:  scripts\firewall_ot.ps1 -Rimuovi" -ForegroundColor DarkGray
