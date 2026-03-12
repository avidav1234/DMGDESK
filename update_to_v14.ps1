# Tool Manager - Aggiornamento Automatico Versione
# Da V12.4/V13 a V14

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TOOL MANAGER - AGGIORNAMENTO V14" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$files = @(
    "config\constants.py",
    "ui\main_window.py",
    "main.py",
    "logic\code_generator_logic.py",
    "ui\tab_generatore.py",
    "README.md"
)

$updated = 0
$notFound = 0

foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "Aggiornamento: $file" -ForegroundColor Yellow
        
        $content = Get-Content $file -Raw -Encoding UTF8
        $originalContent = $content
        
        # Sostituisci V12.4 con V14
        $content = $content -replace 'V12\.4', 'V14'
        $content = $content -replace 'v12\.4', 'v14'
        
        # Sostituisci 12.4 con 14.0 (solo per versioni)
        $content = $content -replace '(["\x27])12\.4(["\x27])', '$114.0$2'
        
        # Sostituisci V13 con V14 (per i file nuovi)
        $content = $content -replace '(?<!V1)V13(?!\.)', 'V14'
        $content = $content -replace 'v13', 'v14'
        
        # Verifica se ci sono state modifiche
        if ($content -ne $originalContent) {
            Set-Content $file -Value $content -Encoding UTF8 -NoNewline
            Write-Host "  ✅ Aggiornato" -ForegroundColor Green
            $updated++
        } else {
            Write-Host "  ℹ️  Nessuna modifica necessaria" -ForegroundColor Gray
        }
    } else {
        Write-Host "  ⚠️  $file non trovato" -ForegroundColor Red
        $notFound++
    }
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  RIEPILOGO" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "File aggiornati:  $updated" -ForegroundColor Green
Write-Host "File non trovati: $notFound" -ForegroundColor $(if ($notFound -gt 0) { "Red" } else { "Green" })
Write-Host ""

if ($updated -gt 0) {
    Write-Host "✅ AGGIORNAMENTO COMPLETATO!" -ForegroundColor Green
    Write-Host "Versione aggiornata a V14" -ForegroundColor Green
} else {
    Write-Host "ℹ️  Nessun file da aggiornare" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Premi un tasto per continuare..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
